from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass

from .series import DEFAULT_DISCRETE_COLUMNS, DEFAULT_NS_COLUMNS, RATE_MATURITY_MONTHS


@dataclass
class NelsonSiegelResult:
    betas: pd.DataFrame
    observed: pd.DataFrame
    fitted: pd.DataFrame
    lambda_value: float


@dataclass
class DiscreteNelsonSiegelResult:
    phi: float
    monthly_betas: pd.DataFrame
    observed_monthly: pd.DataFrame
    reconstructed_curve: pd.DataFrame
    phi_summary: pd.DataFrame


def prepare_rates_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    prepared = df.copy()
    if "Date" not in prepared.columns:
        raise ValueError("El archivo debe incluir una columna 'Date'.")

    prepared["Date"] = pd.to_datetime(prepared["Date"], errors="coerce")
    prepared = prepared.dropna(subset=["Date"]).sort_values("Date")

    rate_columns = [column for column in prepared.columns if column != "Date"]
    for column in rate_columns:
        prepared[column] = pd.to_numeric(prepared[column], errors="coerce")

    if not rate_columns:
        raise ValueError("El archivo debe incluir al menos una columna de tasas.")

    prepared = prepared.dropna(subset=rate_columns, how="any")
    if prepared.empty:
        raise ValueError("No quedaron filas completas después de eliminar NA en las columnas de tasas.")

    return prepared.reset_index(drop=True)


def build_demo_dataset() -> pd.DataFrame:
    dates = pd.date_range("2018-01-01", "2024-12-01", freq="MS")
    months = np.array([RATE_MATURITY_MONTHS[column] for column in DEFAULT_DISCRETE_COLUMNS], dtype=float)
    rows = []

    for index, date in enumerate(dates):
        cycle = np.sin(index / 7.5)
        level = 3.2 + 1.5 * cycle
        slope = -1.4 + 0.9 * np.cos(index / 10.0)
        curvature = 0.25 * np.sin(index / 5.0)
        phi = 0.93
        load2 = discrete_lambda2(months, phi)
        load3 = discrete_lambda3(months, phi)
        values = level + slope * load2 + curvature * load3

        row = {"Date": date}
        for column, value in zip(DEFAULT_DISCRETE_COLUMNS, values):
            row[column] = round(float(value), 4)
        rows.append(row)

    return pd.DataFrame(rows)


def discrete_lambda2(months: np.ndarray, phi: float) -> np.ndarray:
    return (1.0 / months) * ((1.0 - phi**months) / (1.0 - phi))


def discrete_lambda3(months: np.ndarray, phi: float) -> np.ndarray:
    load2 = discrete_lambda2(months, phi)
    return load2 - months * phi ** (months - 1.0)


def nelson_siegel_loadings(tau_years: np.ndarray, lambda_value: float) -> np.ndarray:
    level = np.ones(len(tau_years))
    slope = (1.0 - np.exp(-lambda_value * tau_years)) / (lambda_value * tau_years)
    curvature = slope - np.exp(-lambda_value * tau_years)
    return np.column_stack([level, slope, curvature])


def reconstruct_nelson_siegel_curve(
    tau_years: np.ndarray,
    betas_row: pd.Series,
    lambda_value: float,
) -> np.ndarray:
    loadings = nelson_siegel_loadings(tau_years, lambda_value)
    beta_vector = betas_row[["level", "slope", "curvature"]].to_numpy(dtype=float)
    return loadings @ beta_vector


def fit_nelson_siegel(
    df: pd.DataFrame,
    columns: list[str] | None = None,
    lambda_value: float = 0.0609,
) -> NelsonSiegelResult:
    columns = columns or DEFAULT_NS_COLUMNS
    columns = sorted(columns, key=lambda column: RATE_MATURITY_MONTHS[column])
    observed = df[["Date", *columns]].dropna().copy()
    if observed.empty:
        raise ValueError("No hay suficientes datos completos para ajustar Nelson-Siegel.")

    tau_years = np.array([RATE_MATURITY_MONTHS[column] / 12.0 for column in columns], dtype=float)
    loadings = nelson_siegel_loadings(tau_years, lambda_value)

    betas = []
    fitted_rows = []
    for _, row in observed.iterrows():
        rates = row[columns].to_numpy(dtype=float)
        beta = np.linalg.lstsq(loadings, rates, rcond=None)[0]
        fitted = loadings @ beta
        betas.append(
            {
                "Date": row["Date"],
                "level": beta[0],
                "slope": beta[1],
                "curvature": beta[2],
            }
        )
        fitted_rows.append({"Date": row["Date"], **dict(zip(columns, fitted))})

    return NelsonSiegelResult(
        betas=pd.DataFrame(betas),
        observed=observed,
        fitted=pd.DataFrame(fitted_rows),
        lambda_value=lambda_value,
    )


def _long_rates(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    long_df = df[["Date", *columns]].melt(
        id_vars="Date",
        var_name="Tipo_Tasa",
        value_name="Valor_Tasa",
    )
    long_df["n"] = long_df["Tipo_Tasa"].map(RATE_MATURITY_MONTHS)
    long_df = long_df.dropna(subset=["n"])
    long_df["DateM"] = long_df["Date"].dt.to_period("M").dt.to_timestamp()
    return long_df.dropna(subset=["Valor_Tasa"]).sort_values(["DateM", "n"]).reset_index(drop=True)


def _fit_cross_section(y: np.ndarray, load2: np.ndarray, load3: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    design = np.column_stack([np.ones(len(y)), load2, load3])
    beta = np.linalg.lstsq(design, y, rcond=None)[0]
    fitted = design @ beta
    return beta, fitted


def fit_discrete_nelson_siegel(
    df: pd.DataFrame,
    columns: list[str] | None = None,
    phi: float | None = None,
    phi_grid: np.ndarray | None = None,
) -> DiscreteNelsonSiegelResult:
    columns = columns or DEFAULT_DISCRETE_COLUMNS
    long_df = _long_rates(df, columns)
    if long_df.empty:
        raise ValueError("No hay datos suficientes para ajustar el modelo discreto.")

    monthly = (
        long_df.groupby(["DateM", "Tipo_Tasa", "n"], as_index=False)["Valor_Tasa"]
        .mean()
        .sort_values(["DateM", "n"])
    )

    phi_grid = phi_grid if phi_grid is not None else np.round(np.arange(0.10, 0.99, 0.01), 2)
    summary_rows = []
    if phi is None:
        for candidate_phi in phi_grid:
            monthly_errors = []
            for _, group in monthly.groupby("DateM"):
                if len(group) < 3:
                    continue
                load2 = discrete_lambda2(group["n"].to_numpy(dtype=float), candidate_phi)
                load3 = discrete_lambda3(group["n"].to_numpy(dtype=float), candidate_phi)
                _, fitted = _fit_cross_section(group["Valor_Tasa"].to_numpy(dtype=float), load2, load3)
                mse = np.mean((group["Valor_Tasa"].to_numpy(dtype=float) - fitted) ** 2)
                monthly_errors.append(mse)
            if monthly_errors:
                summary_rows.append(
                    {
                        "phi": candidate_phi,
                        "avg_mse": float(np.mean(monthly_errors)),
                        "months_used": len(monthly_errors),
                    }
                )

        phi_summary = pd.DataFrame(summary_rows).sort_values("avg_mse").reset_index(drop=True)
        if phi_summary.empty:
            raise ValueError("No se pudo calibrar phi con los datos disponibles.")
        phi = float(phi_summary.iloc[0]["phi"])
    else:
        phi_summary = pd.DataFrame(columns=["phi", "avg_mse", "months_used"])

    beta_rows = []
    observed_rows = []
    reconstructed_rows = []
    curve_months = np.arange(1, 121, dtype=float)
    full_load2 = discrete_lambda2(curve_months, phi)
    full_load3 = discrete_lambda3(curve_months, phi)

    for date_m, group in monthly.groupby("DateM"):
        if len(group) < 3:
            continue
        months = group["n"].to_numpy(dtype=float)
        load2 = discrete_lambda2(months, phi)
        load3 = discrete_lambda3(months, phi)
        beta, fitted = _fit_cross_section(group["Valor_Tasa"].to_numpy(dtype=float), load2, load3)
        beta_rows.append(
            {
                "DateM": date_m,
                "Beta_Constante": beta[0],
                "Beta_lambda2": beta[1],
                "Beta_lambda3": beta[2],
            }
        )
        for observed_value, maturity, rate_name, fitted_value in zip(
            group["Valor_Tasa"].to_numpy(dtype=float),
            months,
            group["Tipo_Tasa"],
            fitted,
        ):
            observed_rows.append(
                {
                    "DateM": date_m,
                    "Tipo_Tasa": rate_name,
                    "n": maturity,
                    "Valor_Tasa": observed_value,
                    "Valor_Ajustado": fitted_value,
                }
            )

        reconstructed = beta[0] + beta[1] * full_load2 + beta[2] * full_load3
        for maturity, estimated_rate in zip(curve_months, reconstructed):
            reconstructed_rows.append(
                {
                    "DateM": date_m,
                    "n": int(maturity),
                    "Tasa_Estimada": float(estimated_rate),
                }
            )

    return DiscreteNelsonSiegelResult(
        phi=float(phi),
        monthly_betas=pd.DataFrame(beta_rows).sort_values("DateM").reset_index(drop=True),
        observed_monthly=pd.DataFrame(observed_rows).sort_values(["DateM", "n"]).reset_index(drop=True),
        reconstructed_curve=pd.DataFrame(reconstructed_rows).sort_values(["DateM", "n"]).reset_index(drop=True),
        phi_summary=phi_summary,
    )


def reconstruct_discrete_curve(phi: float, beta_const: float, beta_lambda2: float, beta_lambda3: float) -> pd.DataFrame:
    months = np.arange(1, 121, dtype=float)
    curve = beta_const + beta_lambda2 * discrete_lambda2(months, phi) + beta_lambda3 * discrete_lambda3(months, phi)
    return pd.DataFrame({"n": months.astype(int), "Tasa_Estimada": curve})
