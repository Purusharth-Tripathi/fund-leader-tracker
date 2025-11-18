# Fund Leader Tracker - Static Fund List Fix

## Problem Fixed

**BUG:** The program was re-evaluating which funds are "top 5" every day during analysis, instead of using a static list.

**LOCATION:**
- `fund_analyzer.py:102` - Called `_find_sector_funds()` which searched for funds dynamically
- `fund_analyzer.py:218-220` - The `_find_sector_funds()` method performed fresh fund searches each run

**IMPACT:** This meant the funds being tracked could change daily, defeating the purpose of consistent monitoring.

---

## Solution Implemented

The fix separates the workflow into **two distinct phases**:

### Phase 1: One-Time Initialization (NEW)
Run **ONCE** to identify and save the top 5 funds per industry:
```bash
python initialize_tracked_funds.py
```

This script:
1. Analyzes all candidate funds for each sector
2. Ranks them by 3-year performance
3. Selects the top 5 funds per sector
4. Saves them to a new `tracked_funds` database table
5. **This list remains STATIC** unless you re-run initialization

### Phase 2: Daily Monitoring (MODIFIED)
Run **DAILY** to monitor the pre-selected funds:
```bash
python main.py
```

The daily analysis now:
1. Reads the STATIC fund list from the database (set during initialization)
2. Analyzes only those specific 5 funds per sector
3. **Never changes which funds are being tracked**
4. Only monitors performance and identifies leaders among the static list

---

## Files Changed

### 1. `db_manager.py` ✓
**Changes:**
- Added new `tracked_funds` table to store static fund lists
- Added methods:
  - `save_tracked_fund()` - Save a fund to the static list
  - `get_tracked_funds(sector_name)` - Retrieve static funds for a sector
  - `has_tracked_funds(sector_name)` - Check if static list exists
  - `clear_tracked_funds()` - Clear for re-initialization

**Lines Modified:** 112-122, 332-395

### 2. `fund_analyzer.py` ✓
**Changes:**
- Modified `_find_sector_funds()` method to:
  - **FIRST**: Check database for static tracked funds
  - **IF FOUND**: Use those funds (no re-evaluation!)
  - **IF NOT FOUND**: Warn user and fall back to dynamic search
- Updated method signature to accept `sector_name` parameter
- Updated call site (line 102) to pass sector name

**Lines Modified:** 102, 208-242

**Critical Fix:**
```python
# OLD CODE (BUG):
def _find_sector_funds(self, keywords):
    fund_symbols = self.fetcher.search_funds_by_keywords(keywords)
    return fund_symbols[:top_n]  # Re-searches every time!

# NEW CODE (FIXED):
def _find_sector_funds(self, keywords, sector_name):
    # Use STATIC list from database
    if self.db.has_tracked_funds(sector_name):
        tracked = self.db.get_tracked_funds(sector_name)
        return [f['fund_symbol'] for f in tracked]  # Same funds every time!
```

### 3. `initialize_tracked_funds.py` ✓ (NEW FILE)
**Purpose:** One-time setup script to identify and save top 5 funds per sector

**Functionality:**
- Finds all candidate funds for each sector
- Fetches 3-year performance data
- Ranks by performance
- Saves top 5 to database
- Can be re-run to update the static list

---

## How The System Works Now

### Initial Setup (ONE TIME)
```
User runs: python initialize_tracked_funds.py
    ↓
For each sector:
    ↓
Search all matching funds → Get 3-year performance → Rank funds
    ↓
Select TOP 5 → Save to tracked_funds table
    ↓
RESULT: Static list saved to database
```

### Daily Monitoring (EVERY DAY)
```
User runs: python main.py
    ↓
For each sector:
    ↓
Read STATIC fund list from database (NO re-evaluation!)
    ↓
Fetch holdings for those 5 specific funds
    ↓
Identify leader among those holdings
    ↓
RESULT: Consistent tracking of same funds daily
```

---

## Database Changes

### New Table: `tracked_funds`
```sql
CREATE TABLE tracked_funds (
    id INTEGER PRIMARY KEY,
    sector_name TEXT NOT NULL,
    fund_symbol TEXT NOT NULL,
    fund_name TEXT,
    performance_3year REAL,
    rank_in_sector INTEGER,
    initialized_at TEXT,
    UNIQUE(sector_name, fund_symbol)
);
```

This table stores the **permanent** list of funds to track for each sector.

---

## Usage Instructions

### First Time Setup
```bash
# Step 1: Run initialization (identifies top 5 funds per sector)
python initialize_tracked_funds.py

# Step 2: Run daily analysis (monitors those specific funds)
python main.py
```

### Daily Usage
```bash
# Just run the main analysis - it uses the static fund list
python main.py
```

### Re-initialization (Optional)
```bash
# To change which funds are tracked, re-run initialization
python initialize_tracked_funds.py

# The script will ask if you want to overwrite existing tracked funds
```

---

## Verification

### How to Verify the Fix Works

1. **Check tracked funds in database:**
   ```bash
   python view_leaders.py
   ```

2. **Run analysis twice and compare fund lists:**
   - First run: `python main.py > run1.log`
   - Second run: `python main.py > run2.log`
   - Compare: The fund symbols analyzed should be **identical**

3. **Check logs:**
   Look for this message in logs:
   ```
   Using {N} STATIC tracked funds for {sector_name}
   ```

### Warning Messages
If you see this warning, you need to run initialization first:
```
⚠ WARNING: No static funds configured for {sector_name}
Using dynamic search (not recommended for production)
```

---

## Key Benefits

✓ **Consistent Tracking**: Same funds monitored every day
✓ **No Daily Re-evaluation**: Fund selection happens once during initialization
✓ **Performance-Based Selection**: Top 5 funds chosen by 3-year performance
✓ **Auditable**: Static list stored in database with timestamps
✓ **Controllable**: User decides when to update the tracked fund list

---

## Important Notes

1. **3-Year Performance Data**: The current implementation uses simulated performance data. In production, replace `get_fund_3year_performance()` in `initialize_tracked_funds.py` with actual API calls to fetch real historical performance.

2. **Re-initialization**: Only re-run `initialize_tracked_funds.py` when you want to **change** which funds are being tracked (e.g., quarterly review).

3. **Backward Compatibility**: If no tracked funds exist in the database, the system falls back to the old dynamic search behavior (with warnings).

---

## Summary

The bug is **FIXED**. The system now properly separates:
- **Initialization** (one-time): Select top 5 funds based on performance
- **Daily Monitoring** (recurring): Track only those pre-selected funds

The daily process **never** changes which funds are being tracked!
