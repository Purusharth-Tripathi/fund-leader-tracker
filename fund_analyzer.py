"""
Fund Analyzer - Core analysis engine for Fund Leader Tracker
Coordinates the analysis workflow across sectors
"""
import logging
from holdings_fetcher import HoldingsFetcher
from leader_identifier import LeaderIdentifier
from db_manager import DatabaseManager
from utils import print_header, print_colored, Colors, print_progress

logger = logging.getLogger(__name__)


class FundAnalyzer:
    """Main analyzer that coordinates the fund analysis workflow"""

    def __init__(self, config, api_key):
        """
        Initialize the Fund Analyzer

        Args:
            config: Configuration dictionary
            api_key: Alpha Vantage API key
        """
        self.config = config
        self.api_key = api_key
        self.sectors = config.get('sectors', [])
        self.analysis_config = config.get('analysis', {})

        # Initialize components
        api_config = config.get('api', {})
        self.fetcher = HoldingsFetcher(
            api_key=api_key,
            requests_per_minute=api_config.get('requests_per_minute', 5),
            verify_ssl=False  # For corporate environments
        )

        self.identifier = LeaderIdentifier(
            min_holding_threshold=self.analysis_config.get('min_holding_threshold', 1.0)
        )

        db_path = config.get('output', {}).get('database_path', 'data/fund_leaders.db')
        self.db = DatabaseManager(db_path)

        self.results = {}
        self.leadership_changes = []

    def analyze_all_sectors(self):
        """
        Run analysis for all configured sectors

        Returns:
            dict: Analysis results for all sectors
        """
        print_header("Fund Leader Tracker - Starting Analysis")
        print_colored(f"Analyzing {len(self.sectors)} sectors...\n", Colors.OKBLUE)

        # Get previous leaders for change detection
        previous_leaders = self.db.get_latest_leaders_by_sector()
        if previous_leaders:
            logger.info(f"Retrieved {len(previous_leaders)} previous leaders for comparison")

        total_sectors = len(self.sectors)
        total_funds_analyzed = 0
        total_leaders_found = 0

        for i, sector_config in enumerate(self.sectors, 1):
            sector_name = sector_config['name']
            keywords = sector_config['keywords']

            print_colored(f"\n[{i}/{total_sectors}] Analyzing: {sector_name}", Colors.HEADER)
            print(f"Keywords: {', '.join(keywords)}")

            try:
                # Step 1: Find relevant funds
                fund_symbols = self._find_sector_funds(keywords)
                if not fund_symbols:
                    print_colored(f"No funds found for {sector_name}", Colors.WARNING)
                    continue

                print(f"Found {len(fund_symbols)} funds: {', '.join(fund_symbols)}")
                total_funds_analyzed += len(fund_symbols)

                # Step 2: Fetch holdings for each fund
                holdings_by_fund = self.fetcher.batch_fetch_holdings(fund_symbols)

                if not holdings_by_fund:
                    print_colored(f"No holdings data retrieved for {sector_name}", Colors.WARNING)
                    continue

                # Step 3: Identify leaders
                leaders = self.identifier.analyze_holdings(holdings_by_fund, sector_name)
                total_leaders_found += len(leaders)

                # Step 4: Save to database (only top leader)
                self._save_sector_results(sector_name, keywords, fund_symbols, holdings_by_fund, leaders)

                # Step 5: Store results (only top 1 leader)
                current_leader = leaders[0] if leaders else None
                self.results[sector_name] = {
                    'funds': fund_symbols,
                    'top_leader': current_leader,
                    'holdings_count': sum(len(h) for h in holdings_by_fund.values())
                }

                # Step 6: Detect leadership changes
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
                            'new_avg_weight': current_leader['avg_weight']
                        }
                        self.leadership_changes.append(change)
                        logger.info(f"Leadership change detected in {sector_name}: {prev_leader['symbol']} -> {current_leader['symbol']}")
                        print_colored(f"  [CHANGE] Leader changed from {prev_leader['symbol']} to {current_leader['symbol']}", Colors.WARNING)

                # Display results (only #1 leader)
                self.identifier.print_leaders_summary(leaders, sector_name, top_n=1)

            except Exception as e:
                logger.error(f"Error analyzing {sector_name}: {e}")
                print_colored(f"Error analyzing {sector_name}: {str(e)}", Colors.FAIL)
                continue

        # Save analysis run metadata
        self.db.save_analysis_run(
            sectors_analyzed=len(self.results),
            funds_analyzed=total_funds_analyzed,
            leaders_found=total_leaders_found,
            status='completed',
            notes=f"Analyzed {total_sectors} sectors"
        )

        print_header("Analysis Complete")
        print_colored(f"Total sectors analyzed: {len(self.results)}", Colors.OKGREEN)
        print_colored(f"Total funds analyzed: {total_funds_analyzed}", Colors.OKGREEN)
        print_colored(f"Total leaders identified: {total_leaders_found}", Colors.OKGREEN)

        # Display leadership changes summary
        if self.leadership_changes:
            print_header("Leadership Changes Detected")
            print_colored(f"{len(self.leadership_changes)} leadership change(s) detected:\n", Colors.WARNING)
            for change in self.leadership_changes:
                print(f"  {change['sector']}:")
                print(f"    Old Leader: {change['old_symbol']} ({change['old_name']})")
                print(f"    New Leader: {change['new_symbol']} ({change['new_name']})")
                print()
        else:
            print_colored("\nNo leadership changes detected.", Colors.OKGREEN)

        return self.results

    def _find_sector_funds(self, keywords):
        """
        Find funds for a specific sector based on keywords

        Args:
            keywords: List of sector keywords

        Returns:
            list: List of fund symbols
        """
        top_n = self.analysis_config.get('top_funds_per_sector', 5)
        fund_symbols = self.fetcher.search_funds_by_keywords(keywords)
        return fund_symbols[:top_n]

    def _save_sector_results(self, sector_name, keywords, fund_symbols, holdings_by_fund, leaders):
        """
        Save sector analysis results to database

        Args:
            sector_name: Name of the sector
            keywords: Sector keywords
            fund_symbols: List of fund symbols analyzed
            holdings_by_fund: Holdings data
            leaders: Identified leaders
        """
        try:
            # Save sector
            self.db.save_sector(sector_name, keywords)

            # Save funds
            for fund_symbol in fund_symbols:
                self.db.save_fund(fund_symbol, fund_symbol, sector_name)

            # Save holdings
            for fund_symbol, holdings in holdings_by_fund.items():
                for holding in holdings:
                    self.db.save_holding(
                        fund_symbol,
                        holding['symbol'],
                        holding['name'],
                        holding['weight']
                    )

            # Save ONLY the #1 leader
            if leaders:
                top_leader = leaders[0]
                self.db.save_leader(
                    sector_name,
                    top_leader['symbol'],
                    top_leader['name'],
                    top_leader['times_held'],
                    top_leader['total_weight'],
                    top_leader['avg_weight']
                )

            logger.info(f"Saved top leader for {sector_name} to database")

        except Exception as e:
            logger.error(f"Error saving results for {sector_name}: {e}")

    def export_results(self):
        """Export analysis results to CSV and JSON"""
        output_config = self.config.get('output', {})

        if not self.results:
            print_colored("No results to export", Colors.WARNING)
            return

        try:
            # Export to CSV
            if output_config.get('save_to_csv', True):
                self._export_to_csv(output_config.get('csv_path', 'output/leaders.csv'))

            # Export to JSON
            if output_config.get('save_to_json', True):
                self._export_to_json(output_config.get('json_path', 'output/leaders.json'))

            print_colored("\nResults exported successfully!", Colors.OKGREEN)

        except Exception as e:
            logger.error(f"Error exporting results: {e}")
            print_colored(f"Error exporting results: {str(e)}", Colors.FAIL)

    def _export_to_csv(self, filepath):
        """Export results to CSV file - ONE leader per sector"""
        import csv
        import os

        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Sector', 'Symbol', 'Company', 'Times Held', 'Avg Weight %', 'Prevalence %'])

            for sector_name, data in self.results.items():
                leader = data.get('top_leader')
                if leader:
                    writer.writerow([
                        sector_name,
                        leader['symbol'],
                        leader['name'],
                        leader['times_held'],
                        f"{leader['avg_weight']:.2f}",
                        f"{leader['prevalence']:.1f}"
                    ])

        print(f"CSV exported to: {filepath}")

    def _export_to_json(self, filepath):
        """Export results to JSON file - ONE leader per sector"""
        import json
        import os

        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        export_data = {}
        for sector_name, data in self.results.items():
            export_data[sector_name] = {
                'funds_analyzed': data['funds'],
                'top_leader': data.get('top_leader'),
                'total_holdings_analyzed': data['holdings_count']
            }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2)

        print(f"JSON exported to: {filepath}")

    def get_summary(self):
        """
        Get a summary of the analysis

        Returns:
            dict: Summary statistics
        """
        if not self.results:
            return None

        leaders_found = sum(1 for data in self.results.values() if data.get('top_leader'))

        return {
            'sectors_analyzed': len(self.results),
            'total_leaders': leaders_found,  # One per sector
            'sectors': list(self.results.keys()),
            'changes_detected': len(self.leadership_changes),
            'has_changes': len(self.leadership_changes) > 0
        }

    def get_leadership_changes(self):
        """
        Get detected leadership changes

        Returns:
            list: List of leadership changes
        """
        return self.leadership_changes
