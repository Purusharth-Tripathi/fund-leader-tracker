# Fund Leader Tracker - Deployment Guide

## 🌐 Public Access Options

This guide covers multiple ways to access your dashboard from anywhere.

---

## Option 1: Streamlit Cloud (FREE & Easiest) ⭐ RECOMMENDED

Deploy to Streamlit's free cloud hosting - perfect for sharing with anyone, anywhere.

### Prerequisites
- GitHub account (free)
- Your code pushed to GitHub

### Step-by-Step:

#### 1. Create GitHub Repository
```bash
# Initialize git in your project folder
cd C:\Users\ptripathi22\fund_leader_tracker
git init
git add .
git commit -m "Initial commit - Fund Leader Tracker"

# Create repository on GitHub.com
# Then connect and push:
git remote add origin https://github.com/YOUR_USERNAME/fund-leader-tracker.git
git branch -M main
git push -u origin main
```

#### 2. Deploy to Streamlit Cloud

1. Go to https://share.streamlit.io/
2. Click "New app"
3. Connect your GitHub account
4. Select:
   - Repository: `fund-leader-tracker`
   - Branch: `main`
   - Main file path: `dashboard.py`
5. Click "Deploy"

#### 3. Configure Secrets

Since your database is local, you'll need to handle data differently:

**Option A:** Upload database to GitHub (if data is not sensitive)
```bash
git add data/fund_leaders.db
git commit -m "Add sample database"
git push
```

**Option B:** Use GitHub Actions to run analysis daily and commit results

### Result:
You'll get a public URL like:
```
https://your-username-fund-leader-tracker.streamlit.app
```

Access from anywhere: mobile, tablet, laptop!

---

## Option 2: ngrok (Quick Temporary Access)

Get a public URL instantly for testing - no setup required!

### Step 1: Install ngrok
1. Download from: https://ngrok.com/download
2. Extract to a folder
3. Sign up for free account at https://ngrok.com/signup
4. Get your auth token from dashboard

### Step 2: Setup ngrok
```cmd
# Navigate to ngrok folder
cd C:\path\to\ngrok

# Authenticate
ngrok authtoken YOUR_AUTH_TOKEN
```

### Step 3: Create Tunnel
```cmd
# In one terminal, run dashboard
cd C:\Users\ptripathi22\fund_leader_tracker
python -m streamlit run dashboard.py

# In another terminal, create tunnel
ngrok http 8501
```

### Result:
You'll get a public URL like:
```
https://abc123.ngrok.io
```

**Pros:**
- Instant public access
- No code changes needed
- Works with local database

**Cons:**
- URL changes every time you restart
- Free tier has session limits (2 hours)
- Requires keeping your PC running

---

## Option 3: Local Network Access (Already Working!)

Access from any device on your home/office WiFi.

### Your Network URLs:
```
Local:    http://localhost:8501
Network:  http://10.61.95.20:8501
```

### On Your Mobile/Tablet (Same WiFi):
1. Connect to same WiFi network
2. Open browser
3. Go to: `http://10.61.95.20:8501`

**Note:** This only works when:
- Device is on same WiFi
- Dashboard is running on your PC
- Firewall allows connections

---

## Option 4: Port Forwarding (Access from Internet)

Make your dashboard accessible from anywhere via your home IP.

### Prerequisites:
- Access to router settings
- Static or dynamic DNS service

### Steps:

#### 1. Configure Windows Firewall
```cmd
# Allow port 8501 through firewall
netsh advfirewall firewall add rule name="Streamlit Dashboard" dir=in action=allow protocol=TCP localport=8501
```

#### 2. Setup Router Port Forwarding
1. Login to router admin panel (usually 192.168.1.1)
2. Find "Port Forwarding" settings
3. Add rule:
   - External Port: 8501
   - Internal IP: 10.61.95.20 (your PC's IP)
   - Internal Port: 8501
   - Protocol: TCP

#### 3. Find Your Public IP
```cmd
# Visit this in browser:
https://www.whatismyip.com/
```

#### 4. Access Dashboard
```
http://YOUR_PUBLIC_IP:8501
```

**Security Warning:** This exposes your dashboard to the internet. Consider:
- Adding authentication
- Using HTTPS
- Restricting IP access
- Using a VPN instead

---

## Option 5: Cloud Deployment (AWS/Azure/GCP)

Professional hosting with full control.

### AWS Lightsail (Easiest AWS Option)

**Monthly Cost:** ~$5

#### Steps:
1. Create Lightsail instance (Ubuntu)
2. SSH into instance
3. Install Python and dependencies:
```bash
sudo apt update
sudo apt install python3-pip
pip3 install streamlit plotly pandas
```
4. Upload your code via SCP
5. Run dashboard:
```bash
streamlit run dashboard.py --server.port 8501 --server.address 0.0.0.0
```
6. Configure Lightsail firewall to allow port 8501

### Access:
```
http://YOUR_LIGHTSAIL_IP:8501
```

---

## Comparison Table

| Method | Cost | Setup Time | Permanent | Internet Access | Best For |
|--------|------|------------|-----------|-----------------|----------|
| **Streamlit Cloud** | Free | 10 min | Yes | Yes | Sharing with others |
| **ngrok** | Free | 2 min | No | Yes | Quick testing |
| **Local Network** | Free | 0 min | Yes | No | Personal use at home |
| **Port Forward** | Free | 15 min | Yes | Yes | Home access only |
| **AWS/Azure** | $5-20/mo | 30 min | Yes | Yes | Professional use |

---

## Recommended Approach: Streamlit Cloud

For your use case (access from mobile + other devices), I recommend **Streamlit Cloud**:

### Why?
✅ Completely free
✅ Automatic HTTPS (secure)
✅ Accessible from anywhere
✅ No need to keep PC running
✅ Professional URL you can share
✅ Auto-deploys when you update code

### Quick Start:

1. **Install Git** (if not already):
   - Download: https://git-scm.com/download/win

2. **Push to GitHub:**
   ```bash
   cd C:\Users\ptripathi22\fund_leader_tracker
   git init
   git add .
   git commit -m "Fund Leader Tracker"
   ```
   - Create repo at github.com
   - Follow GitHub's instructions to push

3. **Deploy:**
   - Go to share.streamlit.io
   - Connect GitHub
   - Deploy `dashboard.py`
   - Done!

---

## Handling the Database for Cloud Deployment

Since your database is local, you have options:

### Option A: Include Sample Data
```bash
# Add database to git
git add data/fund_leaders.db
git commit -m "Add sample data"
git push
```

### Option B: Use Cloud Database
- SQLite won't work well in Streamlit Cloud (read-only filesystem)
- Consider: PostgreSQL, MySQL, or MongoDB Atlas (free tier)

### Option C: Read-Only Dashboard
- Upload database with sample data
- Dashboard shows data but doesn't run new analyses
- Perfect for viewing/sharing results

---

## Security Considerations

### For Public Deployment:

**1. Remove Sensitive Data**
- Don't commit API keys or passwords to GitHub
- Use `.gitignore`:
```
.env
*.log
__pycache__/
```

**2. Use Streamlit Secrets** (for cloud deployment)
Create `.streamlit/secrets.toml`:
```toml
ALPHA_VANTAGE_API_KEY = "your_key_here"
```

**3. Add Authentication** (optional)
Use streamlit-authenticator package for login page

---

## Mobile-Optimized Access

Your dashboard is already mobile-friendly thanks to Streamlit!

### Tips for Mobile:
- Dashboard auto-adjusts to screen size
- Sidebar collapses on mobile (tap hamburger menu)
- Charts are interactive with touch
- Tables scroll horizontally

---

## Need Help?

Would you like me to:
1. ✅ Help you set up Streamlit Cloud deployment (easiest)
2. ✅ Configure ngrok for instant public access
3. ✅ Set up port forwarding on your router
4. ✅ Create authentication for your dashboard

Let me know which option you prefer, and I'll guide you through it step by step!
