"""
Email Alerts for Fund Leader Tracker
Sends email notifications with analysis results
"""
import smtplib
import os
import logging
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime

logger = logging.getLogger(__name__)


class EmailAlerts:
    """Handles email notifications for analysis results"""

    def __init__(self, config):
        """
        Initialize Email Alerts

        Args:
            config: Email configuration dictionary
        """
        self.config = config or {}
        email_cfg = self.config.get('email_alerts', {}) if isinstance(self.config, dict) else {}

        env_enabled = os.getenv('EMAIL_ENABLED')
        cfg_enabled = email_cfg.get('enabled')
        self.enabled = str(env_enabled if env_enabled is not None else cfg_enabled if cfg_enabled is not None else 'false').lower() == 'true'

        self.send_on_completion = str(email_cfg.get('send_on_completion', True)).lower() == 'true'
        self.send_on_change_only = str(email_cfg.get('send_on_change_only', False)).lower() == 'true'
        self.include_top_n_leaders = int(email_cfg.get('include_top_n_leaders', 10) or 10)

        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', 587))
        self.email_from = os.getenv('EMAIL_FROM', '')
        self.email_password = os.getenv('EMAIL_PASSWORD', '')
        self.email_to = os.getenv('EMAIL_TO', '')

    def send_analysis_complete(self, results, summary, changes=None, attachments=None, run_payload=None):
        """
        Send email when analysis is complete

        Args:
            results: Analysis results dictionary
            summary: Summary statistics
            changes: List of leadership changes (optional)
            attachments: Optional iterable of file paths to attach
            run_payload: Optional full run payload for richer email rendering

        Returns:
            bool: True if email sent successfully
        """
        if not self.enabled:
            logger.info("Email alerts are disabled")
            return False

        if not self.send_on_completion:
            logger.info("Email alerts configured to skip completion sends")
            return False

        if self.send_on_change_only and not changes:
            logger.info("Email alerts configured for change-only sends and no changes were detected")
            return False

        if not self._validate_config():
            logger.warning("Email configuration incomplete - skipping email")
            return False

        try:
            review_date = None
            if run_payload:
                review_date = run_payload.get('review_date')
            date_label = review_date or datetime.now().strftime('%Y-%m-%d')

            if changes:
                subject = f"ETF Leadership Weekly Review - Changes Detected ({date_label})"
            else:
                subject = f"ETF Leadership Weekly Review ({date_label})"

            body = self._create_email_body(results, summary, changes, run_payload=run_payload)

            return self._send_email(subject, body, attachments=attachments)

        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return False

    def _validate_config(self):
        """Validate email configuration"""
        if not self.email_from or not self.email_to or not self.email_password:
            return False
        return True

    def _create_email_body(self, results, summary, changes=None, run_payload=None):
        """
        Create formatted email body

        Args:
            results: Analysis results
            summary: Summary statistics
            changes: List of leadership changes (optional)

        Returns:
            str: Formatted email body
        """
        body = []
        body.append("ETF SECTOR LEADERSHIP WEEKLY REVIEW")
        body.append("=" * 60)
        if run_payload:
            body.append(f"\nRun timestamp: {run_payload.get('run_timestamp', datetime.now().isoformat())}")
            body.append(f"Review date: {run_payload.get('review_date', datetime.now().strftime('%Y-%m-%d'))}\n")
        else:
            body.append(f"\nDate: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        # Leadership changes section (if any)
        if changes:
            body.append("*** LEADERSHIP CHANGES DETECTED ***")
            body.append("=" * 60)
            body.append(f"{len(changes)} sector(s) have new leaders:\n")

            for change in changes:
                body.append(f"Sector: {change['sector']}")
                body.append(f"  OLD: {change['old_symbol']} - {change['old_name']}")
                body.append(f"  NEW: {change['new_symbol']} - {change['new_name']}")
                body.append(f"       Held by {change['new_times_held']}/5 funds, Avg Weight: {change['new_avg_weight']:.2f}%")
                body.append("")

            body.append("=" * 60)
            body.append("")

        # Summary section
        body.append("SUMMARY")
        body.append("-" * 60)
        body.append(f"Sectors analyzed: {summary.get('sectors_analyzed', 0)}")
        body.append(f"Leaders identified: {summary.get('total_leaders', 0)}")
        body.append(f"Switches proposed: {summary.get('switches', summary.get('changes_detected', 0))}")
        body.append(f"ETF fallback sectors: {summary.get('fallbacks', 0)}")
        body.append(f"Stale sectors: {summary.get('stale_sectors', 0)}")
        body.append(f"Cache-miss sectors: {summary.get('cache_miss_sectors', 0)}")
        if run_payload:
            portfolio = run_payload.get('portfolio_plan', {}) or {}
            body.append(f"Actionable sectors: {portfolio.get('actionable_sector_count', 0)}")
        body.append("")

        if run_payload and run_payload.get('sectors'):
            body.append("SECTOR DECISIONS")
            body.append("=" * 60)
            for sector in run_payload.get('sectors', []):
                freshness = sector.get('sector_freshness') or {}
                body.append(f"{sector.get('sector')}: {sector.get('target_symbol')} ({sector.get('target_kind')})")
                body.append(f"  Action: {sector.get('action')} | Status: {sector.get('review_status')} | Freshness: {freshness.get('freshness', 'unknown')}")
                body.append(f"  Reason: {sector.get('action_reason')}")
                if sector.get('candidate_symbol') and sector.get('candidate_symbol') != sector.get('target_symbol'):
                    body.append(f"  Watching: {sector.get('candidate_symbol')} | confirmations {sector.get('pending_confirmations', 0)}/{sector.get('confirmation_required', 0)}")
                body.append("")
        else:
            # Legacy fallback: Top leader by sector
            body.append("TOP LEADER BY SECTOR")
            body.append("=" * 60)
            body.append(f"{'Sector':<25} {'Symbol':<10} {'Company':<30} {'Held By':<12} {'Weight'}")
            body.append("-" * 80)

            for sector_name, data in results.items():
                leader = data.get('top_leader')
                if not leader:
                    continue

                symbol = leader['symbol'][:9]
                name = leader.get('name', 'N/A')[:29]
                times = f"{leader['times_held']}/5"
                weight = f"{leader['avg_weight']:.2f}%"

                body.append(f"{sector_name:<25} {symbol:<10} {name:<30} {times:<12} {weight}")

            body.append("")

        # Footer
        body.append("=" * 60)
        body.append("\nAttached: text and JSON review reports when available.")
        body.append("Advisory only — review manually before taking any action.\n")

        return '\n'.join(body)

    def _send_email(self, subject, body, attachments=None):
        """
        Send email using SMTP

        Args:
            subject: Email subject
            body: Email body
            attachments: Iterable of file paths to attach

        Returns:
            bool: True if sent successfully
        """
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_from
            msg['To'] = self.email_to
            msg['Subject'] = subject

            msg.attach(MIMEText(body, 'plain', 'utf-8'))

            for attachment in attachments or []:
                if not attachment:
                    continue
                path = Path(attachment)
                if not path.exists() or not path.is_file():
                    logger.warning(f"Attachment not found, skipping: {attachment}")
                    continue
                with path.open('rb') as handle:
                    part = MIMEApplication(handle.read(), Name=path.name)
                part['Content-Disposition'] = f'attachment; filename="{path.name}"'
                msg.attach(part)

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_from, self.email_password)
                server.send_message(msg)

            logger.info(f"Email sent successfully to {self.email_to}")
            print(f"[EMAIL] Email sent to {self.email_to}")
            return True

        except smtplib.SMTPException as e:
            logger.error(f"SMTP error sending email: {e}")
            return False
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return False

    def send_error_alert(self, error_message):
        """
        Send alert when analysis encounters an error

        Args:
            error_message: Description of the error

        Returns:
            bool: True if sent successfully
        """
        if not self.enabled or not self._validate_config():
            return False

        subject = "Fund Leader Tracker - Analysis Error"
        body = f"""
FUND LEADER TRACKER - ERROR ALERT
{'=' * 60}

Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

An error occurred during the analysis:

{error_message}

Please check the logs for more details.

{'=' * 60}
This is an automated alert from Fund Leader Tracker
"""

        return self._send_email(subject, body)
