from collections import OrderedDict

# Define canonical columns per scanner and mappings from variant keys
CANONICAL_COLUMNS = {
    'swing': [
        'Stock Symbol', 'Current Price', 'Entry Range', 'Target Price (15–20 day horizon)',
        'Stop Loss', 'Trend Type (Uptrend / Range Breakout)', 'Technical Reason (short explanation)',
        'Confidence Score (0–100)', 'pct_change'
    ],
    'smc': [
        'Stock Symbol', 'Current Price', 'Signal Type (Accumulation / Breakout / Absorption / Re-accumulation)',
        'Volume Spike %', 'Delivery %', 'Institutional Activity (Yes/No + short note)',
        'Smart Money Score (0–100)', 'Signal Strength (Weak / Moderate / Strong)'
    ],
    'long_term': [
        'Stock Symbol', 'Sector', 'Market Cap', 'Revenue Growth %', 'Profit Growth %', 'ROE %', 'Debt to Equity',
        'Long-Term Thesis (1–2 line summary)'
    ],
    'cyclical': [
        'Stock Symbol', 'Sector', 'Quarter', 'Probabilistic Consistency (%)', 'Historical Median Return (%)', 'Score'
    ],
    'stage_analysis': [
        'Stock Symbol', 'Price', 'RS', 'Action'
    ]
}

# Known variant key mappings to canonical names
KEY_MAP = {
    # swing variants
    'Confidence Score (0–100)': 'Confidence Score (0–100)',
    'Confidence Score': 'Confidence Score (0–100)',
    'Score': 'Smart Money Score (0–100)',
    'Smart Money Score (0–100)': 'Smart Money Score (0–100)',

    # smc variants
    'Smart Money Score (0–100)': 'Smart Money Score (0–100)',
    'Signal Strength': 'Signal Strength (Weak / Moderate / Strong)',
    'Signal Strength (Weak / Moderate / Strong)': 'Signal Strength (Weak / Moderate / Strong)',

    # generic mappings
    'Target Price': 'Target Price (15–20 day horizon)'
}


def normalize_scanner_results(scanner_key, results):
    """Normalize a list of result dicts for consistent display.

    - Adds missing canonical keys with None
    - Maps variant keys to canonical names
    - Preserves ordering from CANONICAL_COLUMNS
    - Drops columns that are entirely None across all rows (keeps consistency between live/store)

    Args:
        scanner_key (str): one of 'swing','smc','long_term','cyclical','stage_analysis'
        results (list[dict]): list of result dicts

    Returns:
        list[OrderedDict]: normalized rows ready for DataFrame
    """
    if not results:
        return []

    scanner = scanner_key.lower()
    canonical_cols = CANONICAL_COLUMNS.get(scanner, None)

    # Normalize each entry keys via KEY_MAP
    norm_rows = []
    for r in results:
        new_r = {}
        # First copy mapped keys
        for k, v in r.items():
            target = KEY_MAP.get(k, k)
            new_r[target] = v
        norm_rows.append(new_r)

    # Ensure all canonical columns present
    if canonical_cols:
        ordered_rows = []
        for r in norm_rows:
            od = OrderedDict()
            for col in canonical_cols:
                od[col] = r.get(col, None)
            # Also keep any additional keys at the end to avoid data loss
            for extra_k, extra_v in r.items():
                if extra_k not in od:
                    od[extra_k] = extra_v
            ordered_rows.append(od)

        # Drop columns that are entirely None
        # Compute columns to keep
        cols = list(ordered_rows[0].keys())
        keep = []
        for c in cols:
            any_val = any(row.get(c) not in (None, '', []) for row in ordered_rows)
            if any_val:
                keep.append(c)
        # Return pruned rows
        pruned = []
        for row in ordered_rows:
            od = OrderedDict()
            for c in keep:
                od[c] = row.get(c)
            pruned.append(od)
        return pruned

    # Fallback: just return original rows as OrderedDicts
    out = []
    for r in norm_rows:
        out.append(OrderedDict(sorted(r.items())))
    return out
