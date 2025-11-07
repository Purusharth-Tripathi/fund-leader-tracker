"""
Leader Identifier for Fund Leader Tracker
Analyzes fund holdings to identify industry leaders
"""
import logging
from collections import defaultdict
from utils import print_header, print_colored, Colors

logger = logging.getLogger(__name__)


class LeaderIdentifier:
    """Identifies industry leaders based on fund holdings"""

    def __init__(self, min_holding_threshold=1.0):
        """
        Initialize the Leader Identifier

        Args:
            min_holding_threshold: Minimum portfolio weight % to consider
        """
        self.min_holding_threshold = min_holding_threshold

    def analyze_holdings(self, holdings_by_fund, sector_name):
        """
        Analyze holdings across multiple funds to identify leaders

        Args:
            holdings_by_fund: Dict mapping fund symbols to list of holdings
            sector_name: Name of the sector being analyzed

        Returns:
            list: List of leader companies sorted by prominence
        """
        logger.info(f"Analyzing holdings for sector: {sector_name}")

        if not holdings_by_fund:
            logger.warning(f"No holdings data available for {sector_name}")
            return []

        # Aggregate holdings across all funds
        company_stats = defaultdict(lambda: {
            'times_held': 0,
            'total_weight': 0.0,
            'weights': [],
            'name': None
        })

        total_funds = len(holdings_by_fund)

        for fund_symbol, holdings in holdings_by_fund.items():
            if not holdings:
                continue

            for holding in holdings:
                symbol = holding.get('symbol')
                name = holding.get('name', 'Unknown')
                weight = holding.get('weight', 0)

                # Filter out invalid or placeholder symbols
                invalid_symbols = ['n/a', 'N/A', 'Unknown', 'UNKNOWN', '', None]
                if not symbol or symbol in invalid_symbols or weight < self.min_holding_threshold:
                    continue

                company_stats[symbol]['times_held'] += 1
                company_stats[symbol]['total_weight'] += weight
                company_stats[symbol]['weights'].append(weight)
                if not company_stats[symbol]['name']:
                    company_stats[symbol]['name'] = name

        # Calculate average weights and create leader list
        # NEW CRITERIA: Stock must be held by at least 3 funds (60% minimum consensus)
        min_funds_required = 3

        leaders = []
        for symbol, stats in company_stats.items():
            avg_weight = stats['total_weight'] / stats['times_held']

            # Only include stocks held by at least 3 funds
            if stats['times_held'] >= min_funds_required:
                leaders.append({
                    'symbol': symbol,
                    'name': stats['name'],
                    'times_held': stats['times_held'],
                    'total_weight': stats['total_weight'],
                    'avg_weight': avg_weight,
                    'prevalence': (stats['times_held'] / total_funds) * 100
                })

        # Sort by average weight (descending) - highest conviction wins
        # Stocks already filtered to have at least 3 funds holding them
        leaders.sort(key=lambda x: x['avg_weight'], reverse=True)

        logger.info(f"Identified {len(leaders)} leaders in {sector_name} (held by >=3 funds)")
        return leaders

    def get_top_leaders(self, leaders, n=10):
        """
        Get top N leaders from the analysis

        Args:
            leaders: List of leader dictionaries
            n: Number of top leaders to return

        Returns:
            list: Top N leaders
        """
        return leaders[:n]

    def filter_by_prevalence(self, leaders, min_prevalence=40.0):
        """
        Filter leaders by how prevalent they are across funds

        Args:
            leaders: List of leader dictionaries
            min_prevalence: Minimum % of funds that must hold the stock

        Returns:
            list: Filtered list of leaders
        """
        filtered = [
            leader for leader in leaders
            if leader['prevalence'] >= min_prevalence
        ]
        logger.info(f"Filtered to {len(filtered)} leaders with >{min_prevalence}% prevalence")
        return filtered

    def print_leaders_summary(self, leaders, sector_name, top_n=1):
        """
        Print a formatted summary of industry leaders

        Args:
            leaders: List of leader dictionaries
            sector_name: Name of the sector
            top_n: Number of top leaders to display (default: 1 - THE top leader)
        """
        print_header(f"Top Leader in {sector_name}")

        if not leaders:
            try:
                print_colored("No leaders identified for this sector.", Colors.WARNING)
            except (UnicodeEncodeError, UnicodeDecodeError):
                print("No leaders identified for this sector.")
            return

        # Get only the #1 leader
        top_leader = leaders[0]

        print(f"{'Symbol':<10} {'Company':<35} {'Held By':<12} {'Avg Weight':<15} {'Prevalence'}")
        print("-" * 85)

        symbol = top_leader['symbol'][:9]
        name = top_leader['name'][:33] if top_leader['name'] else 'N/A'
        times_held = f"{top_leader['times_held']}/5 funds"
        avg_weight = f"{top_leader['avg_weight']:.2f}%"
        prevalence = f"{top_leader['prevalence']:.1f}%"

        print(f"{symbol:<10} {name:<35} {times_held:<12} {avg_weight:<15} {prevalence}")
        print()

    def compare_with_previous(self, current_leaders, previous_leaders):
        """
        Compare current leaders with previous analysis to detect changes

        Args:
            current_leaders: Current list of leaders
            previous_leaders: Previous list of leaders

        Returns:
            dict: Changes detected (new, removed, moved_up, moved_down)
        """
        if not previous_leaders:
            return {'new': current_leaders, 'removed': [], 'moved_up': [], 'moved_down': []}

        current_symbols = {l['symbol'] for l in current_leaders[:10]}
        previous_symbols = {l['symbol'] for l in previous_leaders[:10]}

        new = current_symbols - previous_symbols
        removed = previous_symbols - current_symbols

        # Track rank changes
        current_ranks = {l['symbol']: i for i, l in enumerate(current_leaders[:10])}
        previous_ranks = {l['symbol']: i for i, l in enumerate(previous_leaders[:10])}

        moved_up = []
        moved_down = []

        for symbol in current_symbols & previous_symbols:
            current_rank = current_ranks[symbol]
            previous_rank = previous_ranks[symbol]

            if current_rank < previous_rank:
                moved_up.append({
                    'symbol': symbol,
                    'from': previous_rank + 1,
                    'to': current_rank + 1
                })
            elif current_rank > previous_rank:
                moved_down.append({
                    'symbol': symbol,
                    'from': previous_rank + 1,
                    'to': current_rank + 1
                })

        return {
            'new': [l for l in current_leaders if l['symbol'] in new],
            'removed': [l for l in previous_leaders if l['symbol'] in removed],
            'moved_up': moved_up,
            'moved_down': moved_down
        }

    def generate_sector_report(self, leaders, sector_name):
        """
        Generate a detailed report for a sector

        Args:
            leaders: List of leader dictionaries
            sector_name: Name of the sector

        Returns:
            dict: Sector report
        """
        if not leaders:
            return {
                'sector': sector_name,
                'total_leaders': 0,
                'top_10': [],
                'summary': f"No leaders identified in {sector_name}"
            }

        top_10 = self.get_top_leaders(leaders, 10)

        return {
            'sector': sector_name,
            'total_leaders': len(leaders),
            'top_10': top_10,
            'avg_prevalence': sum(l['prevalence'] for l in top_10) / len(top_10),
            'most_prevalent': max(leaders, key=lambda x: x['prevalence']),
            'highest_weight': max(leaders, key=lambda x: x['avg_weight']),
            'summary': f"Identified {len(leaders)} leaders with top pick being {top_10[0]['symbol']}"
        }
