from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

import numpy as np
import pandas as pd
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from yield_curve import (
    DEFAULT_NS_COLUMNS,
    RATE_SERIES,
    fetch_bcch_series,
    fit_nelson_siegel,
    fit_svensson,
    normalize_rates_dataframe,
    reconstruct_cubic_spline_curve,
    reconstruct_nelson_siegel_curve,
    reconstruct_svensson_curve,
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DATA_FILE = DATA_DIR / "market_rates.csv"
META_FILE = DATA_DIR / "market_meta.json"

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app = FastAPI(title="Yield Curve Public API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEFAULT_COLUMNS = DEFAULT_NS_COLUMNS.copy()
CALCULATION_CACHE: dict[str, dict] = {}
MARKET_STATE: dict[str, object] = {
    "rates_df": pd.DataFrame(),
    "meta": None,
}


class RefreshRequest(BaseModel):
    user: str
    password: str
    start_date: str = "2005-01-01"
    columns: list[str] = Field(default_factory=lambda: DEFAULT_COLUMNS.copy())


class PublicCurveRequest(BaseModel):
    model: str = Field(pattern="^(nelson-siegel|svensson|cubic-spline)$")
    columns: list[str] = Field(default_factory=lambda: DEFAULT_COLUMNS.copy())
    lambda_value: float = 0.0609
    lambda1: float = 0.0609
    lambda2: float = 0.20


class PlotRequest(BaseModel):
    calc_id: str
    curve_dates: list[str] = Field(default_factory=list)


def _sort_columns(columns: list[str]) -> list[str]:
    try:
        return sorted(columns, key=lambda column: RATE_SERIES[column].months)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"Serie desconocida: {exc.args[0]}") from exc


def _latest_available_date(df: pd.DataFrame) -> str:
    if "Date" not in df.columns or df.empty:
        raise HTTPException(status_code=400, detail="No hay datos cargados.")
    last_date = pd.to_datetime(df["Date"], errors="coerce").dropna().max()
    if pd.isna(last_date):
        raise HTTPException(status_code=400, detail="No se pudo determinar la ultima fecha disponible.")
    return last_date.strftime("%Y-%m-%d")


def _require_admin_token(x_admin_token: str | None) -> None:
    configured = os.getenv("PUBLIC_API_ADMIN_TOKEN", "").strip()
    if not configured:
        return
    if x_admin_token != configured:
        raise HTTPException(status_code=401, detail="Token de administrador invalido.")


def _save_market_state(rates_df: pd.DataFrame, meta: dict) -> None:
    to_save = rates_df.copy()
    to_save["Date"] = pd.to_datetime(to_save["Date"], errors="coerce").dt.strftime("%Y-%m-%d")
    to_save.to_csv(DATA_FILE, index=False)
    META_FILE.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    MARKET_STATE["rates_df"] = rates_df
    MARKET_STATE["meta"] = meta


def _load_market_state() -> None:
    if not DATA_FILE.exists():
        MARKET_STATE["rates_df"] = pd.DataFrame()
        MARKET_STATE["meta"] = None
        return

    rates_df = pd.read_csv(DATA_FILE)
    rates_df = normalize_rates_dataframe(rates_df)
    meta = None
    if META_FILE.exists():
        meta = json.loads(META_FILE.read_text(encoding="utf-8"))
    else:
        meta = {
            "start_date": str(rates_df["Date"].min().date()) if not rates_df.empty else None,
            "end_date": _latest_available_date(rates_df) if not rates_df.empty else None,
            "raw_row_count": int(len(rates_df)),
            "rows_used": int(len(rates_df)),
            "removed_rows": 0,
            "columns": [column for column in rates_df.columns if column != "Date"],
            "available_dates": rates_df["Date"].drop_duplicates().sort_values().dt.strftime("%Y-%m-%d").tolist(),
        }
    MARKET_STATE["rates_df"] = rates_df
    MARKET_STATE["meta"] = meta


def _require_market_data() -> tuple[pd.DataFrame, dict]:
    rates_df = MARKET_STATE.get("rates_df")
    meta = MARKET_STATE.get("meta")
    if rates_df is None or not isinstance(rates_df, pd.DataFrame) or rates_df.empty or not meta:
        raise HTTPException(status_code=404, detail="No hay base cargada en el backend. Primero ejecuta el refresh privado.")
    return rates_df, meta


def _available_dates_for_calculation(calculation: dict) -> list[str]:
    model = calculation["model"]
    rates_df: pd.DataFrame = calculation["rates_df"]
    columns: list[str] = calculation["columns"]

    if model == "nelson-siegel":
        return calculation["result"].observed["Date"].drop_duplicates().sort_values().dt.strftime("%Y-%m-%d").tolist()
    if model == "svensson":
        return calculation["result"].observed["Date"].drop_duplicates().sort_values().dt.strftime("%Y-%m-%d").tolist()

    working = rates_df[["Date", *columns]].dropna().copy()
    return working["Date"].drop_duplicates().sort_values().dt.strftime("%Y-%m-%d").tolist()


def _curve_payload_for_dates(calculation: dict, curve_dates: list[str]) -> tuple[list[dict], list[dict]]:
    rates_df: pd.DataFrame = calculation["rates_df"]
    columns: list[str] = calculation["columns"]
    model: str = calculation["model"]
    lambda_value: float = calculation["lambda_value"]
    lambda1: float = calculation["lambda1"]
    lambda2: float = calculation["lambda2"]
    columns = _sort_columns(columns)
    maturities = np.array([RATE_SERIES[column].months for column in columns], dtype=float)
    curve_months = np.arange(int(maturities.min()), int(maturities.max()) + 1, dtype=float)

    available_dates = _available_dates_for_calculation(calculation)
    if not curve_dates:
        curve_dates = available_dates[-1:]

    missing_dates = [date for date in curve_dates if date not in available_dates]
    if missing_dates:
        raise HTTPException(status_code=400, detail=f"Fechas fuera del rango cargado: {', '.join(missing_dates)}")

    if model == "nelson-siegel":
        result = calculation["result"]
        factor_names = ["level", "slope", "curvature"]
        curves = []
        for date_label in curve_dates:
            date_value = pd.Timestamp(date_label)
            observed_row = result.observed.loc[result.observed["Date"] == date_value].iloc[-1]
            beta_row = result.betas.loc[result.betas["Date"] == date_value].iloc[-1]
            estimated = reconstruct_nelson_siegel_curve(curve_months / 12.0, beta_row, lambda_value)
            curves.append(
                {
                    "date": date_label,
                    "curve_months": curve_months.astype(int).tolist(),
                    "estimated": [float(value) for value in estimated],
                    "observed_months": maturities.astype(int).tolist(),
                    "observed": [float(observed_row[column]) for column in columns],
                }
            )

        factor_df = result.betas.copy()
        factor_df["Date"] = factor_df["Date"].dt.strftime("%Y-%m-%d")
        factors = [
            {
                "name": factor_name,
                "dates": factor_df["Date"].tolist(),
                "values": factor_df[factor_name].astype(float).tolist(),
            }
            for factor_name in factor_names
        ]
        return curves, factors

    if model == "svensson":
        result = calculation["result"]
        factor_names = ["level", "slope", "curvature_1", "curvature_2"]
        curves = []
        for date_label in curve_dates:
            date_value = pd.Timestamp(date_label)
            observed_row = result.observed.loc[result.observed["Date"] == date_value].iloc[-1]
            beta_row = result.betas.loc[result.betas["Date"] == date_value].iloc[-1]
            estimated = reconstruct_svensson_curve(curve_months / 12.0, beta_row, lambda1, lambda2)
            curves.append(
                {
                    "date": date_label,
                    "curve_months": curve_months.astype(int).tolist(),
                    "estimated": [float(value) for value in estimated],
                    "observed_months": maturities.astype(int).tolist(),
                    "observed": [float(observed_row[column]) for column in columns],
                }
            )

        factor_df = result.betas.copy()
        factor_df["Date"] = factor_df["Date"].dt.strftime("%Y-%m-%d")
        factors = [
            {
                "name": factor_name,
                "dates": factor_df["Date"].tolist(),
                "values": factor_df[factor_name].astype(float).tolist(),
            }
            for factor_name in factor_names
        ]
        return curves, factors

    working = rates_df[["Date", *columns]].dropna().copy()
    curves = []
    for date_label in curve_dates:
        date_value = pd.Timestamp(date_label)
        observed_row = working.loc[working["Date"] == date_value].iloc[-1]
        observed_values = np.array([observed_row[column] for column in columns], dtype=float)
        estimated = reconstruct_cubic_spline_curve(maturities, observed_values, curve_months)
        curves.append(
            {
                "date": date_label,
                "curve_months": curve_months.astype(int).tolist(),
                "estimated": [float(value) for value in estimated],
                "observed_months": maturities.astype(int).tolist(),
                "observed": [float(value) for value in observed_values],
            }
        )

    return curves, []


@app.on_event("startup")
def startup_load_state() -> None:
    _load_market_state()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "default_columns": DEFAULT_COLUMNS,
        },
    )


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/api/market/status")
async def market_status() -> dict:
    rates_df, meta = _require_market_data()
    sample_rows = rates_df.head(100).copy()
    sample_rows["Date"] = sample_rows["Date"].dt.strftime("%Y-%m-%d")
    return {
        "meta": {
            **meta,
            "available_dates": rates_df["Date"].drop_duplicates().sort_values().dt.strftime("%Y-%m-%d").tolist(),
            "sample_rows": sample_rows.to_dict(orient="records"),
        }
    }


@app.post("/api/admin/refresh")
async def admin_refresh(payload: RefreshRequest, x_admin_token: str | None = Header(default=None)) -> dict:
    _require_admin_token(x_admin_token)
    try:
        raw_df = fetch_bcch_series(
            series_keys=payload.columns,
            user=payload.user,
            password=payload.password,
            start_date=payload.start_date,
            end_date="2099-12-31",
        )
        rates_df = normalize_rates_dataframe(raw_df)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    sorted_columns = _sort_columns(payload.columns)
    available_dates = rates_df["Date"].drop_duplicates().sort_values().dt.strftime("%Y-%m-%d").tolist()
    meta = {
        "start_date": payload.start_date,
        "end_date": _latest_available_date(rates_df),
        "raw_row_count": int(len(raw_df)),
        "rows_used": int(len(rates_df)),
        "removed_rows": int(raw_df["Date"].isna().sum()),
        "columns": sorted_columns,
        "available_dates": available_dates,
        "last_refresh_utc": pd.Timestamp.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
    }
    _save_market_state(rates_df, meta)
    return {"ok": True, "meta": meta}


@app.post("/api/calculate")
async def calculate(payload: PublicCurveRequest) -> dict:
    rates_df, _ = _require_market_data()
    columns = _sort_columns(payload.columns)
    try:
        if payload.model == "nelson-siegel":
            result = fit_nelson_siegel(rates_df, columns=columns, lambda_value=payload.lambda_value)
        elif payload.model == "svensson":
            result = fit_svensson(
                rates_df,
                columns=columns,
                lambda1_value=payload.lambda1,
                lambda2_value=payload.lambda2,
            )
        else:
            result = None
            working = rates_df[["Date", *columns]].dropna().copy()
            if working.empty:
                raise ValueError("No hay suficientes datos completos para cubic spline.")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    calc_id = uuid4().hex
    calculation = {
        "model": payload.model,
        "rates_df": rates_df,
        "columns": columns,
        "lambda_value": payload.lambda_value,
        "lambda1": payload.lambda1,
        "lambda2": payload.lambda2,
        "result": result,
    }
    CALCULATION_CACHE[calc_id] = calculation

    return {
        "calc_id": calc_id,
        "meta": {
            "model": payload.model,
            "rows_used": int(len(rates_df[["Date", *columns]].dropna())),
            "columns": columns,
            "available_dates": _available_dates_for_calculation(calculation),
        },
    }


@app.post("/api/plot")
async def plot(payload: PlotRequest) -> dict:
    calculation = CALCULATION_CACHE.get(payload.calc_id)
    if not calculation:
        raise HTTPException(status_code=404, detail="No existe el calculo solicitado o ya expiro.")

    curves, factors = _curve_payload_for_dates(calculation, payload.curve_dates)
    return {"curves": curves, "factors": factors}
