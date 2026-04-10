"""Core analysis engine for Fund Leader Tracker."""
import logging

from db_manager import DatabaseManager
from holdings_fetcher import HoldingsFetcher
from leader_identifier import LeaderIdentifier
from utils import Colors, print_colored, print_header

logger = logging.getLogger(__name__)


class FundAnalyzer:
    def __init__(self, config, api_key):
        self.config = config
        self.api_key = api_key
        self.sectors = config.get('sectors', [])
        self.analysis_config = config.get('analysis', {})

        api_config = config.get('api', {})
        self.fetcher = HoldingsFetcher(
            api_key=api_key,
            requests_per_minute=api_config.get('requests_per_minute', 5),
            verify_ssl=api_config.get('verify_ssl', True),
            retry_attempts=api_config.get('retry_attempts', 3),
            retry_delay=api_config.get('retry_delay', 5),
        )
        self.identifier = LeaderIdentifier(
            min_holding_threshold=self.analysis_config.get('min_holding_threshold', 1.0)
        )
        db_path = config.get('output', {}).get('database_path', 'data/fund_leaders.db')
        self.db = DatabaseManager(db_path)
        self.results = {}
        self.leadership_changes = []

    def analyze_all_sectors(self):
        print_header("Fund Leader Tracker - Starting Analysis")
        previous_leaders = self.db.get_latest_leaders_by_sector()
        total_funds_analyzed = 0
        total_leaders_found = 0

        for index, sector_config in enumerate(self.sectors, 1):
            sector_name = sector_config['name']
            keywords = sector_config.get('keywords', [])
            try:
                print_colored(f"\n[{index}/{len(self.sectors)}] Analyzing: {sector_name}", Colors.HEADER)
                fund_symbols = self._find_sector_funds(keywords, sector_name)
                if not fund_symbols:
                    print_colored(f"No tracked funds found for {sector_name}", Colors.WARNING)
                    continue

                print(f"Tracked funds: {', '.join(fund_symbols)}")
                holdings_by_fund = self.fetcher.batch_fetch_holdings(fund_symbols)
                if not holdings_by_fund:
                    print_colored(f"No holdings data retrieved for {sector_name}", Colors.WARNING)
                    continue

                leaders = self.identifier.analyze_holdings(holdings_by_fund, sector_name)
                total_funds_analyzed += len(fund_symbols)
                total_leaders_found += len(leaders)
                self._save_sector_results(sector_name, keywords, fund_symbols, holdings_by_fund, leaders)

                current_leader = leaders[0] if leaders else None
                self.results[sector_name] = {
                    'funds': fund_symbols,
                    'top_leader': current_leader,
                    'leaders': leaders[: self.analysis_config.get('export_top_n_leaders', 10)],
                    'holdings_count': sum(len(h) for h in holdings_by_fund.values()),
                }

                if current_leader and sector_name in previous_leaders:
                    prev_leader = previous_leaders[sector_name]
                    if prev_leader['symbol'] != current_leader['symbol']:
                        change = {
                            'sector': sector_name,
                            'old_symbol': prev_leader['symbol'],
                            'old_name': prev_leader['name'],
                            'new_symbol': current_leader['symbol'],
                            'new_name': current_leader['name'],
                            'new_times_held': current_leader['times_held'],
                            'new_avg_weight': current_leader['avg_weight'],
                        }
                        self.leadership_changes.append(change)
                        print_colored(f"Leader changed from {prev_leader['symbol']} to {current_leader['symbol']}", Colors.WARNING)

                self.identifier.print_leaders_summary(leaders, sector_name, top_n=1)
            except Exception as exc:
                logger.exception("Error analyzing %s: %s", sector_name, exc)
                print_colored(f"Error analyzing {sector_name}: {exc}", Colors.FAIL)

        self.db.save_analysis_run(
            sectors_analyzed=len(self.results),
            funds_analyzed=total_funds_analyzed,
            leaders_found=total_leaders_found,
            status='completed',
            notes='Tracked-fund production workflow',
        )
        return self.results

    def _find_sector_funds(self, keywords, sector_name):
        tracked = self.db.get_tracked_funds(sector_name)
        if tracked:
            return [fund['fund_symbol'] for fund in tracked]

        if self.analysis_config.get('allow_uninitialized_sector_fallback', False):
            logger.warning("Using curated manifest fallback for uninitialized sector %s", sector_name)
            return self.fetcher.search_funds_by_keywords(keywords, sector_name=sector_name)[: self.analysis_config.get('top_funds_per_sector', 5)]
        return []

    def _save_sector_results(self, sector_name, keywords, fund_symbols, holdings_by_fund, leaders):
        self.db.save_sector(sector_name, keywords)
        tracked_funds = {row['fund_symbol']: row for row in self.db.get_tracked_funds(sector_name)}

        for fund_symbol in fund_symbols:
            tracked_meta = tracked_funds.get(fund_symbol, {})
            self.db.save_fund(
                fund_symbol,
                tracked_meta.get('fund_name', fund_symbol),
                sector_name,
                performance_3year=tracked_meta.get('performance_3year'),
            )

        for fund_symbol, holdings in holdings_by_fund.items():
            for holding in holdings:
                self.db.save_holding(fund_symbol, holding['symbol'], holding['name'], holding['weight'])

        if leaders:
            top_leader = leaders[0]
            self.db.save_leader(
                sector_name,
                top_leader['symbol'],
                top_leader['name'],
                top_leader['times_held'],
                top_leader['total_weight'],
                top_leader['avg_weight'],
                prevalence=top_leader.get('prevalence'),
            )

    def export_results(self):
        if not self.results:
            print_colored("No results to export", Colors.WARNING)
            return
        output_config = self.config.get('output', {})
        if output_config.get('save_to_csv', True):
            self._export_to_csv(output_config.get('csv_path', 'output/leaders.csv'))
        if output_config.get('save_to_json', True):
            self._export_to_json(output_config.get('json_path', 'output/leaders.json'))
        print_colored("\nResults exported successfully!", Colors.OKGREEN)

    def _export_to_csv(self, filepath):
        import csv
        import os

        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Sector', 'Symbol', 'Company', 'Times Held', 'Avg Weight %', 'Prevalence %'])
            for sector_name, data in self.results.items():
                leader = data.get('top_leader')
                if leader:
                    writer.writerow([sector_name, leader['symbol'], leader['name'], leader['times_held'], f"{leader['avg_weight']:.2f}", f"{leader['prevalence']:.1f}"])

    def _export_to_json(self, filepath):
        import json
        import os

        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        export_data = {}
        for sector_name, data in self.results.items():
            export_data[sector_name] = {
                'funds_analyzed': data['funds'],
                'top_leader': data.get('top_leader'),
                'leaders_considered': data.get('leaders', []),
                'total_holdings_analyzed': data['holdings_count'],
            }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2)

    def get_summary(self):
        if not self.results:
            return None
        leaders_found = sum(1 for data in self.results.values() if data.get('top_leader'))
        return {
            'sectors_analyzed': len(self.results),
            'total_leaders': leaders_found,
            'sectors': list(self.results.keys()),
            'changes_detected': len(self.leadership_changes),
            'has_changes': bool(self.leadership_changes),
        }

    def get_leadership_changes(self):
        return self.leadership_changes
