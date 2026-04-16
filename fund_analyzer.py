"""Core analysis engine for Fund Leader Tracker."""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from data_providers import (
    AlphaVantageBudgetLedger,
    WORKFLOW_REFRESH,
    WORKFLOW_REVIEW,
)
from db_manager import DatabaseManager
from holdings_fetcher import HoldingsFetcher
from leader_identifier import LeaderIdentifier
from manual_report import export_manual_report
from strategy_engine import StrategyEngine
from utils import Colors, print_colored, print_header

logger = logging.getLogger(__name__)


class FundAnalyzer:
    def __init__(self, config, api_key, review_date=None, workflow: str = WORKFLOW_REVIEW):
        self.config = config
        self.api_key = api_key
        self.workflow = workflow
        self.sectors = config.get('sectors', [])
        self.analysis_config = config.get('analysis', {})
        self.strategy_config = config.get('strategy', {})
        self.refresh_config = config.get('refresh', {})
        self.review_date = review_date or datetime.now().date()

        api_config = config.get('api', {})
        db_path = config.get('output', {}).get('database_path', 'data/fund_leaders.db')
        self.db = DatabaseManager(db_path)

        # Only refresh is permitted to issue live Alpha Vantage holdings calls.
        # Review and everything else must stay within cache, regardless of
        # provider order or caller arguments.
        live_calls_allowed = workflow == WORKFLOW_REFRESH
        api_key_present = bool(api_key and api_key != 'your_api_key_here')
        self.ledger = AlphaVantageBudgetLedger(
            db=self.db,
            workflow=workflow,
            daily_budget=api_config.get('requests_per_day', 25),
            live_calls_allowed=live_calls_allowed,
            api_key_present=api_key_present,
        )

        self.fetcher = HoldingsFetcher(
            api_key=api_key,
            requests_per_minute=api_config.get('requests_per_minute', 5),
            verify_ssl=api_config.get('verify_ssl', True),
            retry_attempts=api_config.get('retry_attempts', 3),
            retry_delay=api_config.get('retry_delay', 5),
            cache_directory=api_config.get('cache_directory', 'data/cache'),
            cache_ttl_hours=api_config.get('holdings_cache_ttl_hours', 168),
            holdings_provider_order=api_config.get('holdings_provider_order'),
            ledger=self.ledger,
        )
        self.identifier = LeaderIdentifier(
            min_holding_threshold=self.analysis_config.get('min_holding_threshold', 1.0),
            min_funds_required=self.strategy_config.get('leader_rules', {}).get('min_times_held', 3),
        )
        self.strategy_engine = StrategyEngine(self.strategy_config)
        self.results: Dict[str, Dict[str, Any]] = {}
        self.sector_decisions: List[Dict[str, Any]] = []
        self.report_paths: Dict[str, str] = {}

    def refresh_holdings_snapshots(self, batch_name: Optional[str] = None):
        print_header('ETF Holdings Snapshot Refresh')
        selected = self._resolve_refresh_batch(batch_name=batch_name)
        if not selected:
            print_colored('No sectors selected for refresh.', Colors.WARNING)
            return {'batch': None, 'sectors': []}

        refreshed = []
        for index, sector_config in enumerate(selected, 1):
            sector_name = sector_config['name']
            keywords = sector_config.get('keywords', [])
            try:
                print_colored(f'\n[{index}/{len(selected)}] Refreshing: {sector_name}', Colors.HEADER)
                fund_rows = self.db.get_tracked_funds(sector_name)
                fund_symbols = [fund['fund_symbol'] for fund in fund_rows]
                if not fund_symbols and self.analysis_config.get('allow_uninitialized_sector_fallback', False):
                    fund_symbols = self.fetcher.search_funds_by_keywords(keywords, sector_name=sector_name)[: self.analysis_config.get('top_funds_per_sector', 5)]
                if not fund_symbols:
                    print_colored(f'No tracked funds found for {sector_name}', Colors.WARNING)
                    refreshed.append({'sector': sector_name, 'refreshed_funds': 0, 'status': 'no_tracked_funds'})
                    continue

                print(f"Tracked ETFs: {', '.join(fund_symbols)}")
                holdings_by_fund, holding_status = self.fetcher.batch_fetch_holdings(fund_symbols, mode='auto')
                self._save_sector_results(sector_name, keywords, fund_rows, holdings_by_fund, leaders=[])
                quota_exhausted = self.fetcher.alpha_vantage_quota_exhausted
                refreshed.append({
                    'sector': sector_name,
                    'refreshed_funds': len(holding_status),
                    'requested_funds': len(fund_symbols),
                    'live_fetches': sum(1 for meta in holding_status.values() if meta.get('data_status') == 'live'),
                    'etf_freshness': holding_status,
                    'sector_freshness': self._summarize_sector_freshness(holding_status),
                    'status': 'partial_quota_stop' if quota_exhausted else 'ok',
                    'quota_exhausted': quota_exhausted,
                    'quota_note': self.fetcher.last_rate_limit_note,
                })
                if quota_exhausted:
                    print_colored('Alpha Vantage quota exhausted. Stopping refresh early to preserve the remaining batch for after reset.', Colors.WARNING)
                    break
            except Exception as exc:
                logger.exception('Error refreshing %s: %s', sector_name, exc)
                print_colored(f'Error refreshing {sector_name}: {exc}', Colors.FAIL)
                refreshed.append({'sector': sector_name, 'refreshed_funds': 0, 'status': 'error', 'error': str(exc)})

        return {
            'batch': self._resolve_refresh_batch_name(batch_name),
            'review_date': self.review_date.isoformat(),
            'workflow': self.workflow,
            'sectors': refreshed,
            'api_budget': {
                'requests_per_day': self.config.get('api', {}).get('requests_per_day', 25),
                'tracked_etfs_per_sector': self.analysis_config.get('top_funds_per_sector', 5),
            },
            'alpha_vantage_usage': self.ledger.run_summary(),
        }

    def analyze_all_sectors(self, fetch_mode: str = 'cache_only'):
        # Review workflow is contractually cache-only. Force the mode here so
        # no caller or misconfigured provider_order can escalate a review run
        # into a live Alpha Vantage burst.
        if self.workflow == WORKFLOW_REVIEW and fetch_mode != 'cache_only':
            logger.info('Review workflow forces fetch_mode=cache_only (was %s)', fetch_mode)
            fetch_mode = 'cache_only'
        print_header('ETF Sector Leadership Review')
        total_funds_analyzed = 0
        total_leaders_found = 0

        for index, sector_config in enumerate(self.sectors, 1):
            sector_name = sector_config['name']
            keywords = sector_config.get('keywords', [])
            try:
                print_colored(f'\n[{index}/{len(self.sectors)}] Reviewing: {sector_name}', Colors.HEADER)
                fund_rows = self.db.get_tracked_funds(sector_name)
                fund_symbols = [fund['fund_symbol'] for fund in fund_rows]
                if not fund_symbols and self.analysis_config.get('allow_uninitialized_sector_fallback', False):
                    fund_symbols = self.fetcher.search_funds_by_keywords(keywords, sector_name=sector_name)[: self.analysis_config.get('top_funds_per_sector', 5)]
                if not fund_symbols:
                    print_colored(f'No tracked funds found for {sector_name}', Colors.WARNING)
                    continue

                print(f"Tracked ETFs: {', '.join(fund_symbols)}")
                holdings_by_fund, holding_status = self.fetcher.batch_fetch_holdings(fund_symbols, mode=fetch_mode)
                leaders = self.identifier.analyze_holdings(holdings_by_fund, sector_name) if holdings_by_fund else []
                fallback = self._resolve_sector_fallback(sector_config, fund_rows, fund_symbols)
                previous_state = self.db.get_latest_strategy_state(sector_name)
                sector_freshness = self._summarize_sector_freshness(holding_status)
                decision = self.strategy_engine.evaluate_sector(
                    sector_name=sector_name,
                    review_date=self.review_date,
                    leaders=leaders,
                    fallback=fallback,
                    previous_state=previous_state,
                    data_status=sector_freshness['data_status'],
                    sector_freshness=sector_freshness,
                )
                decision.evidence['etf_freshness'] = holding_status
                decision.evidence['fetch_mode'] = fetch_mode

                total_funds_analyzed += len(fund_symbols)
                total_leaders_found += len(leaders)
                self._save_sector_results(sector_name, keywords, fund_rows, holdings_by_fund, leaders)
                self.db.save_sector_strategy_state(decision.as_dict(), self.review_date.isoformat())
                self.sector_decisions.append(decision.as_dict())
                self.results[sector_name] = {
                    'funds': fund_symbols,
                    'top_leader': leaders[0] if leaders else None,
                    'leaders': leaders[: self.analysis_config.get('export_top_n_leaders', 10)],
                    'decision': decision.as_dict(),
                    'holdings_count': sum(len(h) for h in holdings_by_fund.values()),
                    'etf_freshness': holding_status,
                    'sector_freshness': sector_freshness,
                }
                self.identifier.print_leaders_summary(leaders, sector_name, top_n=1)
                print(
                    f"Recommendation: {decision.target_symbol} ({decision.target_kind}) | action={decision.action} | "
                    f"status={decision.review_status} | freshness={sector_freshness['freshness']}"
                )
            except Exception as exc:
                logger.exception('Error analyzing %s: %s', sector_name, exc)
                print_colored(f'Error analyzing {sector_name}: {exc}', Colors.FAIL)

        self.db.save_analysis_run(
            sectors_analyzed=len(self.results),
            funds_analyzed=total_funds_analyzed,
            leaders_found=total_leaders_found,
            status='completed',
            notes=f'ETF-only sector leadership strategy review ({fetch_mode})',
        )
        return self.results

    def _resolve_sector_fallback(self, sector_config, fund_rows, fund_symbols):
        strategy_fallbacks = self.strategy_config.get('sector_fallbacks', {})
        explicit = strategy_fallbacks.get(sector_config['name']) if isinstance(strategy_fallbacks, dict) else None
        if explicit:
            return explicit
        if fund_rows:
            top = fund_rows[0]
            return {'symbol': top['fund_symbol'], 'name': top.get('fund_name') or top['fund_symbol']}
        if fund_symbols:
            return {'symbol': fund_symbols[0], 'name': fund_symbols[0]}
        return {'symbol': 'CASH', 'name': 'Cash / no allocation'}

    def _summarize_sector_freshness(self, holding_status):
        statuses = [meta.get('data_status') for meta in holding_status.values() if meta]
        freshness_values = [meta.get('freshness') for meta in holding_status.values() if meta]
        ages = [meta.get('age_hours') for meta in holding_status.values() if meta.get('age_hours') is not None]
        if not statuses:
            return {
                'data_status': 'unavailable',
                'freshness': 'unknown',
                'coverage_ratio': '0/0',
                'avg_age_hours': None,
                'stale_etfs': 0,
                'live_etfs': 0,
                'cache_miss_etfs': 0,
            }

        if any(status == 'cache_miss' for status in statuses):
            aggregate_status = 'cache_miss'
        elif any(status == 'stale_cache' for status in statuses):
            aggregate_status = 'stale_cache'
        elif all(status == 'fresh_cache' for status in statuses):
            aggregate_status = 'fresh_cache'
        elif any(status == 'live' for status in statuses):
            aggregate_status = 'live_or_mixed'
        else:
            aggregate_status = statuses[0]

        if 'very_stale' in freshness_values:
            freshness = 'very_stale'
        elif 'stale' in freshness_values:
            freshness = 'stale'
        elif all(value == 'fresh' for value in freshness_values if value):
            freshness = 'fresh'
        else:
            freshness = 'mixed'

        return {
            'data_status': aggregate_status,
            'freshness': freshness,
            'coverage_ratio': f"{sum(1 for meta in holding_status.values() if meta.get('holdings_count', 0) > 0)}/{len(holding_status)}",
            'avg_age_hours': round(sum(ages) / len(ages), 2) if ages else None,
            'stale_etfs': sum(1 for meta in holding_status.values() if meta.get('freshness') in {'stale', 'very_stale'}),
            'live_etfs': sum(1 for meta in holding_status.values() if meta.get('data_status') == 'live'),
            'cache_miss_etfs': sum(1 for meta in holding_status.values() if meta.get('data_status') == 'cache_miss'),
        }

    def _resolve_refresh_batch_name(self, batch_name: Optional[str] = None) -> str:
        if batch_name:
            return batch_name.strip().lower()
        day_index = self.review_date.toordinal() % 2
        return 'batch_a' if day_index == 0 else 'batch_b'

    def _resolve_refresh_batch(self, batch_name: Optional[str] = None):
        batches = self.refresh_config.get('sector_batches', {})
        normalized = self._resolve_refresh_batch_name(batch_name)
        sector_names = batches.get(normalized)
        if sector_names:
            order = {name: idx for idx, name in enumerate(sector_names)}
            selected = [sector for sector in self.sectors if sector['name'] in order]
            return sorted(selected, key=lambda sector: order[sector['name']])

        midpoint = len(self.sectors) // 2
        return self.sectors[:midpoint] if normalized == 'batch_a' else self.sectors[midpoint:]

    def _save_sector_results(self, sector_name, keywords, fund_rows, holdings_by_fund, leaders):
        self.db.save_sector(sector_name, keywords)
        tracked_funds = {row['fund_symbol']: row for row in fund_rows}
        for fund_symbol in holdings_by_fund.keys():
            tracked_meta = tracked_funds.get(fund_symbol, {})
            self.db.save_fund(
                fund_symbol,
                tracked_meta.get('fund_name', fund_symbol),
                sector_name,
                performance_3year=tracked_meta.get('performance_3year'),
            )
            self.db.delete_holdings_for_fund(fund_symbol)
            for holding in holdings_by_fund[fund_symbol]:
                self.db.save_holding(fund_symbol, holding['symbol'], holding['name'], holding['weight'])

        if leaders:
            top = leaders[0]
            self.db.save_leader(
                sector_name,
                top['symbol'],
                top['name'],
                top['times_held'],
                top['total_weight'],
                top['avg_weight'],
                prevalence=top.get('prevalence'),
            )

    def export_results(self):
        if not self.results:
            print_colored('No results to export', Colors.WARNING)
            return
        output_config = self.config.get('output', {})
        if output_config.get('save_to_csv', True):
            self._export_to_csv(output_config.get('csv_path', 'output/leaders.csv'))
        if output_config.get('save_to_json', True):
            self._export_to_json(output_config.get('json_path', 'output/leaders.json'))
        payload = self.build_run_payload()
        self.report_paths = export_manual_report(payload, output_config)
        self.db.save_strategy_run(self.review_date.isoformat(), payload['run_timestamp'], payload['summary'], payload['portfolio_plan'], self.report_paths)
        print_colored('\nResults and manual report exported successfully!', Colors.OKGREEN)

    def _export_to_csv(self, filepath):
        import csv
        import os

        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Sector', 'Top Leader', 'Leader Name', 'Recommendation', 'Recommendation Type', 'Action', 'Status', 'Sector Freshness', 'Data Status'])
            for sector_name, data in self.results.items():
                leader = data.get('top_leader') or {}
                decision = data.get('decision') or {}
                sector_freshness = data.get('sector_freshness') or {}
                writer.writerow([
                    sector_name,
                    leader.get('symbol'),
                    leader.get('name'),
                    decision.get('target_symbol'),
                    decision.get('target_kind'),
                    decision.get('action'),
                    decision.get('review_status'),
                    sector_freshness.get('freshness'),
                    sector_freshness.get('data_status'),
                ])

    def _export_to_json(self, filepath):
        import json
        import os

        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.build_run_payload(), f, indent=2)

    def build_run_payload(self):
        summary = self.get_summary()
        portfolio_plan = self.strategy_engine.build_portfolio_plan(self.sector_decisions)
        return {
            'run_timestamp': datetime.now().isoformat(),
            'review_date': self.review_date.isoformat(),
            'workflow': self.workflow,
            'alpha_vantage_usage': self.ledger.run_summary(),
            'summary': summary,
            'portfolio_plan': portfolio_plan,
            'sectors': self.sector_decisions,
            'results': self.results,
            'report_paths': self.report_paths,
        }

    def get_summary(self):
        leaders_found = sum(1 for data in self.results.values() if data.get('top_leader'))
        stale_sectors = sum(1 for data in self.results.values() if (data.get('sector_freshness') or {}).get('freshness') in {'stale', 'very_stale'})
        cache_miss_sectors = sum(1 for data in self.results.values() if (data.get('sector_freshness') or {}).get('data_status') == 'cache_miss')
        return {
            'sectors_analyzed': len(self.results),
            'total_leaders': leaders_found,
            'recommendations_generated': len(self.sector_decisions),
            'switches': sum(1 for d in self.sector_decisions if d.get('action') == 'switch'),
            'fallbacks': sum(1 for d in self.sector_decisions if d.get('target_kind') == 'sector_etf'),
            'stale_sectors': stale_sectors,
            'cache_miss_sectors': cache_miss_sectors,
        }

    def get_leadership_changes(self):
        return [
            d for d in self.sector_decisions
            if d.get('action') in {'switch', 'watch'} and d.get('candidate_symbol') and d.get('candidate_symbol') != d.get('previous_symbol')
        ]
