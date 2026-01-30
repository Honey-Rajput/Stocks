# Scanner Issues Found & Analysis

## Summary
All 4 scanners have similar issues with incomplete data handling. Here's what's weird:

---

## Issue #1: SWING SCANNER
**File**: `src/analysis_engine.py` lines 686-730

### Problems Found

1. **Price Filter Too High** (Line 619)
```python
if price < 100:
    return None
```
- Excludes low-price quality stocks (e.g., HDFC Bank ₹1500+, but many good stocks ₹50-100)
- This is catching good opportunities

2. **Not Handling Empty/Missing Indicators** (Lines 613-616)
```python
ema_val = df['EMA_20'].iloc[-1]
vol_sma_val = df['Vol_SMA_20'].iloc[-1]
rsi_val = df['RSI_14'].iloc[-1]
```
- No check if these are NaN or None
- If calculation fails → scanner crashes silently

3. **Batch Processing Silently Fails** (Line 725)
```python
batch_data = batch_download_data(batch, period=period, interval=interval)
```
- If yFinance fails to fetch data, continues anyway
- No retry logic

4. **Default Result Limit Issue** (Line 75 in run_all_scanners.py)
```python
results = func(ticker_pool, max_results=50, max_workers=15)
```
- Returns 50 results but database may store different amount
- Inconsistency between runs

---

## Issue #2: SMART MONEY (SMC) SCANNER
**File**: `src/analysis_engine.py` lines 952-1000

### Problems Found

1. **Hardcoded Volume Spike Threshold** (Line 981)
```python
if last['Close'] >= prev['Close'] and vol_spike > 50:
```
- 50% volume spike is arbitrary
- Different stocks have different volatility
- May miss real accumulation or catch false signals

2. **No Data Validation** (Lines 970-975)
```python
spread = last['High'] - last['Low']
avg_spread = (df['High'] - df['Low']).rolling(20).mean().iloc[-1]
```
- What if df has < 20 rows?
- What if NaN values in High/Low?
- No error handling

3. **Hardcoded Estimation** (Line 984)
```python
"Delivery %": "85% (Est)",
```
- Static "Est" value - not calculated
- Misleading if true delivery is 40%

4. **Score Calculation Capped** (Line 987)
```python
"Smart Money Score (0–100)": int(min(98, 55 + vol_spike/4)),
```
- Always caps at 98 (why not 100?)
- Different from what user sees in database

---

## Issue #3: CYCLICAL SCANNER
**File**: `src/analysis_engine.py` lines 878-928

### Problems Found

1. **Probability Threshold Hard-Coded** (Line 851)
```python
valid_quarters = [s for s in stats if s['Probability'] >= 0.7 and s['MedianReturn'] >= 2.0]
```
- 70% probability = arbitrary
- 2% median return = arbitrary
- Not configurable

2. **Deleting Data After Processing** (Lines 898-900)
```python
del res['Quarter']
del res['Score']
quarterly_data[q].append(res)
```
- Why delete after appending?
- Harder to debug if needed later

3. **No Validation for Historical Data** (Line 846)
```python
if df_q.empty: return None
```
- But what if only 1 year of data? (Need ~5 for consistency)
- Already filtered at line 846 but not clear why

4. **Data Missing Months** (Line 872)
```python
if len(q_returns) < 5: continue  # Skip if less than 5 instances of this quarter
```
- What if Q1 has 4 instances due to missing data?
- Results become incomplete

---

## Issue #4: WEINSTEIN STAGE SCANNER
**File**: `src/analysis_engine.py` lines 1009-1049

### Problems Found

1. **Stages Dictionary Declared Twice!** (Lines 1022-1023)
```python
stages = {"Stage 1 - Basing": [], "Stage 2 - Advancing": [], "Stage 3 - Top": [], "Stage 4 - Declining": []}
from concurrent.futures import ThreadPoolExecutor
stages = {"Stage 1 - Basing": [], "Stage 2 - Advancing": [], "Stage 3 - Top": [], "Stage 4 - Declining": []}
```
- **BUG**: Dictionary created twice (wasteful, indicates copy-paste error)

2. **Stage Matching Logic is Fragile** (Lines 1035-1040)
```python
for k in stages.keys():
    if k.split(" - ")[0] in stage_name:
        stages[k].append(res)
        break
```
- Relies on string matching ("Stage 1" in stage_name)
- If stage_name format changes → breaks silently
- Better to use a dict mapping

3. **No Data Validation** (Line 1026)
```python
batch_data = batch_download_data(batch, period='1y', interval='1d')
```
- Same issue: no check if data is valid

4. **Only 1 Year Data** (Line 1026)
```python
batch_data = batch_download_data(batch, period='1y', interval='1d')
```
- Stage analysis usually needs longer history
- 1y may miss important support/resistance levels

---

## COMMON ISSUES ACROSS ALL SCANNERS

### Issue A: No Retry Logic
When yFinance fails:
```python
batch_data = batch_download_data(batch, period=period, interval=interval)
```
- Just continues with empty/partial data
- No exponential backoff
- No timeout handling

### Issue B: NaN/None Not Handled
```python
value = df['Indicator'].iloc[-1]  # What if NaN?
if value > threshold:  # Comparison with NaN = Always False
    return result
```

### Issue C: Silent Failures
```python
try:
    # complex calculation
except:
    pass  # Silently skip, no logging
return None
```
- No way to debug what went wrong
- User thinks stock was filtered when it crashed

### Issue D: Inconsistent Data Requirements
- Swing: 50 rows minimum
- SMC: 100 rows minimum
- Cyclical: 10y monthly data (~120 rows)
- Weinstein: 1y daily (~250 rows)
- **No validation that data exists before processing**

### Issue E: Hardcoded Thresholds
All scanners have magic numbers:
- Swing: price > 100, RSI > 50, Volume spike > 50%
- SMC: Volume spike > 50%, spread < avg_spread * 0.8
- Cyclical: Probability >= 0.7, Median Return >= 2.0
- Weinstein: 1 year data

**Should be configurable or documented constants**

---

## Weird Behaviors Explained

### "Swing Scanner returns 3 stocks one day, 18 another"
**Root Cause**: 
- Silent failures when data fetch times out
- Some batches fail, some succeed
- Results inconsistent based on random network delays

**Fix**: Add retry logic with exponential backoff

### "SMC Scanner shows high scores but no real volume"
**Root Cause**:
- Hardcoded 50% volume spike threshold
- May be catching noise instead of real institutional activity
- "Delivery %" is hardcoded "85% (Est)" - not real

**Fix**: Calculate actual delivery % from NSE API, make thresholds dynamic

### "Cyclical Scanner misses obvious seasonal stocks"
**Root Cause**:
- 70% probability requirement too strict
- Some good seasonal stocks may have 65% probability
- Only uses quarterly data (coarse granularity)

**Fix**: Make probability configurable, add monthly analysis

### "Weinstein Scanner shows same stocks in multiple stages"
**Root Cause**:
- Stages dictionary declared twice (bug)
- Stage matching logic fragile
- No clear separation between stages

**Fix**: Clean up duplicate code, use proper stage classification

---

## Comparison: Why Long-Term Scanner Had Different Severity

**Long-Term Scanner Issues**:
- Missing fundamental data (from yFinance API limitation)
- All conditions AND together → strict rejection

**Other Scanners Issues**:
- Data validation problems (NaN/None)
- Silent failures (try/except without logging)
- Retry logic missing
- Magic numbers without documentation
- Inconsistent requirements
- Random batches failing

**Why Long-Term was "worse"**:
- Technical data (OHLCV) is more complete in yFinance
- Fundamental data is sparse for Indian stocks
- Combination hit 99% rejection rate

**Why Others are "weird"**:
- Data exists but processing is fragile
- Random network failures cause inconsistent results
- No robust error handling
- User sees different results day-to-day

---

## Priority Fixes Needed

### HIGH PRIORITY (Affects accuracy)
1. Add data validation before processing (check for NaN)
2. Add retry logic with exponential backoff
3. Implement proper logging for debugging
4. Make hardcoded thresholds configurable

### MEDIUM PRIORITY (Affects reliability)
1. Fix duplicate stages dictionary in Weinstein
2. Handle empty batch_data gracefully
3. Add timeout handling for stuck requests

### LOW PRIORITY (Affects consistency)
1. Standardize minimum data requirements
2. Document all magic numbers
3. Add progress reporting for long operations

---

## Weird Behaviors Summary Table

| Scanner | Weird Behavior | Root Cause | Severity |
|---------|---|---|---|
| Swing | Returns 1-20 stocks randomly | Silent batch failures | HIGH |
| SMC | Shows fake "85% Delivery" | Hardcoded estimate | MEDIUM |
| Cyclical | Misses good seasonal stocks | Probability threshold too strict | MEDIUM |
| Weinstein | Duplicate stages dict | Copy-paste error | HIGH |
| All | Silent failures | No logging/error handling | HIGH |
| All | Inconsistent results | No retry logic | HIGH |
| All | NaN crashes | No data validation | HIGH |

