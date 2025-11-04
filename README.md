# 📊 Fund Leader Tracker

**Identify industry leaders by analyzing top fund holdings across 10 key sectors**

## 🎯 Overview

Fund Leader Tracker is a financial research tool that identifies industry leaders by analyzing the holdings of top-performing mutual funds.

## ✨ Features

- 📈 Real-time fund holdings analysis
- 🏆 Leader identification (#1 per sector)
- 🔄 Leadership change detection
- 📧 Email alerts for changes
- 📊 Interactive web dashboard
- 📅 Historical tracking with SQLite
- ⏰ Daily automation support

## 🏢 Sectors Covered

1. Aerospace & Defense
2. Renewable Energy
3. Healthcare & Biotech
4. Automotive
5. Precious Metals
6. Consumer Staples
7. Tech & AI
8. Financial Services
9. Infrastructure
10. Real Estate

## 🚀 Quick Start

### Installation

```bash
pip install -r requirements.txt
```

### Configuration

1. Copy `.env.example` to `.env`
2. Add your Alpha Vantage API key
3. Configure email settings (optional)

### Run Analysis

```bash
python main.py
```

### Launch Dashboard

```bash
streamlit run dashboard.py
```

## 📊 Dashboard Features

- Current leaders with interactive charts
- Historical trends and changes
- Sector-by-sector analysis
- CSV export functionality
- Mobile-friendly design

## 📁 Project Structure

```
fund_leader_tracker/
├── main.py                # Main analysis engine
├── dashboard.py           # Streamlit dashboard
├── fund_analyzer.py       # Analysis logic
├── holdings_fetcher.py    # API integration
├── leader_identifier.py   # Leader detection
├── db_manager.py         # Database operations
├── email_alerts.py       # Email notifications
├── config.yaml           # Configuration
└── requirements.txt      # Dependencies
```

## 🌐 Deployment

Deploy to Streamlit Cloud for free public access:

1. Push to GitHub
2. Go to share.streamlit.io
3. Connect repository
4. Deploy!

See `DEPLOYMENT_GUIDE.md` for details.

## 📖 Documentation

- `QUICK_START.md` - Setup guide
- `SCHEDULING_GUIDE.md` - Automation
- `DASHBOARD_GUIDE.md` - Dashboard usage
- `DEPLOYMENT_GUIDE.md` - Cloud deployment

## 🔒 Security

- Never commit `.env` file
- Use `.gitignore` for sensitive data
- Use Streamlit secrets for cloud deployment

## 📝 License

MIT License - Open source

---

**Data provided by Alpha Vantage | Dashboard powered by Streamlit**
