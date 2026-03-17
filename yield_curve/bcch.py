from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from .series import RATE_SERIES


def fetch_bcch_series(
    series_keys: list[str],
    user: str,
    password: str,
    start_date: str,
    end_date: str,
    workers: int = 8,
) -> pd.DataFrame:
    if not user or not password:
        raise ValueError("Debes ingresar usuario y contraseña de BCCh.")

    import bcchapi

    siete = bcchapi.Siete(user, password)

    def download_one(key: str) -> pd.DataFrame:
        if key not in RATE_SERIES:
            raise ValueError(f"Serie desconocida: {key}")

        series = RATE_SERIES[key]
        return siete.cuadro(
            series=[series.code],
            nombres=[key],
            desde=start_date,
            hasta=end_date,
        )

    with ThreadPoolExecutor(max_workers=workers) as executor:
        frames = list(executor.map(download_one, series_keys))

    if not frames:
        raise ValueError("BCCh no devolvió datos para las series solicitadas.")

    merged = pd.concat(frames, axis=1)
    merged.index = pd.to_datetime(merged.index, errors="coerce")
    merged = merged.reset_index().rename(columns={"index": "Date"})
    merged["Date"] = pd.to_datetime(merged["Date"], errors="coerce")
    return merged.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
