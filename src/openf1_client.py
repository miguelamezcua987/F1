import requests
import pandas as pd
from functools import lru_cache

BASE_URL = "https://api.openf1.org/v1"
TIMEOUT = 15


def _get(endpoint: str, params: dict) -> list[dict]:
    resp = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


@lru_cache(maxsize=8)
def get_meetings(year: int) -> pd.DataFrame:
    data = _get("meetings", {"year": year})
    return pd.DataFrame(data)


@lru_cache(maxsize=32)
def get_sessions(meeting_key: int) -> pd.DataFrame:
    data = _get("sessions", {"meeting_key": meeting_key})
    return pd.DataFrame(data)


def get_drivers(session_key: int) -> pd.DataFrame:
    data = _get("drivers", {"session_key": session_key})
    return pd.DataFrame(data)


def get_laps(session_key: int, driver_number: int | None = None) -> pd.DataFrame:
    params: dict = {"session_key": session_key}
    if driver_number is not None:
        params["driver_number"] = driver_number
    data = _get("laps", params)
    df = pd.DataFrame(data)
    if not df.empty and "lap_duration" in df.columns:
        df["lap_duration"] = pd.to_numeric(df["lap_duration"], errors="coerce")
    return df


def get_stints(session_key: int) -> pd.DataFrame:
    data = _get("stints", {"session_key": session_key})
    return pd.DataFrame(data)


def get_position(session_key: int) -> pd.DataFrame:
    data = _get("position", {"session_key": session_key})
    return pd.DataFrame(data)


def get_car_data(session_key: int, driver_number: int) -> pd.DataFrame:
    data = _get("car_data", {"session_key": session_key, "driver_number": driver_number})
    return pd.DataFrame(data)


def is_live_session(session_key: int) -> bool:
    """True if the session is the special 'latest' key or currently active."""
    return session_key == 9999


SESSION_TYPE_MAP = {
    "Practice 1": "FP1",
    "Practice 2": "FP2",
    "Practice 3": "FP3",
    "Qualifying": "Q",
    "Sprint": "S",
    "Sprint Qualifying": "SQ",
    "Race": "R",
}
