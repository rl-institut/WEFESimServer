import pandas as pd
import numpy as np
import json
import math

def df_to_records(df: pd.DataFrame):
    # reset_index so index isn't lost (important for your 'kpis' table)
    return df.reset_index().to_dict(orient="records")

def to_jsonable(obj):
    # pandas / numpy scalars
    if isinstance(obj, (np.integer, np.int64)):
        return int(obj)
    if isinstance(obj, (np.floating, np.float64)):
        x = float(obj)
        if math.isfinite(x):
            return x
        return None
    if isinstance(obj, float):
        if math.isfinite(obj):
            return obj
        return None
    if isinstance(obj, (pd.Timestamp,)):
        return obj.isoformat()

    # containers
    if isinstance(obj, pd.DataFrame):
        return df_to_records(obj)
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]

    return obj
