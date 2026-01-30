# Scanner Fixes - Implementation Guide

## Issue Summary & Fixes

### SWING SCANNER FIXES

**Current Code** (lines 686-730):
```python
def get_swing_stocks(ticker_pool, interval='1d', period='1y', max_results=20, max_workers=20):
    batch_data = batch_download_data(batch, period=period, interval=interval)
    # No retry logic, silent failures
    
    if price < 100:  # Too high
        return None
    
    ema_val = df['EMA_20'].iloc[-1]  # No NaN check
```

**Issues**:
1. No data validation
2. Price filter at 100 is arbitrary
3. No retry for failed downloads
4. Silent NaN crashes

**Fix Locations**:
- Add data validation before indicator calculation
- Make price configurable (ScannerConfig.SWING_MIN_PRICE)
- Add safe value retrieval with defaults
- Add retry logic to batch_download_data

---

### SMC SCANNER FIXES

**Current Code** (lines 952-1000):
```python
def _process_smc_stock(ticker, df):
    # No minimum row check
    last = df.iloc[-1]
    vol_spike = (last['Volume'] / avg_vol) * 100 - 100
    
    "Delivery %": "85% (Est)",  # Hardcoded!
    "Smart Money Score (0–100)": int(min(98, 55 + vol_spike/4))
```

**Issues**:
1. No data validation
2. Hardcoded delivery %
3. Arbitrary score cap at 98
4. Fragile volume calculation

**Fix Locations**:
- Add min row check: `if len(df) < ScannerConfig.SMC_MIN_ROWS: return None`
- Calculate actual delivery % (stub for now, would need NSE API)
- Remove artificial cap: use `min(100, ...)`
- Add try/except around division operations

---

### CYCLICAL SCANNER FIXES

**Current Code** (lines 878-928):
```python
valid_quarters = [s for s in stats if s['Probability'] >= 0.7 and s['MedianReturn'] >= 2.0]

if len(q_returns) < 5: continue  # Skip if less than 5 instances

# Deletes data after processing
del res['Quarter']
del res['Score']
```

**Issues**:
1. Hardcoded 0.7 probability threshold
2. Hardcoded 2.0% return threshold
3. Incomplete data silently skipped
4. Unnecessary data deletion

**Fix Locations**:
- Use `ScannerConfig.CYCLICAL_MIN_PROBABILITY` instead of 0.7
- Use `ScannerConfig.CYCLICAL_MIN_RETURN` instead of 2.0
- Log when quarters are skipped due to insufficient data
- Don't delete Quarter/Score (use copy if needed)

---

### WEINSTEIN SCANNER FIXES

**Current Code** (lines 1009-1049):
```python
stages = {"Stage 1 - Basing": [], ...}  # Line 1022
from concurrent.futures import ThreadPoolExecutor
stages = {"Stage 1 - Basing": [], ...}  # Line 1023 - DUPLICATE!

for k in stages.keys():
    if k.split(" - ")[0] in stage_name:  # Fragile string matching
```

**Issues**:
1. Duplicate stages dictionary (line 1022 & 1023)
2. Fragile string matching for stage names
3. No validation of stage_name format
4. Only 1 year data (may be insufficient)

**Fix Locations**:
- Remove duplicate dictionary (line 1022)
- Create proper stage mapping dict (instead of string matching)
- Validate stage_name format before matching
- Increase period to '2y' for better support/resistance

---

## Implementation Order

### Priority 1: Add Robustness Utilities (DONE)
- ✅ Created `src/scanner_robustness.py`
- ✅ Includes: retry_with_backoff, DataValidator, BatchProcessor

### Priority 2: Fix Individual Scanners
1. Swing Scanner: Add validation + configurable thresholds
2. SMC Scanner: Add validation + remove hardcoded values
3. Cyclical Scanner: Use config values + logging
4. Weinstein Scanner: Fix duplicate dict + improve stage matching

### Priority 3: Test & Verify
- Run scanners individually
- Check for silent failures
- Verify result consistency

---

## Code Changes Needed

### Change 1: Swing Scanner (Line 619)
```python
# OLD
if price < 100:
    return None

# NEW
from scanner_robustness import ScannerConfig, DataValidator
if price < ScannerConfig.SWING_MIN_PRICE:
    return None
```

### Change 2: Swing Scanner (Lines 613-616)
```python
# OLD
ema_val = df['EMA_20'].iloc[-1]
vol_sma_val = df['Vol_SMA_20'].iloc[-1]
rsi_val = df['RSI_14'].iloc[-1]

# NEW
ema_val = DataValidator.safe_get_value(df['EMA_20'], default=None)
if ema_val is None:
    return None
vol_sma_val = DataValidator.safe_get_value(df['Vol_SMA_20'], default=None)
rsi_val = DataValidator.safe_get_value(df['RSI_14'], default=None)
if vol_sma_val is None or rsi_val is None:
    return None
```

### Change 3: SMC Scanner (Line 969)
```python
# OLD
if len(df) < 100: return None

# NEW
if len(df) < ScannerConfig.SMC_MIN_ROWS: return None
```

### Change 4: SMC Scanner (Line 984)
```python
# OLD
"Delivery %": "85% (Est)",

# NEW
"Delivery %": "N/A (Requires NSE API)",  # TODO: Integrate with NSE data
```

### Change 5: SMC Scanner (Line 987)
```python
# OLD
"Smart Money Score (0–100)": int(min(98, 55 + vol_spike/4)),

# NEW
"Smart Money Score (0–100)": int(min(100, max(0, 55 + vol_spike/4))),
```

### Change 6: Cyclical Scanner (Line 851)
```python
# OLD
valid_quarters = [s for s in stats if s['Probability'] >= 0.7 and s['MedianReturn'] >= 2.0]

# NEW
from scanner_robustness import ScannerConfig
valid_quarters = [s for s in stats 
                  if s['Probability'] >= ScannerConfig.CYCLICAL_MIN_PROBABILITY 
                  and s['MedianReturn'] >= ScannerConfig.CYCLICAL_MIN_RETURN]
```

### Change 7: Cyclical Scanner (Lines 898-900)
```python
# OLD
del res['Quarter']
del res['Score']
quarterly_data[q].append(res)

# NEW
res_copy = res.copy()  # Don't modify original
del res_copy['Quarter']
del res_copy['Score']
quarterly_data[q].append(res_copy)
```

### Change 8: Weinstein Scanner (Lines 1022-1023)
```python
# OLD
stages = {"Stage 1 - Basing": [], "Stage 2 - Advancing": [], "Stage 3 - Top": [], "Stage 4 - Declining": []}
from concurrent.futures import ThreadPoolExecutor
stages = {"Stage 1 - Basing": [], "Stage 2 - Advancing": [], "Stage 3 - Top": [], "Stage 4 - Declining": []}

# NEW
from concurrent.futures import ThreadPoolExecutor
stages = {"Stage 1 - Basing": [], "Stage 2 - Advancing": [], "Stage 3 - Top": [], "Stage 4 - Declining": []}

# (Remove first declaration)
```

### Change 9: Weinstein Scanner (Lines 1035-1040)
```python
# OLD
for k in stages.keys():
    if k.split(" - ")[0] in stage_name:
        stages[k].append(res)
        break

# NEW
stage_mapping = {
    "Stage 1": "Stage 1 - Basing",
    "Stage 2": "Stage 2 - Advancing",
    "Stage 3": "Stage 3 - Top",
    "Stage 4": "Stage 4 - Declining"
}

for stage_key, stage_full_name in stage_mapping.items():
    if stage_key in stage_name:
        stages[stage_full_name].append(res)
        break
```

---

## Testing Checklist

### After Swing Scanner Fix
- [ ] Stocks with price 50-100 now included
- [ ] No crashes on NaN values
- [ ] Results consistent across runs

### After SMC Scanner Fix
- [ ] Results show 0-100 score range (not capped at 98)
- [ ] Delivery % shows "N/A" instead of "Est"
- [ ] Volume calculations handle edge cases

### After Cyclical Scanner Fix
- [ ] Uses configurable thresholds
- [ ] Data isn't modified during processing
- [ ] Consistent seasonal patterns

### After Weinstein Scanner Fix
- [ ] No duplicate dictionary
- [ ] Stage matching is reliable
- [ ] All 4 stages properly classified

---

## Monitoring

### Add Logging to `run_all_scanners.py`
```python
import time
from scanner_robustness import ScannerHealthCheck

for name, func in scanners:
    start = time.time()
    results = func(ticker_pool, max_results=50, max_workers=15)
    duration = time.time() - start
    
    health = ScannerHealthCheck.check_result_quality(results)
    ScannerHealthCheck.log_scanner_stats(name, results, duration)
    
    if not health['valid']:
        print(f"⚠️ {name} scanner warning: {health['issues']}")
```

This provides visibility into scanner health and helps detect issues early.
