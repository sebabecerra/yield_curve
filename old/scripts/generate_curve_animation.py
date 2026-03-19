from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("MPLCONFIGDIR", str(PROJECT_ROOT / ".matplotlib"))

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv(PROJECT_ROOT / ".env")

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
import numpy as np
import pandas as pd

from yield_curve import (
    DEFAULT_NS_COLUMNS,
    RATE_SERIES,
    fetch_bcch_series,
    fit_nelson_siegel,
    fit_svensson,
    prepare_rates_dataframe,
    reconstruct_cubic_spline_curve,
    reconstruct_nelson_siegel_curve,
    reconstruct_svensson_curve,
)

BLOOMBERG_BG = "#0b0f14"
BLOOMBERG_PANEL = "#11161d"
BLOOMBERG_GRID = "#2a3441"
BLOOMBERG_TEXT = "#d7dde5"
BLOOMBERG_CURVE = "#f5a623"
BLOOMBERG_POINTS = "#ffd166"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Genera un GIF con la evolucion de la curva de tasas.")
    parser.add_argument("--source", choices=["csv", "bcch"], required=True)
    parser.add_argument("--csv-path", help="Ruta al CSV con Date y columnas de tasas.")
    parser.add_argument("--user", default=os.getenv("BCCH_USER"), help="Usuario BCCh o variable BCCH_USER.")
    parser.add_argument(
        "--password",
        default=os.getenv("BCCH_PASSWORD"),
        help="Contrasena BCCh o variable BCCH_PASSWORD.",
    )
    parser.add_argument("--start-date", required=True, help="Fecha inicial YYYY-MM-DD.")
    parser.add_argument("--end-date", required=True, help="Fecha final YYYY-MM-DD.")
    parser.add_argument(
        "--model",
        choices=["nelson-siegel", "svensson", "cubic-spline"],
        default="nelson-siegel",
    )
    parser.add_argument(
        "--columns",
        nargs="+",
        default=DEFAULT_NS_COLUMNS,
        help="Columnas/series a usar. Default: SPC base 2Y,3Y,4Y,5Y,10Y.",
    )
    parser.add_argument("--lambda-value", type=float, default=0.0609)
    parser.add_argument("--lambda1", type=float, default=0.0609)
    parser.add_argument("--lambda2", type=float, default=0.20)
    parser.add_argument("--fps", type=int, default=10)
    parser.add_argument("--step", type=int, default=1, help="Usa cada n-esima fecha para reducir frames.")
    parser.add_argument(
        "--dynamic-y-axis",
        action="store_true",
        help="Ajusta el eje Y en cada frame usando las tasas observadas y estimadas de esa fecha.",
    )
    parser.add_argument(
        "--output",
        default="outputs/curve_evolution.gif",
        help="Ruta del GIF de salida.",
    )
    return parser.parse_args()


def load_rates(args: argparse.Namespace) -> pd.DataFrame:
    if args.source == "csv":
        if not args.csv_path:
            raise ValueError("--csv-path es obligatorio cuando source=csv.")
        raw = pd.read_csv(args.csv_path)
    else:
        if not args.user or not args.password:
            raise ValueError("--user y --password son obligatorios cuando source=bcch.")
        raw = fetch_bcch_series(
            series_keys=args.columns,
            user=args.user,
            password=args.password,
            start_date=args.start_date,
            end_date=args.end_date,
        )

    rates = prepare_rates_dataframe(raw)
    mask = (rates["Date"] >= pd.Timestamp(args.start_date)) & (rates["Date"] <= pd.Timestamp(args.end_date))
    rates = rates.loc[mask].reset_index(drop=True)
    if rates.empty:
        raise ValueError("No quedaron datos en el rango solicitado.")
    return rates


def build_curves(rates_df: pd.DataFrame, args: argparse.Namespace) -> tuple[list[pd.Timestamp], dict[pd.Timestamp, dict[str, np.ndarray]]]:
    columns = sorted(args.columns, key=lambda column: RATE_SERIES[column].months)
    maturities = np.array([RATE_SERIES[column].months for column in columns], dtype=float)
    curve_months = np.arange(int(maturities.min()), int(maturities.max()) + 1, dtype=float)

    dates = rates_df["Date"].drop_duplicates().sort_values().tolist()[:: max(args.step, 1)]
    curves: dict[pd.Timestamp, dict[str, np.ndarray]] = {}

    if args.model == "nelson-siegel":
        result = fit_nelson_siegel(rates_df, columns=columns, lambda_value=args.lambda_value)
        for date in dates:
            observed = result.observed.loc[result.observed["Date"] == date].iloc[-1]
            betas = result.betas.loc[result.betas["Date"] == date].iloc[-1]
            estimated = reconstruct_nelson_siegel_curve(curve_months / 12.0, betas, args.lambda_value)
            curves[date] = {
                "curve_months": curve_months,
                "estimated": estimated,
                "observed_months": maturities,
                "observed": np.array([observed[column] for column in columns], dtype=float),
            }
    elif args.model == "svensson":
        result = fit_svensson(rates_df, columns=columns, lambda1_value=args.lambda1, lambda2_value=args.lambda2)
        for date in dates:
            observed = result.observed.loc[result.observed["Date"] == date].iloc[-1]
            betas = result.betas.loc[result.betas["Date"] == date].iloc[-1]
            estimated = reconstruct_svensson_curve(curve_months / 12.0, betas, args.lambda1, args.lambda2)
            curves[date] = {
                "curve_months": curve_months,
                "estimated": estimated,
                "observed_months": maturities,
                "observed": np.array([observed[column] for column in columns], dtype=float),
            }
    else:
        working = rates_df[["Date", *columns]].dropna().copy()
        for date in dates:
            observed = working.loc[working["Date"] == date].iloc[-1]
            observed_values = np.array([observed[column] for column in columns], dtype=float)
            estimated = reconstruct_cubic_spline_curve(maturities, observed_values, curve_months)
            curves[date] = {
                "curve_months": curve_months,
                "estimated": estimated,
                "observed_months": maturities,
                "observed": observed_values,
            }

    return dates, curves


def create_animation(
    dates: list[pd.Timestamp],
    curves: dict[pd.Timestamp, dict[str, np.ndarray]],
    output_path: Path,
    fps: int,
    dynamic_y_axis: bool,
) -> None:
    fig, ax = plt.subplots(figsize=(10, 6), facecolor=BLOOMBERG_BG)
    ax.set_facecolor(BLOOMBERG_PANEL)
    for spine in ax.spines.values():
        spine.set_color(BLOOMBERG_GRID)
    ax.tick_params(colors=BLOOMBERG_TEXT)
    ax.xaxis.label.set_color(BLOOMBERG_TEXT)
    ax.yaxis.label.set_color(BLOOMBERG_TEXT)
    ax.title.set_color(BLOOMBERG_TEXT)
    ax.grid(color=BLOOMBERG_GRID, alpha=0.7)
    ax.set_xlabel("Madurez (meses)")
    ax.set_ylabel("Tasa")
    ax.set_xlim(
        float(min(payload["curve_months"][0] for payload in curves.values()) - 6),
        float(max(payload["curve_months"][-1] for payload in curves.values()) + 5),
    )

    all_values = np.concatenate([np.r_[payload["estimated"], payload["observed"]] for payload in curves.values()])
    y_min = float(np.nanmin(all_values))
    y_max = float(np.nanmax(all_values))
    padding = max((y_max - y_min) * 0.1, 0.1)
    ax.set_ylim(y_min - padding, y_max + padding)

    line, = ax.plot([], [], color=BLOOMBERG_CURVE, linewidth=2.5, label="Curva estimada")
    observed_line, = ax.plot(
        [],
        [],
        color=BLOOMBERG_POINTS,
        linewidth=1.8,
        linestyle="--",
        alpha=0.9,
        label="Tasas observadas",
    )
    points = ax.scatter(
        [],
        [],
        color=BLOOMBERG_POINTS,
        s=120,
        edgecolors=BLOOMBERG_BG,
        linewidths=1.2,
        zorder=5,
    )
    title = ax.set_title("")
    ax.legend(facecolor=BLOOMBERG_PANEL, edgecolor=BLOOMBERG_GRID, labelcolor=BLOOMBERG_TEXT)

    def update(frame_idx: int):
        date = dates[frame_idx]
        payload = curves[date]
        line.set_data(payload["curve_months"], payload["estimated"])
        observed_line.set_data(payload["observed_months"], payload["observed"])
        points.set_offsets(np.column_stack([payload["observed_months"], payload["observed"]]))
        if dynamic_y_axis:
            frame_values = np.r_[payload["estimated"], payload["observed"]]
            frame_min = float(np.nanmin(frame_values))
            frame_max = float(np.nanmax(frame_values))
            frame_padding = max((frame_max - frame_min) * 0.12, 0.05)
            ax.set_ylim(frame_min - frame_padding, frame_max + frame_padding)
        title.set_text(f"Evolucion de la curva: {pd.Timestamp(date).strftime('%Y-%m-%d')}")
        return line, observed_line, points, title

    animation = FuncAnimation(fig, update, frames=len(dates), interval=1000 / fps, blit=False)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    animation.save(output_path, writer=PillowWriter(fps=fps))
    plt.close(fig)


def main() -> None:
    args = parse_args()
    rates_df = load_rates(args)
    dates, curves = build_curves(rates_df, args)
    create_animation(
        dates,
        curves,
        Path(args.output),
        fps=args.fps,
        dynamic_y_axis=args.dynamic_y_axis,
    )
    print(f"GIF generado en: {args.output}")


if __name__ == "__main__":
    main()
