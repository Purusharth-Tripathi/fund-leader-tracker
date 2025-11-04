"""
Email Alerts for Fund Leader Tracker
Sends email notifications with analysis results
"""
import smtplib
import os
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
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
        self.enabled = os.getenv('EMAIL_ENABLED', 'false').lower() == 'true'
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', 587))
        self.email_from = os.getenv('EMAIL_FROM', '')
        self.email_password = os.getenv('EMAIL_PASSWORD', '')
        self.email_to = os.getenv('EMAIL_TO', '')
        self.config = config

    def send_analysis_complete(self, results, summary, changes=None):
        """
        Send email when analysis is complete

        Args:
            results: Analysis results dictionary
            summary: Summary statistics
            changes: List of leadership changes (optional)

        Returns:
            bool: True if email sent successfully
        """
        if not self.enabled:
            logger.info("Email alerts are disabled")
            return False

        if not self._validate_config():
            logger.warning("Email configuration incomplete - skipping email")
            return False

        try:
            # Customize subject based on changes
            if changes:
                subject = f"Fund Leader Tracker - LEADERSHIP CHANGES DETECTED ({datetime.now().strftime('%Y-%m-%d')})"
            else:
                subject = f"Fund Leader Tracker - Analysis Complete ({datetime.now().strftime('%Y-%m-%d')})"

            body = self._create_email_body(results, summary, changes)

            return self._send_email(subject, body)

        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return False

    def _validate_config(self):
        """Validate email configuration"""
        if not self.email_from or not self.email_to or not self.email_password:
            return False
        return True

    def _create_email_body(self, results, summary, changes=None):
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
        body.append("FUND LEADER TRACKER - ANALYSIS RESULTS")
        body.append("=" * 60)
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
        body.append(f"Sectors Analyzed: {summary.get('sectors_analyzed', 0)}")
        body.append(f"Leaders Identified: {summary.get('total_leaders', 0)} (1 per sector)")
        body.append(f"Leadership Changes: {summary.get('changes_detected', 0)}")
        body.append("")

        # Top leader by sector
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
        body.append("\nThis is an automated report from Fund Leader Tracker")
        body.append("Generated with Alpha Vantage data\n")

        return '\n'.join(body)

    def _send_email(self, subject, body):
        """
        Send email using SMTP

        Args:
            subject: Email subject
            body: Email body

        Returns:
            bool: True if sent successfully
        """
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_from
            msg['To'] = self.email_to
            msg['Subject'] = subject

            msg.attach(MIMEText(body, 'plain'))

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
