from __future__ import annotations

from io import StringIO

import pandas as pd
import requests

from .series import RATE_SERIES

BCCH_REST_URL = "https://si3.bcentral.cl/SieteRestWS/SieteRestWS.ashx"


def fetch_bcch_series(
    series_keys: list[str],
    user: str,
    password: str,
    start_date: str,
    end_date: str,
    timeout: int = 30,
) -> pd.DataFrame:
    if not user or not password:
        raise ValueError("Debes ingresar usuario y contraseña de BCCh.")

    frames: list[pd.DataFrame] = []
    for key in series_keys:
        if key not in RATE_SERIES:
            raise ValueError(f"Serie desconocida: {key}")

        response = requests.get(
            BCCH_REST_URL,
            params={
                "user": user,
                "pass": password,
                "firstdate": start_date,
                "lastdate": end_date,
                "timeseries": RATE_SERIES[key].code,
                "function": "GetSeries",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        observations = payload.get("Series", {}).get("Obs", [])
        series_frame = pd.DataFrame(observations)
        if series_frame.empty:
            continue

        date_column = "indexDateString" if "indexDateString" in series_frame.columns else "indexDate"
        value_column = "value"
        normalized = series_frame[[date_column, value_column]].copy()
        normalized.columns = ["Date", key]
        normalized["Date"] = pd.to_datetime(normalized["Date"], errors="coerce")
        normalized[key] = pd.to_numeric(normalized[key], errors="coerce")
        frames.append(normalized.dropna(subset=["Date"]))

    if not frames:
        raise ValueError("BCCh no devolvió datos para las series solicitadas.")

    merged = frames[0]
    for frame in frames[1:]:
        merged = merged.merge(frame, on="Date", how="outer")

    return merged.sort_values("Date").reset_index(drop=True)
