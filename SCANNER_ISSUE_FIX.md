# Scanner Issue: Getting 1 Stock Instead of 20 - ROOT CAUSE & FIX

## Problem Summary
- **Database (from website)**: Returns 20 stocks
- **Direct Scanner Run**: Returns only 1 stock
- **Root Cause**: Over-restrictive filtering with strict AND logic

---

## Root Cause Analysis

### The Original Filtering Logic
In `src/analysis_engine.py` → `get_long_term_stocks()`:

```python
# OLD CODE (Too Strict - ALL conditions must pass)
if rev_growth > 0.1 AND roe > 0.15 AND debt_equity < 0.5 AND market_cap > 50_000_000_000:
    ACCEPT stock
```

### Why This Failed
1. **Missing Data from yFinance**: Many Indian stocks don't have complete fundamental data
   - `revenueGrowth` → Returns None (especially for older/smaller stocks)
   - `returnOnEquity` → Returns None or incomplete
   - `debtToEquity` → Returns None for many stocks
   
2. **Default Value Problem**:
   - Original code used `info.get('revenueGrowth', 0)` - defaults to 0 when missing
   - `0 > 0.1` fails immediately
   - So even good stocks were rejected due to missing data

3. **All-Or-Nothing Logic**:
   - Required ALL 4 conditions to pass simultaneously
   - In reality, different stocks excel in different areas
   - A high-growth stock might have higher debt
   - A stable dividend stock might have lower growth

4. **Market Cap Paradox**:
   - You had ₹1000+ Cr filter (line 733)
   - But also required ₹5000+ Cr (line 741)
   - This 5x multiplier was unnecessary

---

## The Fix Applied

### New Filtering Logic
```python
# NEW CODE (Flexible - 2 of 3 criteria needed)

MANDATORY: Market Cap > ₹1000 Cr (hard filter)

THEN require AT LEAST 2 of these 3:
  ✓ Revenue Growth > 10%
  ✓ ROE > 15%
  ✓ Debt to Equity < 0.5
```

### Key Changes

#### 1. **Handle Missing Data Properly**
```python
# OLD
rev_growth = info.get('revenueGrowth', 0)  # Defaults to 0 (fails test)

# NEW
rev_growth = info.get('revenueGrowth')  # Stays None if missing
if rev_growth is not None and rev_growth > 0.10:
    criteria_met += 1
```

#### 2. **Flexible Criteria (2 of 3)**
```python
criteria_met = 0

# Test each criterion independently
if rev_growth is not None and rev_growth > 0.10:
    criteria_met += 1

if roe is not None and roe > 0.15:
    criteria_met += 1

if debt_equity is not None and debt_equity < 0.5:
    criteria_met += 1

# Accept if 2+ pass
if criteria_met >= 2:
    ACCEPT stock
```

#### 3. **Increased Scan Pool**
```python
# OLD
max_stocks=800  # Check ~800 stocks

# NEW
max_stocks=2000  # Check ~2000 stocks
# More chances to find 20 results with relaxed criteria
```

#### 4. **Safe Value Formatting**
```python
# Handles N/A values gracefully in output
rev_growth_pct = f"{rev_growth*100:.1f}%" if rev_growth is not None else "N/A"
```

---

## Expected Results

### Before Fix
- Scanner: 1 stock
- Database: 20 stocks  
- Discrepancy: 1900% difference!

### After Fix
- Scanner: ~15-25 stocks (should match database results)
- Quality: Still fundamentally strong (meets 2+ criteria)
- Explanation: More inclusive, less likely to miss good stocks

---

## How the Scoring Works Now

### Example 1: Strong Compounder (HIGH GROWTH)
- Revenue Growth: 25% ✓ (exceeds 10%)
- ROE: 18% ✓ (exceeds 15%)
- Debt/Equity: 0.6 ✗ (slightly above 0.5)
- **Score: 2/3 criteria → ACCEPTED** ✓

### Example 2: Stable Blue Chip (LOW DEBT)
- Revenue Growth: 8% ✗ (below 10%)
- ROE: 16% ✓ (exceeds 15%)
- Debt/Equity: 0.2 ✓ (well below 0.5)
- **Score: 2/3 criteria → ACCEPTED** ✓

### Example 3: Startup (Weak on All)
- Revenue Growth: -5% ✗ (negative)
- ROE: -10% ✗ (negative)
- Debt/Equity: 0.8 ✗ (above 0.5)
- **Score: 0/3 criteria → REJECTED** ✗

---

## File Modified
- `src/analysis_engine.py` → `get_long_term_stocks()` method (lines 723-813)

## Testing Recommendations
1. **Run the scanner** and confirm you get ~15-25 results
2. **Compare with database** - should match now
3. **Check the results** - all should have Market Cap > ₹1000 Cr and pass 2+ criteria
4. **Review edge cases** - stocks with N/A values should still appear if they meet criteria

---

## Additional Notes
- The filter still prevents low-quality stocks (always requires Market Cap > ₹1000 Cr)
- By requiring 2 out of 3 criteria, we capture different stock profiles (growth, value, stability)
- This is more realistic because no single metric tells the whole story
- The 3 criteria cover: **Growth** (revenue), **Efficiency** (ROE), **Safety** (debt/equity)
