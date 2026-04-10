import logging
from collections import defaultdict
from utils import Colors, print_colored, print_header

logger = logging.getLogger(__name__)


class LeaderIdentifier:
    def __init__(self, min_holding_threshold=1.0, min_funds_required=3):
        self.min_holding_threshold = min_holding_threshold
        self.min_funds_required = min_funds_required

    def analyze_holdings(self, holdings_by_fund, sector_name):
        logger.info('Analyzing holdings for sector: %s', sector_name)
        if not holdings_by_fund:
            logger.warning('No holdings data available for %s', sector_name)
            return []

        company_stats = defaultdict(lambda: {'times_held': 0, 'total_weight': 0.0, 'weights': [], 'name': None})
        total_funds = len(holdings_by_fund)

        for holdings in holdings_by_fund.values():
            for holding in holdings:
                symbol = holding.get('symbol')
                name = holding.get('name', 'Unknown')
                weight = holding.get('weight', 0)
                if not symbol or symbol in {'n/a', 'N/A', 'Unknown', 'UNKNOWN', '', None} or weight < self.min_holding_threshold:
                    continue
                company_stats[symbol]['times_held'] += 1
                company_stats[symbol]['total_weight'] += weight
                company_stats[symbol]['weights'].append(weight)
                if not company_stats[symbol]['name']:
                    company_stats[symbol]['name'] = name

        leaders = []
        for symbol, stats in company_stats.items():
            avg_weight = stats['total_weight'] / stats['times_held']
            if stats['times_held'] >= self.min_funds_required:
                leaders.append({
                    'symbol': symbol,
                    'name': stats['name'],
                    'times_held': stats['times_held'],
                    'total_weight': stats['total_weight'],
                    'avg_weight': avg_weight,
                    'prevalence': (stats['times_held'] / total_funds) * 100 if total_funds else 0,
                })

        leaders.sort(key=lambda x: (x['avg_weight'], x['prevalence'], x['times_held']), reverse=True)
        logger.info('Identified %s leaders in %s (held by >=%s funds)', len(leaders), sector_name, self.min_funds_required)
        return leaders

    def print_leaders_summary(self, leaders, sector_name, top_n=1):
        print_header(f'Top Leader in {sector_name}')
        if not leaders:
            print_colored('No leaders identified for this sector.', Colors.WARNING)
            return
        top_leader = leaders[0]
        print(f"{'Symbol':<10} {'Company':<35} {'Held By':<12} {'Avg Weight':<15} {'Prevalence'}")
        print('-' * 85)
        held_by = f"{top_leader['times_held']} funds"
        avg_weight = f"{top_leader['avg_weight']:.2f}%"
        prevalence = f"{top_leader['prevalence']:.1f}%"
        print(f"{top_leader['symbol'][:9]:<10} {top_leader['name'][:33]:<35} {held_by:<12} {avg_weight:<15} {prevalence}")
        print()
