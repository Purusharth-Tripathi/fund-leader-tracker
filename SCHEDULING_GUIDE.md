# Fund Leader Tracker - Daily Scheduling & Email Alerts Setup Guide

This guide will help you set up daily automated analysis with email alerts for leadership changes.

## Table of Contents
1. [Email Configuration](#email-configuration)
2. [Windows Task Scheduler Setup](#windows-task-scheduler-setup)
3. [Testing Your Setup](#testing-your-setup)
4. [Troubleshooting](#troubleshooting)

---

## Email Configuration

### Step 1: Enable Email Alerts

Edit your `.env` file and update the email settings:

```env
# Set to true to enable email alerts
EMAIL_ENABLED=true

# Gmail SMTP settings (most common)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587

# Your Gmail address
EMAIL_FROM=your_email@gmail.com

# Gmail App Password (see Step 2)
EMAIL_PASSWORD=your_app_password_here

# Recipient email (can be the same as EMAIL_FROM)
EMAIL_TO=your_email@gmail.com
```

### Step 2: Generate Gmail App Password

**Important:** Gmail requires an "App Password" for third-party applications.

1. Go to your Google Account: https://myaccount.google.com/
2. Navigate to **Security** → **2-Step Verification** (enable if not already)
3. Go to **App passwords**: https://myaccount.google.com/apppasswords
4. Select:
   - App: **Mail**
   - Device: **Windows Computer**
5. Click **Generate**
6. Copy the 16-character password (spaces don't matter)
7. Paste it into your `.env` file as `EMAIL_PASSWORD`

### Step 3: Configure Alert Behavior

Edit `config.yaml` to control when emails are sent:

```yaml
email_alerts:
  enabled: false  # Master switch (overridden by .env EMAIL_ENABLED)
  send_on_completion: false  # Set true to email after EVERY analysis
  send_on_change_only: true  # Set true to email ONLY when leadership changes
```

**Recommended Settings for Daily Monitoring:**
- `send_on_completion: false`
- `send_on_change_only: true`

This way, you'll only receive an email when a sector's leader changes, not every day.

---

## Windows Task Scheduler Setup

### Step 1: Open Task Scheduler

1. Press `Win + R`, type `taskschd.msc`, and press Enter
2. OR search for "Task Scheduler" in Start Menu

### Step 2: Create a New Task

1. Click **Create Task** (not "Create Basic Task") in the right panel
2. Configure the following tabs:

#### General Tab
- **Name:** Fund Leader Tracker - Daily Analysis
- **Description:** Runs daily fund analysis and sends email alerts for leadership changes
- **Security options:**
  - Select: "Run whether user is logged on or not"
  - Check: "Do not store password"
  - Check: "Run with highest privileges"

#### Triggers Tab
1. Click **New**
2. **Begin the task:** On a schedule
3. **Settings:**
   - **Daily**
   - **Start:** Choose a time (e.g., 8:00 AM)
   - **Recur every:** 1 days
4. **Advanced settings:**
   - Check: "Enabled"
5. Click **OK**

#### Actions Tab
1. Click **New**
2. **Action:** Start a program
3. **Program/script:** Browse to `run_daily_analysis.bat`
   - Full path: `C:\Users\ptripathi22\fund_leader_tracker\run_daily_analysis.bat`
4. **Start in (optional):** `C:\Users\ptripathi22\fund_leader_tracker`
5. Click **OK**

#### Conditions Tab
- **Power:**
  - Uncheck "Start the task only if the computer is on AC power"
  - Check "Wake the computer to run this task" (optional)

#### Settings Tab
- Check: "Allow task to be run on demand"
- Check: "Run task as soon as possible after a scheduled start is missed"
- Check: "If the task fails, restart every: 10 minutes"
- Set: "Attempt to restart up to: 3 times"

### Step 3: Save the Task

1. Click **OK**
2. Enter your Windows password if prompted
3. The task is now scheduled!

---

## Testing Your Setup

### Test 1: Run the Batch Script Manually

```cmd
cd C:\Users\ptripathi22\fund_leader_tracker
run_daily_analysis.bat
```

- Check the `logs\` folder for the output log file
- Verify the analysis runs successfully

### Test 2: Test Email Configuration

Edit `main.py` temporarily to force email sending, or wait for the next scheduled run.

Alternatively, run a quick test:

```cmd
cd C:\Users\ptripathi22\fund_leader_tracker
python -c "from email_alerts import EmailAlerts; from utils import load_config; ea = EmailAlerts(load_config()); ea.send_error_alert('Test email from Fund Leader Tracker')"
```

### Test 3: Run Task Manually from Task Scheduler

1. Open Task Scheduler
2. Find your task: "Fund Leader Tracker - Daily Analysis"
3. Right-click → **Run**
4. Check the **Last Run Result** column (should show "0x0" for success)

---

## How It Works

### Daily Workflow

1. **Every day at your scheduled time:**
   - Windows Task Scheduler runs `run_daily_analysis.bat`

2. **The script:**
   - Changes to the project directory
   - Runs `python main.py`
   - Logs all output to `logs\scheduled_run_YYYYMMDD.log`

3. **The analysis:**
   - Fetches fund holdings from Alpha Vantage API
   - Identifies the #1 leader for each of 10 sectors
   - Compares with previous day's leaders (from database)
   - Detects leadership changes

4. **Email alerts (if enabled):**
   - **If leadership changes detected:** Email sent with changes highlighted
   - **If no changes:** No email sent (if `send_on_change_only: true`)
   - **Subject line:** "LEADERSHIP CHANGES DETECTED" or "Analysis Complete"

### Email Content

When a leadership change is detected, you'll receive:

```
FUND LEADER TRACKER - ANALYSIS RESULTS
============================================================

*** LEADERSHIP CHANGES DETECTED ***
============================================================
2 sector(s) have new leaders:

Sector: Tech & AI
  OLD: NVDA - NVIDIA Corporation
  NEW: MSFT - Microsoft Corporation
       Held by 5/5 funds, Avg Weight: 8.25%

Sector: Renewable Energy
  OLD: NEE - NextEra Energy
  NEW: TSLA - Tesla Inc
       Held by 4/5 funds, Avg Weight: 5.10%

============================================================

[Full list of all sector leaders follows...]
```

---

## Troubleshooting

### Issue: Task doesn't run

**Solutions:**
1. Check Task Scheduler → Task Status → "Last Run Result"
   - `0x0` = Success
   - `0x1` = Error - Check script paths
2. Verify the batch script path is correct
3. Ensure Python is in your system PATH
4. Run the batch script manually to test

### Issue: Email not sending

**Solutions:**
1. Verify `EMAIL_ENABLED=true` in `.env`
2. Check Gmail App Password is correct (16 characters, no spaces)
3. Ensure 2-Step Verification is enabled on Google Account
4. Check `logs\fund_tracker.log` for SMTP errors
5. Try logging in to Gmail manually to ensure account isn't locked

### Issue: Email sends every day (too many emails)

**Solution:**
- Edit `config.yaml`:
  ```yaml
  email_alerts:
    send_on_completion: false
    send_on_change_only: true
  ```

### Issue: API rate limit errors

**Solutions:**
1. Free tier allows 25 API calls per day
2. Schedule task for early morning (e.g., 6 AM) to ensure quota is available
3. Upgrade to Alpha Vantage premium plan for higher limits
4. Reduce `top_funds_per_sector` in `config.yaml` (default: 5)

### Issue: Analysis runs but no data

**Solutions:**
1. Check Alpha Vantage API key is valid
2. Verify internet connection
3. Check `logs\` folder for error messages
4. API may be rate-limited - wait 24 hours

### Issue: Missing logs

**Solution:**
- Logs are saved to `logs\scheduled_run_YYYYMMDD.log`
- Check the `logs\` directory exists
- Run batch script manually to verify it creates logs

---

## Advanced Configuration

### Change Schedule Frequency

To run more frequently (e.g., twice daily):

1. Open Task Scheduler
2. Double-click your task
3. Go to **Triggers** tab
4. Edit the trigger:
   - Change "Recur every" to 12 hours
   - OR add a second trigger for a different time

### Custom Email Template

Edit `email_alerts.py` → `_create_email_body()` method to customize the email format.

### Multiple Recipients

In `.env`, use comma-separated email addresses:

```env
EMAIL_TO=user1@gmail.com,user2@gmail.com,user3@gmail.com
```

(Note: You may need to modify `email_alerts.py` to split the string)

### Use Different Email Provider

For Outlook/Office 365:
```env
SMTP_SERVER=smtp.office365.com
SMTP_PORT=587
```

For Yahoo Mail:
```env
SMTP_SERVER=smtp.mail.yahoo.com
SMTP_PORT=587
```

---

## Monitoring Your Scheduled Task

### View Task History

1. Open Task Scheduler
2. Find your task
3. Click **History** tab (if enabled)
4. Review all execution events

### Enable History (if disabled)

1. Task Scheduler → Actions → **Enable All Tasks History**

### Check Logs

Daily logs are saved to:
```
fund_leader_tracker/logs/scheduled_run_YYYYMMDD.log
```

### Database Query

To check what leaders are stored:

```cmd
python view_leaders.py all
```

---

## Best Practices

1. **Test before scheduling:**
   - Run analysis manually first
   - Verify email works
   - Check logs for errors

2. **Monitor API usage:**
   - Free tier: 25 requests/day
   - Each analysis uses ~15-20 API calls
   - Schedule once per day to stay within limits

3. **Review logs weekly:**
   - Check for consistent successful runs
   - Look for API rate limit warnings
   - Verify leadership changes are being detected

4. **Database maintenance:**
   - Database grows over time
   - Old records are kept for historical analysis
   - Use `db_manager.clear_old_data(days=90)` if needed

---

## Support

For issues or questions:
- Check `logs/fund_tracker.log` for detailed error messages
- Review this guide's Troubleshooting section
- Verify API key and email credentials

**Congratulations!** You now have automated daily fund leadership tracking with email alerts. 🎉
