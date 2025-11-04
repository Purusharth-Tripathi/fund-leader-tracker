# Fund Leader Tracker - Quick Start Guide

Get up and running with Fund Leader Tracker in 5 minutes!

## Step 1: Verify Python Installation

```bash
python --version
```

You should see Python 3.8 or higher. If not, download from https://www.python.org/

## Step 2: Navigate to Project Directory

```bash
cd fund_leader_tracker
```

## Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- requests (API calls)
- pyyaml (configuration)
- python-dotenv (environment variables)
- pandas (data processing)
- colorama (colored output)
- tabulate (formatted tables)

## Step 4: Get Your Free API Key

1. Go to https://www.alphavantage.co/support/#api-key
2. Enter your email address
3. Click "GET FREE API KEY"
4. Copy the API key (it looks like: `ABC123XYZ456`)

## Step 5: Configure API Key

### Option A: Copy and Edit (Recommended)

**Windows:**
```bash
copy .env.example .env
notepad .env
```

**Mac/Linux:**
```bash
cp .env.example .env
nano .env
```

Replace `your_api_key_here` with your actual API key:
```
ALPHA_VANTAGE_API_KEY=ABC123XYZ456
```

Save and close the file.

### Option B: Create .env Manually

Create a new file named `.env` with this content:
```
ALPHA_VANTAGE_API_KEY=ABC123XYZ456
DATABASE_PATH=data/fund_leaders.db
LOG_LEVEL=INFO
EMAIL_ENABLED=false
```

## Step 6: Test Your Setup

```bash
python main.py test
```

You should see:
```
✓ API connection successful!
  Sample quote retrieved for IBM
  Price: 123.45
```

If you see an error, check:
- API key is correct in .env
- Internet connection is working
- No firewall blocking HTTPS

## Step 7: Run Your First Analysis

```bash
python main.py
```

This will:
1. Analyze all 10 sectors
2. Fetch holdings for top 5 funds per sector
3. Identify industry leaders
4. Save results to database
5. Export to CSV and JSON

**Note**: This takes 5-10 minutes due to API rate limits.

Expected output:
```
============================================================
           FUND LEADER TRACKER
============================================================

[1/10] Analyzing: Aerospace & Defense
Found 3 funds: ITA, XAR, PPA
Fetching holdings for ITA [OK]
...

Top Leaders in Aerospace & Defense
------------------------------------------------------------
Rank   Symbol     Company                Times Held  Avg Weight
1      BA         Boeing Co              3           5.67%
2      LMT        Lockheed Martin        3           4.89%
...
```

## Step 8: View Your Results

### Show All Leaders
```bash
python view_leaders.py all
```

### Show Specific Sector
```bash
python view_leaders.py sector "Tech & AI"
```

### List Available Sectors
```bash
python view_leaders.py sectors
```

### Export to CSV
```bash
python view_leaders.py export output/leaders.csv
```

## Understanding the Results

### Leader Rankings

Leaders are ranked by:
1. **Times Held**: How many funds hold this stock
2. **Avg Weight**: Average portfolio allocation across funds
3. **Prevalence**: Percentage of funds that hold this stock

Example:
```
Symbol: MSFT
Times Held: 4 (held by 4 out of 5 funds)
Avg Weight: 8.5% (average allocation is 8.5%)
Prevalence: 80% (80% of funds hold this stock)
```

### Output Files

After running, you'll find:

**Database:**
- `data/fund_leaders.db` - SQLite database with all results

**CSV Export:**
- `output/leaders.csv` - Spreadsheet-friendly format

**JSON Export:**
- `output/leaders.json` - Machine-readable format

**Logs:**
- `logs/fund_tracker.log` - Detailed execution log

## Common Use Cases

### Daily Leader Check
```bash
# Run analysis once per day (API limit: 25 calls/day)
python main.py
python view_leaders.py all
```

### Focus on One Sector
```bash
python view_leaders.py sector "Renewable Energy" 20
```

### Export for Spreadsheet Analysis
```bash
python view_leaders.py export output/my_analysis.csv
# Open output/my_analysis.csv in Excel
```

## Troubleshooting

### "API key not configured"

**Problem**: .env file not found or API key missing

**Solution**:
1. Ensure `.env` file exists in project root
2. Check spelling: `ALPHA_VANTAGE_API_KEY` (exact match)
3. No quotes around the API key
4. No spaces before/after the =

### "API rate limit reached"

**Problem**: Exceeded 25 requests per day (free tier)

**Solutions**:
1. Wait 24 hours for reset
2. Upgrade to premium tier at https://www.alphavantage.co/premium/
3. Run analysis less frequently (once daily recommended)

### "SSL Certificate Error"

**Problem**: Corporate firewall/proxy blocking HTTPS

**Solution**: Already handled! The tool disables SSL verification automatically.

### "No holdings data"

**Problem**: Some funds don't have publicly available holdings

**Solution**: Normal behavior. The tool will skip unavailable funds and continue.

### "Import Error: No module named..."

**Problem**: Dependencies not installed

**Solution**:
```bash
pip install -r requirements.txt
```

## Tips for Best Results

### 1. Run During Off-Peak Hours
API response times are faster early morning or late evening (US time).

### 2. Check the Logs
If something seems off, check `logs/fund_tracker.log` for details.

### 3. Save Historical Data
The database keeps all historical runs. Compare trends over time:
```sql
sqlite3 data/fund_leaders.db
SELECT * FROM analysis_runs ORDER BY run_date DESC;
```

### 4. Customize Sectors
Edit `config.yaml` to add your own sectors or modify keywords.

### 5. Export Regularly
Keep CSV backups for spreadsheet analysis:
```bash
python view_leaders.py export "output/leaders_$(date +%Y%m%d).csv"
```

## Next Steps

### Enable Email Alerts

1. Edit `.env`:
```
EMAIL_ENABLED=true
EMAIL_FROM=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
EMAIL_TO=recipient@gmail.com
```

2. For Gmail, create App Password:
   - Google Account → Security → 2-Step Verification → App passwords
   - Select "Mail" and your device
   - Copy the 16-character password

3. Run analysis:
```bash
python main.py
```

You'll receive an email with top leaders from each sector!

### Customize Your Analysis

Edit `config.yaml` to:
- Add more sectors
- Change number of funds per sector
- Adjust holding weight thresholds
- Modify output formats

### Schedule Automatic Runs

**Windows Task Scheduler:**
```
Action: python C:\path\to\fund_leader_tracker\main.py
Trigger: Daily at 6:00 AM
```

**Linux/Mac Cron:**
```bash
crontab -e
# Add: 0 6 * * * cd /path/to/fund_leader_tracker && python main.py
```

## Getting Help

### Check Logs First
```bash
tail -50 logs/fund_tracker.log
```

### Common Log Messages

**INFO: Successfully fetched profile for XLK**
✓ Normal - fund data retrieved

**WARNING: No holdings data found for XYZ**
⚠ Normal - fund doesn't provide holdings via API

**ERROR: Request error fetching profile**
✗ Problem - check internet connection

### Still Stuck?

1. Verify API key at https://www.alphavantage.co/support/#api-key
2. Test connectivity: `python main.py test`
3. Check file permissions on data/ and logs/ folders
4. Ensure Python version >= 3.8

## Quick Reference

```bash
# Run full analysis
python main.py

# Test API
python main.py test

# View all results
python view_leaders.py all

# View sector
python view_leaders.py sector "Tech & AI"

# List sectors
python view_leaders.py sectors

# Export CSV
python view_leaders.py export output/leaders.csv
```

## Success Checklist

- [ ] Python 3.8+ installed
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Alpha Vantage API key obtained
- [ ] `.env` file created with API key
- [ ] API test successful (`python main.py test`)
- [ ] First analysis completed (`python main.py`)
- [ ] Results viewed (`python view_leaders.py all`)

## What's Next?

🎯 **Congratulations!** You've successfully set up Fund Leader Tracker.

Now you can:
- Run daily analyses to track leader changes
- Export results for further research
- Customize sectors and analysis parameters
- Enable email alerts for automatic updates
- Build your own investment research workflow

---

**Need more details?** See [README.md](README.md) for complete documentation.

**Questions?** Check the troubleshooting section or review the logs.

Happy tracking! 📊
