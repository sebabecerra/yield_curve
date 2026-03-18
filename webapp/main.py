from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
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
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app = FastAPI(title="Yield Curve Web App")
CALCULATION_CACHE: dict[str, dict] = {}
DATA_CACHE: dict[str, dict] = {}


DEFAULT_DATA_COLUMNS = DEFAULT_NS_COLUMNS.copy()


class LoginRequest(BaseModel):
    user: str
    password: str
    start_date: str
    columns: list[str] = Field(default_factory=lambda: DEFAULT_DATA_COLUMNS.copy())


class CurveRequest(BaseModel):
    data_id: str
    model: str = Field(pattern="^(nelson-siegel|svensson|cubic-spline)$")
    columns: list[str] = Field(default_factory=lambda: DEFAULT_DATA_COLUMNS.copy())
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


def _latest_available_date(raw_df: pd.DataFrame) -> str:
    if "Date" in raw_df.columns:
        last_date = pd.to_datetime(raw_df["Date"], errors="coerce").dropna().max()
        if pd.isna(last_date):
            raise HTTPException(status_code=400, detail="No se pudo determinar la ultima fecha disponible.")
        return last_date.strftime("%Y-%m-%d")
    raise HTTPException(status_code=400, detail="La carga de datos no devolvio columna Date.")


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

    available_dates = rates_df["Date"].drop_duplicates().sort_values()
    available_labels = available_dates.dt.strftime("%Y-%m-%d").tolist()
    if not curve_dates:
        curve_dates = available_labels[-1:]

    missing_dates = [date for date in curve_dates if date not in available_labels]
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

        factors = []
        factor_df = result.betas.copy()
        factor_df["Date"] = factor_df["Date"].dt.strftime("%Y-%m-%d")
        for factor_name in factor_names:
            factors.append(
                {
                    "name": factor_name,
                    "dates": factor_df["Date"].tolist(),
                    "values": factor_df[factor_name].astype(float).tolist(),
                }
            )
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

        factors = []
        factor_df = result.betas.copy()
        factor_df["Date"] = factor_df["Date"].dt.strftime("%Y-%m-%d")
        for factor_name in factor_names:
            factors.append(
                {
                    "name": factor_name,
                    "dates": factor_df["Date"].tolist(),
                    "values": factor_df[factor_name].astype(float).tolist(),
                }
            )
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


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "default_columns": DEFAULT_NS_COLUMNS,
            "rate_series": RATE_SERIES,
        },
    )


@app.post("/api/login")
async def api_login(payload: LoginRequest) -> dict:
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

    data_id = uuid4().hex
    sorted_columns = _sort_columns(payload.columns)
    latest_date = _latest_available_date(rates_df)
    DATA_CACHE[data_id] = {
        "rates_df": rates_df,
        "columns": sorted_columns,
        "latest_date": latest_date,
        "raw_row_count": int(len(raw_df)),
    }

    available_dates = rates_df["Date"].drop_duplicates().sort_values().dt.strftime("%Y-%m-%d").tolist()
    sample_rows = rates_df.head(250).copy()
    sample_rows["Date"] = sample_rows["Date"].dt.strftime("%Y-%m-%d")
    return {
        "data_id": data_id,
        "meta": {
            "start_date": payload.start_date,
            "end_date": latest_date,
            "raw_row_count": int(len(raw_df)),
            "rows_used": int(len(rates_df)),
            "removed_rows": int(raw_df["Date"].isna().sum()),
            "columns": sorted_columns,
            "available_dates": available_dates,
            "sample_rows": sample_rows.to_dict(orient="records"),
        },
    }


@app.get("/api/data/{data_id}/download")
async def api_download_clean_data(data_id: str) -> Response:
    data_bundle = DATA_CACHE.get(data_id)
    if data_bundle is None:
        raise HTTPException(status_code=404, detail="Base de datos no encontrada o expirada.")

    export_df = data_bundle["rates_df"].copy()
    export_df["Date"] = export_df["Date"].dt.strftime("%Y-%m-%d")
    return Response(
        content=export_df.to_csv(index=False).encode("utf-8"),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="rates_input_clean.csv"'},
    )


@app.post("/api/calculate")
async def api_calculate(payload: CurveRequest) -> dict:
    data_bundle = DATA_CACHE.get(payload.data_id)
    if data_bundle is None:
        raise HTTPException(status_code=404, detail="Base de datos no encontrada o expirada.")

    rates_df: pd.DataFrame = data_bundle["rates_df"]
    sorted_columns = _sort_columns(payload.columns)
    try:
        result = None
        if payload.model == "nelson-siegel":
            result = fit_nelson_siegel(rates_df, columns=sorted_columns, lambda_value=payload.lambda_value)
        elif payload.model == "svensson":
            result = fit_svensson(rates_df, columns=sorted_columns, lambda1_value=payload.lambda1, lambda2_value=payload.lambda2)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    calc_id = uuid4().hex
    CALCULATION_CACHE[calc_id] = {
        "rates_df": rates_df,
        "columns": sorted_columns,
        "model": payload.model,
        "lambda_value": payload.lambda_value,
        "lambda1": payload.lambda1,
        "lambda2": payload.lambda2,
        "result": result,
    }

    available_dates = _available_dates_for_calculation(CALCULATION_CACHE[calc_id])
    return {
        "calc_id": calc_id,
        "meta": {
            "model": payload.model,
            "rows_used": int(len(available_dates)),
            "columns": sorted_columns,
            "available_dates": available_dates,
        },
    }


@app.post("/api/plot")
async def api_plot(payload: PlotRequest) -> dict:
    calculation = CALCULATION_CACHE.get(payload.calc_id)
    if calculation is None:
        raise HTTPException(status_code=404, detail="Calculo no encontrado o expirado.")

    try:
        curves, factors = _curve_payload_for_dates(calculation, payload.curve_dates)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    available_dates = _available_dates_for_calculation(calculation)
    return {
        "meta": {
            "model": calculation["model"],
            "rows_used": int(len(available_dates)),
            "columns": calculation["columns"],
            "available_dates": available_dates,
        },
        "curves": curves,
        "factors": factors,
    }
