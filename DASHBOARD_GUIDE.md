# Fund Leader Tracker - Dashboard Guide

## 🎯 Quick Start

### Launch the Dashboard

Simply double-click:
```
launch_dashboard.bat
```

Or from command line:
```cmd
cd C:\Users\ptripathi22\fund_leader_tracker
streamlit run dashboard.py
```

The dashboard will automatically open in your default web browser at `http://localhost:8501`

---

## 📊 Dashboard Features

### 1. Overview Section
- **Total Sectors**: Number of sectors being tracked
- **Funds Analyzed**: How many funds were included in the latest analysis
- **Recent Changes**: Count of leadership changes detected
- **Last Analysis**: Date of most recent data update

### 2. Current Leaders Tab
View the current #1 leader for each sector:

**Features:**
- **Interactive Table**: Sortable data table with all leaders
- **Holdings Chart**: Bar chart showing how many funds hold each leader
- **Weight Chart**: Portfolio weight distribution across sectors
- **Top Companies**: Detailed cards for top 5 companies by weight

**Filters:**
- Select specific sectors to analyze
- Filter by date range
- Sort by any column

### 3. Trends Tab
Visualize leadership changes over time:

**Features:**
- **Leadership Timeline**: Line chart tracking weight changes for each symbol
- **Sector Selector**: Choose which sector to analyze
- **Historical Data Table**: Complete history of leadership changes
- **Multi-symbol Comparison**: See when different stocks led the sector

**Use Case:**
Track when NVDA took over from MSFT in Tech & AI, or monitor sector stability

### 4. History Tab
Complete audit trail of all analyses:

**Features:**
- **Analysis Runs Table**: Every analysis run with metadata
- **Trend Chart**: Leaders found over time
- **Complete Leadership History**: Every leader recorded in database
- **CSV Export**: Download historical data for external analysis

**Filters:**
- Date range selection
- Sector filtering

### 5. About Tab
Learn about the system:

- **How It Works**: Methodology explanation
- **Metrics Guide**: What each metric means
- **Sector Coverage**: All 10 sectors with keywords
- **Configuration**: Current setup details

---

## 🎨 Dashboard Layout

```
┌─────────────────────────────────────────────────┐
│  📊 Fund Leader Tracker Dashboard               │
├─────────────────────────────────────────────────┤
│  Sidebar                   Main Content         │
│  ┌──────────────┐         ┌──────────────────┐ │
│  │ 🔄 Refresh   │         │  Overview Metrics│ │
│  │              │         │  ┌────┬────┬────┐ │ │
│  │ 📅 Filters   │         │  │Sec │Fund│Chng│ │ │
│  │  Date Range  │         │  └────┴────┴────┘ │ │
│  │              │         │                  │ │
│  │ 🏢 Sectors   │         │  Tabs:           │ │
│  │  [✓] Tech    │         │  [Leaders]       │ │
│  │  [✓] Health  │         │  [Trends]        │ │
│  │  [ ] Energy  │         │  [History]       │ │
│  └──────────────┘         │  [About]         │ │
│                           └──────────────────┘ │
└─────────────────────────────────────────────────┘
```

---

## 🔍 Key Use Cases

### 1. Monitor Daily Changes
**Workflow:**
1. Launch dashboard
2. Check "Recent Changes" metric
3. If changes > 0, review leadership changes alert
4. Drill into specific sectors in Trends tab

### 2. Analyze Sector Stability
**Workflow:**
1. Go to Trends tab
2. Select sector (e.g., "Tech & AI")
3. Review leadership timeline chart
4. Check if leader frequently changes or stays stable

### 3. Export Data for Reports
**Workflow:**
1. Go to History tab
2. Set date range filter
3. Select sectors of interest
4. Click "Download Historical Data (CSV)"
5. Open in Excel for further analysis

### 4. Compare Across Sectors
**Workflow:**
1. Go to Current Leaders tab
2. Review Holdings Chart
3. Compare which sectors have most concentrated holdings
4. Check Weight Chart to see which sectors have highest weights

---

## 🎯 Dashboard Controls

### Sidebar Controls

#### Refresh Button (🔄)
- Reloads data from database
- Use after running a new analysis
- Clears cached data (auto-refreshes every 5 minutes)

#### Date Range Filter (📅)
- Select start and end dates
- Applies to History and Trends tabs
- Default: All available data

#### Sector Filter (🏢)
- Multi-select checkboxes
- Filter all views by selected sectors
- Default: All sectors selected

### Interactive Charts

**Hover Features:**
- Hover over bars/lines to see exact values
- Company names and symbols displayed
- Dates and percentages shown

**Zoom & Pan:**
- Click and drag to zoom into specific date ranges
- Double-click to reset zoom
- Use toolbar icons for additional controls

---

## 📱 Dashboard Access

### Local Access
Default URL: `http://localhost:8501`

### Network Access
To access from other devices on your network:

1. Find your PC's IP address:
   ```cmd
   ipconfig
   ```
   Look for "IPv4 Address"

2. Launch with network access:
   ```cmd
   streamlit run dashboard.py --server.address 0.0.0.0
   ```

3. Access from other devices:
   ```
   http://YOUR_IP_ADDRESS:8501
   ```

### Cloud Deployment (Optional)
Deploy to Streamlit Cloud for internet access:
1. Push code to GitHub
2. Sign up at https://streamlit.io/cloud
3. Connect repository
4. Deploy (free tier available)

---

## 🚀 Performance Tips

### Data Loading
- Dashboard caches data for 5 minutes
- Click "Refresh" to force reload
- Large historical datasets may take 2-3 seconds to load

### Browser Compatibility
- **Best**: Chrome, Edge (Chromium)
- **Good**: Firefox, Safari
- **Avoid**: Internet Explorer

### Recommended Settings
- Use wide screen (minimum 1280px width)
- Enable JavaScript
- Allow pop-ups for CSV downloads

---

## 🎨 Customization

### Change Dashboard Port
Edit `launch_dashboard.bat`:
```batch
streamlit run dashboard.py --server.port 8502
```

### Customize Theme
Create `.streamlit/config.toml`:
```toml
[theme]
primaryColor="#1f77b4"
backgroundColor="#ffffff"
secondaryBackgroundColor="#f0f2f6"
textColor="#262730"
font="sans serif"
```

### Auto-Refresh
Add to `dashboard.py` (top of main function):
```python
st_autorefresh(interval=300000, key="datarefresh")  # 5 minutes
```

---

## 🔧 Troubleshooting

### Issue: Dashboard won't start

**Solution 1:** Check if Streamlit is installed
```cmd
streamlit --version
```

**Solution 2:** Install missing dependencies
```cmd
pip install streamlit plotly
```

**Solution 3:** Use Python module syntax
```cmd
python -m streamlit run dashboard.py
```

### Issue: No data showing

**Cause:** No analysis has been run yet

**Solution:** Run an analysis first
```cmd
python main.py
```

### Issue: Port already in use

**Solution:** Stop existing Streamlit process or use different port
```cmd
streamlit run dashboard.py --server.port 8502
```

### Issue: Dashboard loads slowly

**Possible Causes:**
- Large database with many historical records
- Multiple users accessing simultaneously
- Slow disk I/O

**Solutions:**
- Reduce date range filter
- Clear old data: `db_manager.clear_old_data(days=30)`
- Increase cache TTL in dashboard.py

### Issue: Charts not interactive

**Solution:** Enable JavaScript in browser
- Chrome: Settings → Privacy → Site Settings → JavaScript → Allowed
- Firefox: about:config → javascript.enabled → true

---

## 📊 Understanding the Visualizations

### Holdings Frequency Chart
**X-Axis:** Sectors
**Y-Axis:** Number of funds (out of 5) holding the leader
**Color:** Intensity = frequency

**Interpretation:**
- Taller bars = More consensus among funds
- Height of 5 = All funds agree on this leader
- Height of 1-2 = Less consensus, possibly emerging leader

### Portfolio Weight Chart
**X-Axis:** Sectors
**Y-Axis:** Average portfolio weight percentage
**Color:** Intensity = weight

**Interpretation:**
- Taller bars = Funds allocate more to this sector
- 5-10% = Significant holding
- 1-3% = Moderate holding
- <1% = Small position

### Leadership Timeline
**X-Axis:** Date
**Y-Axis:** Average weight percentage
**Lines:** Each symbol/stock

**Interpretation:**
- Rising line = Company gaining prominence
- Falling line = Company losing prominence
- Crossing lines = Leadership change
- Flat line = Stable leadership

---

## 🔔 Integration with Email Alerts

The dashboard shows the same data that triggers email alerts:

**Email Sent When:**
- Leadership change detected (old symbol ≠ new symbol)
- AND email alerts enabled
- AND `send_on_change_only: true`

**Dashboard Shows:**
- Same leadership changes in "Recent Changes" alert box
- Historical view of when changes occurred
- Trends leading up to the change

**Workflow:**
1. Receive email alert: "LEADERSHIP CHANGES DETECTED"
2. Open dashboard to investigate
3. Go to Trends tab
4. Select affected sector
5. Review timeline to understand the shift

---

## 💡 Advanced Features

### Export Capabilities
- **CSV Download**: Raw data export for Excel/PowerBI
- **Chart Download**: Click camera icon on Plotly charts
- **Screenshot**: Use browser screenshot tools

### Data Refresh Frequency
- **Auto-cache**: 5 minutes (configurable)
- **Manual refresh**: Click sidebar button
- **Database updates**: Instant when analysis runs

### Multi-User Support
- Multiple people can view dashboard simultaneously
- Each user has independent filters/selections
- Shared database (read-only for dashboard)

---

## 📖 Best Practices

### Daily Monitoring
1. **Morning Check** (after scheduled analysis):
   - Launch dashboard
   - Check overview metrics
   - Review any changes

2. **Weekly Review**:
   - Analyze trends for each sector
   - Export data for reporting
   - Review historical patterns

3. **Monthly Deep Dive**:
   - Compare sector performance
   - Identify emerging leaders
   - Adjust investment strategy

### Performance Optimization
- Close dashboard when not in use
- Use sector filters to reduce data load
- Limit date range for large databases
- Export CSV for heavy analysis (use Excel/Python)

### Data Integrity
- Dashboard is read-only (doesn't modify data)
- Safe to share with multiple users
- Database locked during analysis runs
- Refresh after each analysis completes

---

## 🎓 Learning Resources

### Streamlit Documentation
https://docs.streamlit.io

### Plotly Charts
https://plotly.com/python/

### Dashboard Shortcuts
- `Ctrl + R`: Reload page
- `Ctrl + Shift + R`: Hard refresh
- `F11`: Full screen mode

---

## 📞 Support

**Dashboard Issues:**
- Check browser console for errors (F12)
- Review `logs/fund_tracker.log`
- Verify database file exists: `data/fund_leaders.db`

**Data Issues:**
- Run `python view_leaders.py all` to verify database content
- Check last analysis date in Overview metrics
- Ensure analysis completed successfully

---

**Congratulations!** Your interactive dashboard is ready to use.

Enjoy tracking fund leaders with real-time visualizations! 🎉
