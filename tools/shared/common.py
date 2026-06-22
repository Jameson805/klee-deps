import json
import logging
from typing import Any

import pandas as pd

_BIGINT_HEX_PREFIX = "__combined_json_bigint_hex__:"
# Python's decimal int<->str guardrail trips around 4300 digits; encode well before that.
_BIGINT_HEX_THRESHOLD_BITS = 4096


def _decode_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _decode_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_decode_json_value(item) for item in value]
    if isinstance(value, str) and value.startswith(_BIGINT_HEX_PREFIX):
        payload = value[len(_BIGINT_HEX_PREFIX):]
        negative = payload.startswith("-")
        if negative:
            payload = payload[1:]
        if not payload:
            return value
        try:
            decoded = int(payload, 16)
        except ValueError:
            return value
        return -decoded if negative else decoded
    return value


def _encode_json_value(value: Any) -> Any:
    if value is pd.NA:
        return None
    if isinstance(value, dict):
        return {str(key): _encode_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_encode_json_value(item) for item in value]
    item_method = getattr(value, "item", None)
    if callable(item_method):
        try:
            value = item_method()
        except Exception:
            pass
    if isinstance(value, int) and not isinstance(value, bool):
        if abs(value).bit_length() > _BIGINT_HEX_THRESHOLD_BITS:
            sign = "-" if value < 0 else ""
            return f"{_BIGINT_HEX_PREFIX}{sign}{format(abs(value), 'x')}"
        return value
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    return value

def load_combined_json(input_json: str) -> pd.DataFrame:
    """Load the combined comparison JSON produced by the tool converters.

    Support two forms:
      - A dict with keys {"data": [...], "dtypes": {...}}
      - A plain records-orient JSON array
    """
    with open(input_json, "r") as f:
        obj = _decode_json_value(json.load(f))

    if isinstance(obj, dict) and "data" in obj:
        df = pd.DataFrame(obj["data"])
        metadata = obj.get("metadata")
        if isinstance(metadata, dict):
            df.attrs["metadata"] = metadata
        notes = obj.get("notes")
        if isinstance(notes, dict):
            df.attrs["notes"] = notes
        dtypes = obj.get("dtypes", {})
        for col, dtype in dtypes.items():
            if col in df.columns:
                try:
                    df[col] = df[col].astype(dtype)
                except Exception:
                    logging.debug("failed to cast column %s to %s", col, dtype)
    else:
        df = pd.DataFrame(obj)

    return df

def save_combined_json(df: pd.DataFrame, output_json: str) -> None:
    """Save both data and dtypes so consumers can restore original pandas dtypes"""
    data = _encode_json_value(df.to_dict(orient="records"))
    dtypes = df.dtypes.astype(str).to_dict()

    out_obj = {
        "data": data,
        "dtypes": dtypes
    }
    metadata = df.attrs.get("metadata")
    if isinstance(metadata, dict):
        out_obj["metadata"] = _encode_json_value(metadata)
    notes = df.attrs.get("notes")
    if isinstance(notes, dict):
        out_obj["notes"] = _encode_json_value(notes)

    with open(output_json, "w") as f:
        json.dump(out_obj, f, indent=2)

