"""
Test Email Alert Functionality
Quick test script to verify email configuration
"""
import os
import sys
from utils import load_env, load_config, print_colored, Colors
from email_alerts import EmailAlerts

def test_email():
    """Test email alert functionality"""
    print("=" * 60)
    print("Fund Leader Tracker - Email Alert Test")
    print("=" * 60)
    print()

    # Load configuration
    load_env()
    config = load_config()

    # Check email enabled
    enabled = os.getenv('EMAIL_ENABLED', 'false').lower() == 'true'
    print(f"Email Enabled: {enabled}")
    print(f"SMTP Server: {os.getenv('SMTP_SERVER', 'Not set')}")
    print(f"SMTP Port: {os.getenv('SMTP_PORT', 'Not set')}")
    print(f"Email From: {os.getenv('EMAIL_FROM', 'Not set')}")
    print(f"Email To: {os.getenv('EMAIL_TO', 'Not set')}")
    print()

    if not enabled:
        print_colored("Email is disabled in .env file", Colors.WARNING)
        print("\nTo enable email alerts:")
        print("1. Edit .env file")
        print("2. Set EMAIL_ENABLED=true")
        print("3. Configure EMAIL_FROM, EMAIL_PASSWORD, EMAIL_TO")
        print()
        return False

    # Check credentials
    email_from = os.getenv('EMAIL_FROM', '')
    email_password = os.getenv('EMAIL_PASSWORD', '')
    email_to = os.getenv('EMAIL_TO', '')

    if not email_from or 'your_' in email_from:
        print_colored("EMAIL_FROM not configured", Colors.FAIL)
        return False

    if not email_password or 'your_' in email_password:
        print_colored("EMAIL_PASSWORD not configured", Colors.FAIL)
        return False

    if not email_to or 'recipient@' in email_to:
        print_colored("EMAIL_TO not configured", Colors.FAIL)
        return False

    print_colored("Configuration looks good! Sending test email...\n", Colors.OKGREEN)

    # Create test email
    email_alerts = EmailAlerts(config)

    # Test 1: Simple error alert
    print("Test 1: Sending simple test alert...")
    success = email_alerts.send_error_alert("This is a test email from Fund Leader Tracker!")

    if success:
        print_colored("[SUCCESS] Test email sent!", Colors.OKGREEN)
        print(f"Check your inbox at: {email_to}")
        print()
    else:
        print_colored("[FAILED] Could not send email", Colors.FAIL)
        print("Check logs/fund_tracker.log for details")
        print()
        return False

    # Test 2: Sample analysis complete email
    print("Test 2: Sending sample analysis report with leadership changes...")

    # Mock results
    mock_results = {
        'Tech & AI': {
            'top_leader': {
                'symbol': 'NVDA',
                'name': 'NVIDIA Corporation',
                'times_held': 5,
                'avg_weight': 8.5,
                'prevalence': 100.0
            }
        },
        'Healthcare & Biotech': {
            'top_leader': {
                'symbol': 'UNH',
                'name': 'UnitedHealth Group',
                'times_held': 4,
                'avg_weight': 3.2,
                'prevalence': 80.0
            }
        }
    }

    mock_summary = {
        'sectors_analyzed': 2,
        'total_leaders': 2,
        'changes_detected': 1,
        'has_changes': True
    }

    mock_changes = [
        {
            'sector': 'Tech & AI',
            'old_symbol': 'MSFT',
            'old_name': 'Microsoft Corporation',
            'new_symbol': 'NVDA',
            'new_name': 'NVIDIA Corporation',
            'new_times_held': 5,
            'new_avg_weight': 8.5
        }
    ]

    success = email_alerts.send_analysis_complete(mock_results, mock_summary, mock_changes)

    if success:
        print_colored("[SUCCESS] Sample analysis report sent!", Colors.OKGREEN)
        print(f"Check your inbox at: {email_to}")
        print()
        print("You should receive 2 emails:")
        print("  1. Simple test alert")
        print("  2. Sample analysis report with leadership change")
        print()
    else:
        print_colored("[FAILED] Could not send analysis report", Colors.FAIL)
        print("Check logs/fund_tracker.log for details")
        print()
        return False

    print("=" * 60)
    print_colored("Email test completed successfully!", Colors.OKGREEN)
    print("=" * 60)
    return True


if __name__ == '__main__':
    success = test_email()
    sys.exit(0 if success else 1)
