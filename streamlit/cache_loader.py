import json
import re
import urllib.error
import urllib.request

import streamlit as st

CACHE_BASE_URL = "https://rockborne-advance-group-2.s3.us-east-1.amazonaws.com/parsed_cache"

PROFILE_SLUG = {
    "Balanced investor": "balanced_investor",
    "Revenue focused": "revenue_focused",
    "Risk focused": "risk_focused",
}

# Module-level log of recent lookups, for the sidebar debug panel in main.py.
# Carries the real failure detail (exception type, HTTP status, message), not
# just a bare hit/miss label, since a 403, a DNS failure, a timeout, and a
# genuine 404 are distinct failure modes with different fixes.
_LOOKUP_LOG: list[dict] = []
_LOOKUP_LOG_MAX = 50


def get_last_lookups() -> list[dict]:
    return list(_LOOKUP_LOG)


def _log_lookup(feature: str, item_key: str, status: str, detail: str = ""):
    _LOOKUP_LOG.append({"feature": feature, "key": item_key, "status": status, "detail": detail})
    del _LOOKUP_LOG[:-_LOOKUP_LOG_MAX]


def _slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return re.sub(r"_+", "_", value).strip("_")


def _make_key(*parts: str) -> str:
    return "__".join(_slugify(p) for p in parts)


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_json_cached(feature: str, item_key: str) -> dict:
    """
    Only ever called on a successful fetch — st.cache_data does not cache a
    raised exception, so a failure always retries on the next call instead of
    getting stuck as a cached negative result.
    """
    url = f"{CACHE_BASE_URL}/{feature}/{item_key}.json"
    with urllib.request.urlopen(url, timeout=5) as resp:
        raw = resp.read()
        return json.loads(raw)


def _fetch_json(feature: str, item_key: str) -> tuple[dict | None, str, str]:
    """
    Returns (payload_or_None, status, detail).
    status is one of: "hit", "not_found" (real 404/403 — object genuinely
    absent or access denied), "http_error" (any other HTTP status — 5xx,
    redirect loop, etc.), "network_error" (DNS/connection/SSL/timeout — the
    request never got a real HTTP response at all), "parse_error" (got a
    response, but it wasn't valid JSON).
    detail is the real exception text, populated on failure.
    """
    url = f"{CACHE_BASE_URL}/{feature}/{item_key}.json"
    try:
        payload = _fetch_json_cached(feature, item_key)
        return payload, "hit", ""
    except urllib.error.HTTPError as e:
        if e.code in (403, 404):
            return None, "not_found", f"HTTP {e.code} at {url}"
        return None, "http_error", f"HTTP {e.code}: {e.reason} at {url}"
    except urllib.error.URLError as e:
        return None, "network_error", f"{type(e.reason).__name__ if e.reason else 'URLError'}: {e.reason} at {url}"
    except TimeoutError:
        return None, "network_error", f"Timed out after 5s at {url}"
    except json.JSONDecodeError as e:
        return None, "parse_error", f"Invalid JSON ({e}) at {url}"


def _normalize_json_payload(item: dict | None, required_keys: tuple[str, ...]) -> dict | None:
    """
    Handles the case where a Feature 3/4 object was written wrapped as
    {"text": "<json string>"} instead of the parsed object directly.
    Returns None if the payload can't be made to match required_keys at all.
    """
    if item is None:
        return None
    if not isinstance(item, dict):
        return None

    if all(k in item for k in required_keys):
        return item

    if "text" in item and isinstance(item["text"], str):
        try:
            inner = json.loads(item["text"])
        except json.JSONDecodeError:
            return None
        if isinstance(inner, dict) and all(k in inner for k in required_keys):
            return inner

    return None


def get_borough_recommendation(city: str, borough: str, profile_label: str) -> str | None:
    profile = PROFILE_SLUG.get(profile_label, _slugify(profile_label))
    key = _make_key(city, borough, profile)
    item, status, detail = _fetch_json("borough_recommendation", key)
    # .get(), not item["text"] — a fetched object with an unexpected shape
    # must never raise here, since this runs early enough (inside
    # compute_lad_tables) to halt the whole script if it did.
    text = item.get("text") if isinstance(item, dict) else None
    if status == "hit" and text is None:
        status, detail = "malformed", f"fetched OK but no 'text' key. Raw keys: {list(item.keys()) if isinstance(item, dict) else type(item)}"
    _log_lookup("borough_recommendation", key, status, detail)
    return text


def get_property_type_recommendation(property_type: str, profile_label: str) -> str | None:
    profile = PROFILE_SLUG.get(profile_label, _slugify(profile_label))
    key = _make_key(property_type, profile)
    item, status, detail = _fetch_json("property_type_recommendation", key)
    text = item.get("text") if isinstance(item, dict) else None
    if status == "hit" and text is None:
        status, detail = "malformed", f"fetched OK but no 'text' key. Raw keys: {list(item.keys()) if isinstance(item, dict) else type(item)}"
    _log_lookup("property_type_recommendation", key, status, detail)
    return text


def get_review_summary(city: str, borough: str) -> dict | None:
    key = _make_key(city, borough)
    item, status, detail = _fetch_json("review_summary", key)
    result = _normalize_json_payload(item, ("summary", "investment_signal"))
    if status == "hit" and result is None:
        status, detail = "malformed", f"fetched OK but schema didn't match. Raw keys: {list(item.keys()) if isinstance(item, dict) else type(item)}"
    _log_lookup("review_summary", key, status, detail)
    return result


def get_sentiment(city: str, borough: str) -> dict | None:
    key = _make_key(city, borough)
    item, status, detail = _fetch_json("sentiment_analysis", key)
    result = _normalize_json_payload(item, ("positive_themes", "negative_themes"))
    if status == "hit" and result is None:
        status, detail = "malformed", f"fetched OK but schema didn't match. Raw keys: {list(item.keys()) if isinstance(item, dict) else type(item)}"
    _log_lookup("sentiment_analysis", key, status, detail)
    return result
