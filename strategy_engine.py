from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional


@dataclass
class SectorDecision:
    sector: str
    action: str
    action_reason: str
    target_symbol: str
    target_name: str
    target_kind: str
    review_status: str
    candidate_symbol: Optional[str]
    candidate_name: Optional[str]
    candidate_score: Optional[float]
    candidate_prevalence: Optional[float]
    candidate_avg_weight: Optional[float]
    previous_symbol: Optional[str]
    previous_name: Optional[str]
    previous_kind: Optional[str]
    pending_symbol: Optional[str]
    pending_name: Optional[str]
    pending_confirmations: int
    confirmation_required: int
    significant_change: bool
    rebalance_due: bool
    data_status: str
    sector_freshness: Dict[str, Any]
    evidence: Dict[str, Any]

    def as_dict(self) -> Dict[str, Any]:
        return {
            'sector': self.sector,
            'action': self.action,
            'action_reason': self.action_reason,
            'target_symbol': self.target_symbol,
            'target_name': self.target_name,
            'target_kind': self.target_kind,
            'review_status': self.review_status,
            'candidate_symbol': self.candidate_symbol,
            'candidate_name': self.candidate_name,
            'candidate_score': self.candidate_score,
            'candidate_prevalence': self.candidate_prevalence,
            'candidate_avg_weight': self.candidate_avg_weight,
            'previous_symbol': self.previous_symbol,
            'previous_name': self.previous_name,
            'previous_kind': self.previous_kind,
            'pending_symbol': self.pending_symbol,
            'pending_name': self.pending_name,
            'pending_confirmations': self.pending_confirmations,
            'confirmation_required': self.confirmation_required,
            'significant_change': self.significant_change,
            'rebalance_due': self.rebalance_due,
            'data_status': self.data_status,
            'sector_freshness': self.sector_freshness,
            'evidence': self.evidence,
        }


class StrategyEngine:
    def __init__(self, strategy_config: Dict[str, Any]):
        self.config = strategy_config or {}
        self.confirmation_reviews = int(self.config.get('confirmation_reviews_required', 2))
        self.monthly_action_day = int(self.config.get('monthly_action_day', 1))
        self.min_prevalence = float(self.config.get('leader_rules', {}).get('min_prevalence_pct', 60.0))
        self.min_times_held = int(self.config.get('leader_rules', {}).get('min_times_held', 3))
        self.min_avg_weight = float(self.config.get('leader_rules', {}).get('min_avg_weight_pct', 1.0))
        self.significant_score_gap = float(self.config.get('significant_change', {}).get('score_gap_pct', 1.5))
        self.significant_prevalence_gap = float(self.config.get('significant_change', {}).get('prevalence_gap_pct', 20.0))
        self.allow_invalid_override = bool(self.config.get('significant_change', {}).get('allow_invalid_current_override', True))

    def evaluate_sector(
        self,
        sector_name: str,
        review_date: date,
        leaders: List[Dict[str, Any]],
        fallback: Dict[str, str],
        previous_state: Optional[Dict[str, Any]],
        data_status: str,
        sector_freshness: Optional[Dict[str, Any]] = None,
    ) -> SectorDecision:
        previous_state = previous_state or {}
        sector_freshness = sector_freshness or {}
        previous_symbol = previous_state.get('active_symbol')
        previous_name = previous_state.get('active_name')
        previous_kind = previous_state.get('active_kind')
        pending_symbol = previous_state.get('pending_symbol')
        pending_name = previous_state.get('pending_name')
        pending_confirmations = int(previous_state.get('pending_confirmations', 0) or 0)

        candidate = self._select_candidate(leaders)
        rebalance_due = review_date.day <= self.monthly_action_day
        fallback_symbol = fallback.get('symbol') or 'UNKNOWN'
        fallback_name = fallback.get('name') or fallback_symbol

        common = {
            'confirmation_required': self.confirmation_reviews,
            'data_status': data_status,
            'sector_freshness': sector_freshness,
        }

        if candidate is None:
            return SectorDecision(
                sector=sector_name,
                action='hold' if previous_symbol == fallback_symbol else 'switch',
                action_reason='No valid stock leader met the rules; use sector ETF fallback.',
                target_symbol=fallback_symbol,
                target_name=fallback_name,
                target_kind='sector_etf',
                review_status='fallback',
                candidate_symbol=None,
                candidate_name=None,
                candidate_score=None,
                candidate_prevalence=None,
                candidate_avg_weight=None,
                previous_symbol=previous_symbol,
                previous_name=previous_name,
                previous_kind=previous_kind,
                pending_symbol=None,
                pending_name=None,
                pending_confirmations=0,
                significant_change=self.allow_invalid_override and previous_kind == 'stock',
                rebalance_due=rebalance_due,
                evidence={'leaders_considered': leaders[:5], 'selected_mode': 'fallback'},
                **common,
            )

        candidate_symbol = candidate['symbol']
        candidate_name = candidate['name']
        candidate_score = round(float(candidate.get('avg_weight', 0.0)), 4)
        candidate_prevalence = round(float(candidate.get('prevalence', 0.0)), 2)
        candidate_avg_weight = round(float(candidate.get('avg_weight', 0.0)), 4)

        if previous_symbol is None:
            return SectorDecision(
                sector=sector_name,
                action='initiate',
                action_reason='No previous allocation recorded; establish the current confirmed leader.',
                target_symbol=candidate_symbol,
                target_name=candidate_name,
                target_kind='stock',
                review_status='active',
                candidate_symbol=candidate_symbol,
                candidate_name=candidate_name,
                candidate_score=candidate_score,
                candidate_prevalence=candidate_prevalence,
                candidate_avg_weight=candidate_avg_weight,
                previous_symbol=None,
                previous_name=None,
                previous_kind=None,
                pending_symbol=None,
                pending_name=None,
                pending_confirmations=0,
                significant_change=False,
                rebalance_due=True,
                evidence={'leaders_considered': leaders[:5], 'selected_mode': 'new_position'},
                **common,
            )

        if previous_symbol == candidate_symbol:
            return SectorDecision(
                sector=sector_name,
                action='hold',
                action_reason='Current active leader remains in force.',
                target_symbol=previous_symbol,
                target_name=previous_name or candidate_name,
                target_kind=previous_kind or 'stock',
                review_status='active',
                candidate_symbol=candidate_symbol,
                candidate_name=candidate_name,
                candidate_score=candidate_score,
                candidate_prevalence=candidate_prevalence,
                candidate_avg_weight=candidate_avg_weight,
                previous_symbol=previous_symbol,
                previous_name=previous_name,
                previous_kind=previous_kind,
                pending_symbol=None,
                pending_name=None,
                pending_confirmations=0,
                significant_change=False,
                rebalance_due=rebalance_due,
                evidence={'leaders_considered': leaders[:5], 'selected_mode': 'keep_active'},
                **common,
            )

        if pending_symbol == candidate_symbol:
            pending_confirmations += 1
        else:
            pending_symbol = candidate_symbol
            pending_name = candidate_name
            pending_confirmations = 1

        significant_change = self._is_significant_change(candidate, previous_state)
        confirmed = pending_confirmations >= self.confirmation_reviews
        can_switch = confirmed and (rebalance_due or significant_change)

        if can_switch:
            return SectorDecision(
                sector=sector_name,
                action='switch',
                action_reason='New leader was confirmed and switching window is open.',
                target_symbol=candidate_symbol,
                target_name=candidate_name,
                target_kind='stock',
                review_status='active',
                candidate_symbol=candidate_symbol,
                candidate_name=candidate_name,
                candidate_score=candidate_score,
                candidate_prevalence=candidate_prevalence,
                candidate_avg_weight=candidate_avg_weight,
                previous_symbol=previous_symbol,
                previous_name=previous_name,
                previous_kind=previous_kind,
                pending_symbol=None,
                pending_name=None,
                pending_confirmations=0,
                significant_change=significant_change,
                rebalance_due=rebalance_due,
                evidence={'leaders_considered': leaders[:5], 'selected_mode': 'confirmed_switch'},
                **common,
            )

        return SectorDecision(
            sector=sector_name,
            action='watch',
            action_reason='Candidate leader changed, but confirmation/monthly switch rules are not fully met yet.',
            target_symbol=previous_symbol,
            target_name=previous_name or previous_symbol,
            target_kind=previous_kind or 'stock',
            review_status='pending_confirmation',
            candidate_symbol=candidate_symbol,
            candidate_name=candidate_name,
            candidate_score=candidate_score,
            candidate_prevalence=candidate_prevalence,
            candidate_avg_weight=candidate_avg_weight,
            previous_symbol=previous_symbol,
            previous_name=previous_name,
            previous_kind=previous_kind,
            pending_symbol=pending_symbol,
            pending_name=pending_name,
            pending_confirmations=pending_confirmations,
            significant_change=significant_change,
            rebalance_due=rebalance_due,
            evidence={'leaders_considered': leaders[:5], 'selected_mode': 'pending_confirmation'},
            **common,
        )

    def build_portfolio_plan(self, sector_decisions: List[Any]) -> Dict[str, Any]:
        normalized = [d.as_dict() if hasattr(d, 'as_dict') else d for d in sector_decisions]
        actionable = [d for d in normalized if d['action'] in {'initiate', 'switch'}]
        target_weight = round(100 / len(normalized), 2) if normalized else 0.0
        trades = []
        for decision in normalized:
            if decision['action'] in {'initiate', 'switch'}:
                trades.append({
                    'sector': decision['sector'],
                    'trade': 'BUY',
                    'symbol': decision['target_symbol'],
                    'name': decision['target_name'],
                    'kind': decision['target_kind'],
                    'target_weight_pct': target_weight,
                    'reason': decision['action_reason'],
                })
                if decision.get('previous_symbol') and decision['previous_symbol'] != decision['target_symbol']:
                    trades.append({
                        'sector': decision['sector'],
                        'trade': 'SELL',
                        'symbol': decision['previous_symbol'],
                        'name': decision.get('previous_name') or decision['previous_symbol'],
                        'kind': decision.get('previous_kind') or 'stock',
                        'target_weight_pct': 0.0,
                        'reason': f"Replace with {decision['target_symbol']}",
                    })
        return {
            'target_weight_per_sector_pct': target_weight,
            'actionable_trades': trades,
            'actionable_sector_count': len(actionable),
        }

    def _select_candidate(self, leaders: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        for leader in leaders:
            if (
                float(leader.get('prevalence', 0.0)) >= self.min_prevalence
                and int(leader.get('times_held', 0)) >= self.min_times_held
                and float(leader.get('avg_weight', 0.0)) >= self.min_avg_weight
            ):
                return leader
        return None

    def _is_significant_change(self, candidate: Dict[str, Any], previous_state: Dict[str, Any]) -> bool:
        prev_score = float(previous_state.get('active_avg_weight', 0.0) or 0.0)
        prev_prevalence = float(previous_state.get('active_prevalence', 0.0) or 0.0)
        candidate_score = float(candidate.get('avg_weight', 0.0) or 0.0)
        candidate_prevalence = float(candidate.get('prevalence', 0.0) or 0.0)
        return (candidate_score - prev_score) >= self.significant_score_gap or (candidate_prevalence - prev_prevalence) >= self.significant_prevalence_gap


def parse_review_date(value: Optional[str]) -> date:
    if not value:
        return datetime.now().date()
    return datetime.strptime(value, '%Y-%m-%d').date()
