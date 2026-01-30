import math
from datetime import datetime, date
try:
    import numpy as _np
except Exception:
    _np = None


def _is_nan(x):
    try:
        return math.isnan(x)
    except Exception:
        return False


def sanitize_for_json(obj):
    """Recursively sanitize Python objects for JSON/JSONB storage.

    - Replaces NaN and +/-Inf with None
    - Converts numpy scalar types to native Python types
    - Converts datetimes/dates to ISO strings
    - Leaves other basic types untouched
    """
    # Primitives
    if obj is None:
        return None

    # Numpy scalar handling
    if _np is not None:
        if isinstance(obj, _np.generic):
            try:
                obj = obj.item()
            except Exception:
                obj = float(obj)

    # Numbers
    if isinstance(obj, float):
        if _is_nan(obj) or math.isinf(obj):
            return None
        return obj

    if isinstance(obj, (int, bool, str)):
        return obj

    # Dates / datetimes
    if isinstance(obj, (datetime, date)):
        try:
            return obj.isoformat()
        except Exception:
            return str(obj)

    # Mapping
    if isinstance(obj, dict):
        return {str(k): sanitize_for_json(v) for k, v in obj.items()}

    # Sequence
    if isinstance(obj, (list, tuple)):
        return [sanitize_for_json(v) for v in obj]

    # Fallback: try to coerce simple numpy arrays
    if _np is not None and isinstance(obj, _np.ndarray):
        try:
            return sanitize_for_json(obj.tolist())
        except Exception:
            return [sanitize_for_json(v) for v in obj]

    # Last resort
    try:
        return str(obj)
    except Exception:
        return None
