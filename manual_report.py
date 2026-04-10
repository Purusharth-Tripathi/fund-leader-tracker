from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, List


def render_manual_report(run_payload: Dict[str, Any]) -> str:
    lines: List[str] = []
    summary = run_payload.get('summary', {})
    portfolio = run_payload.get('portfolio_plan', {})
    lines.append('ETF SECTOR LEADERSHIP MANUAL REVIEW')
    lines.append('=' * 40)
    lines.append(f"Run timestamp: {run_payload.get('run_timestamp')}")
    lines.append(f"Review date: {run_payload.get('review_date')}")
    lines.append(f"Sectors reviewed: {summary.get('sectors_analyzed', 0)}")
    lines.append(f"Actionable sectors: {portfolio.get('actionable_sector_count', 0)}")
    lines.append(f"Target sector weight: {portfolio.get('target_weight_per_sector_pct', 0)}%")
    lines.append('')

    for sector in run_payload.get('sectors', []):
        lines.append(f"[{sector['sector']}]")
        lines.append(f"Status: {sector['review_status']} | Action: {sector['action']}")
        lines.append(f"Current recommendation: {sector['target_symbol']} ({sector['target_kind']}) - {sector['target_name']}")
        if sector.get('candidate_symbol') and sector.get('candidate_symbol') != sector['target_symbol']:
            lines.append(
                f"Watching candidate: {sector['candidate_symbol']} | confirmations {sector.get('pending_confirmations', 0)}/{sector.get('confirmation_required', 0)}"
            )
        if sector.get('previous_symbol'):
            lines.append(f"Previous position: {sector['previous_symbol']} ({sector.get('previous_kind')})")
        lines.append(f"Reason: {sector['action_reason']}")
        lines.append(f"Data status: {sector['data_status']}")
        lines.append('')

    trades = portfolio.get('actionable_trades', [])
    lines.append('MANUAL TRADE LIST')
    lines.append('-' * 20)
    if not trades:
        lines.append('No trade changes suggested. Continue monitoring.')
    else:
        for trade in trades:
            lines.append(
                f"{trade['trade']:>4} | {trade['sector']} | {trade['symbol']} | target {trade['target_weight_pct']}% | {trade['reason']}"
            )
    lines.append('')
    lines.append('Advisory only. Review liquidity, taxes, costs, and account suitability before placing any order manually.')
    return '\n'.join(lines)


def export_manual_report(run_payload: Dict[str, Any], output_config: Dict[str, Any]) -> Dict[str, str]:
    report_dir = output_config.get('report_directory', 'output/reports')
    os.makedirs(report_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    txt_path = os.path.join(report_dir, f'manual_review_{timestamp}.txt')
    json_path = os.path.join(report_dir, f'manual_review_{timestamp}.json')

    with open(txt_path, 'w', encoding='utf-8') as handle:
        handle.write(render_manual_report(run_payload))
    with open(json_path, 'w', encoding='utf-8') as handle:
        json.dump(run_payload, handle, indent=2)

    return {'text_report': txt_path, 'json_report': json_path}
