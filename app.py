from __future__ import annotations

import io
import os
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

from yield_curve import (
    DEFAULT_NS_COLUMNS,
    RATE_SERIES,
    fetch_bcch_series,
    fit_nelson_siegel,
    fit_svensson,
    reconstruct_nelson_siegel_curve,
    reconstruct_cubic_spline_curve,
    reconstruct_svensson_curve,
    prepare_rates_dataframe,
)

st.set_page_config(page_title="Yield Curve", layout="wide")

if load_dotenv is not None:
    load_dotenv(Path(__file__).resolve().parent / ".env")

BLOOMBERG_BG = "#0b0f14"
BLOOMBERG_PANEL = "#11161d"
BLOOMBERG_GRID = "#2a3441"
BLOOMBERG_TEXT = "#d7dde5"
BLOOMBERG_CURVE = "#f5a623"
BLOOMBERG_POINTS = "#ffd166"
BLOOMBERG_FACTOR = "#00c2ff"
BLOOMBERG_COMPARE = "#7ae582"
CURVE_COLOR_PAIRS = [
    (BLOOMBERG_CURVE, BLOOMBERG_POINTS),
    (BLOOMBERG_FACTOR, BLOOMBERG_COMPARE),
    ("#ff6b6b", "#c7f464"),
    ("#c792ea", "#82aaff"),
    ("#f78c6c", "#89ddff"),
    ("#addb67", "#f07178"),
]


def _apply_bloomberg_style(fig: go.Figure, xaxis_title: str = "", yaxis_title: str = "") -> None:
    fig.update_layout(
        paper_bgcolor=BLOOMBERG_BG,
        plot_bgcolor=BLOOMBERG_PANEL,
        font={"color": BLOOMBERG_TEXT},
        margin={"l": 20, "r": 20, "t": 20, "b": 20},
        xaxis={
            "title": xaxis_title,
            "gridcolor": BLOOMBERG_GRID,
            "zerolinecolor": BLOOMBERG_GRID,
            "showline": True,
            "linecolor": BLOOMBERG_GRID,
        },
        yaxis={
            "title": yaxis_title,
            "gridcolor": BLOOMBERG_GRID,
            "zerolinecolor": BLOOMBERG_GRID,
            "showline": True,
            "linecolor": BLOOMBERG_GRID,
        },
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
        },
    )


def _download_button(df: pd.DataFrame, label: str, filename: str) -> None:
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(label, data=csv_bytes, file_name=filename, mime="text/csv")


def _line_trace(x: object, y: object, name: str, color: str, width: int = 3) -> go.Scatter:
    return go.Scatter(
        x=x,
        y=y,
        mode="lines",
        name=name,
        line={"color": color, "width": width},
        hovertemplate="Madurez: %{x:.0f} meses<br>Tasa: %{y:.4f}<extra></extra>",
    )


def _marker_trace(x: object, y: object, name: str, color: str, size: int = 10) -> go.Scatter:
    return go.Scatter(
        x=x,
        y=y,
        mode="markers",
        name=name,
        marker={"size": size, "color": color, "line": {"color": BLOOMBERG_BG, "width": 1}},
        hovertemplate="Madurez: %{x:.0f} meses<br>Tasa: %{y:.4f}<extra></extra>",
    )


def _curve_date_selection(available_dates: list[str], key_prefix: str) -> list[str]:
    base_date = st.selectbox(
        "Fecha base",
        options=available_dates,
        index=len(available_dates) - 1,
        key=f"{key_prefix}_base_date",
    )
    compare_dates = st.multiselect(
        "Fechas a comparar",
        options=[date for date in available_dates if date != base_date],
        default=[],
        max_selections=5,
        key=f"{key_prefix}_compare_dates",
        help="Puedes seleccionar hasta 5 fechas adicionales. Con la fecha base, el maximo total es 6.",
    )
    return [base_date, *compare_dates]


st.title("Yield Curve App")
st.caption("App base construida desde los notebooks del proyecto para ajustar y visualizar curvas de tasa.")

with st.sidebar:
    st.header("Datos")
    source_mode = st.radio("Fuente", options=["BCCh", "CSV"], index=0)
    uploaded_file = st.file_uploader("Sube un CSV", type=["csv"], disabled=source_mode != "CSV")
    st.markdown(
        "Formato esperado: columna `Date` más columnas con alias del catálogo, por ejemplo "
        "`TPM`, `SPC_03Y`, `SPC_06Y`, `SPC_1Y`, `SPC_2Y`, `SPC_3Y`, `SPC_4Y`, `SPC_5Y`, `SPC_10Y`."
    )
    st.caption("Series disponibles: " + ", ".join(RATE_SERIES.keys()))
    if source_mode == "BCCh":
        with st.form("bcch_form", clear_on_submit=False):
            bcch_series = st.multiselect(
                "Series BCCh",
                options=list(RATE_SERIES.keys()),
                default=DEFAULT_NS_COLUMNS,
            )
            bcch_user = st.text_input("Usuario BCCh", value=os.getenv("BCCH_USER", ""))
            bcch_password = st.text_input("Contraseña BCCh", type="password", value=os.getenv("BCCH_PASSWORD", ""))
            start_date = st.date_input("Desde", value=pd.Timestamp("2018-01-01"))
            end_date = st.date_input("Hasta", value=pd.Timestamp.today())
            bcch_submit = st.form_submit_button("Entrar")
        if st.button("Recargar series por defecto"):
            st.session_state.bcch_loaded = False
            st.session_state.pop("bcch_series", None)
            st.rerun()

if source_mode == "CSV" and uploaded_file is not None:
    source_df = pd.read_csv(uploaded_file)
elif source_mode == "BCCh":
    if "bcch_loaded" not in st.session_state:
        st.session_state.bcch_loaded = False

    if bcch_submit:
        st.session_state.bcch_loaded = True
        st.session_state.bcch_user = bcch_user
        st.session_state.bcch_password = bcch_password
        st.session_state.bcch_series = bcch_series or DEFAULT_NS_COLUMNS
        st.session_state.bcch_start_date = start_date.isoformat()
        st.session_state.bcch_end_date = end_date.isoformat()

    if not st.session_state.bcch_loaded:
        st.info("Completa las credenciales y presiona `Entrar` para cargar los datos de BCCh.")
        st.stop()

    if not st.session_state.get("bcch_user") or not st.session_state.get("bcch_password"):
        st.info("Ingresa tus credenciales BCCh y selecciona las series para trabajar con datos efectivos.")
        st.stop()
    try:
        source_df = fetch_bcch_series(
            series_keys=st.session_state["bcch_series"],
            user=st.session_state["bcch_user"],
            password=st.session_state["bcch_password"],
            start_date=st.session_state["bcch_start_date"],
            end_date=st.session_state["bcch_end_date"],
        )
    except Exception as exc:
        st.error(f"No se pudo descargar desde BCCh: {exc}")
        st.stop()
else:
    st.info("Sube un CSV real para continuar.")
    st.stop()

raw_row_count = len(source_df)
try:
    rates_df = prepare_rates_dataframe(source_df)
except ValueError as exc:
    st.error(str(exc))
    st.stop()

available_columns = [column for column in rates_df.columns if column != "Date"]
if not available_columns:
    st.error("No se encontraron columnas de tasas para procesar.")
    st.stop()
default_curve_columns = [column for column in DEFAULT_NS_COLUMNS if column in available_columns]

tab_about, tab_data, tab_ns, tab_svensson, tab_spline = st.tabs(
    ["Modelo", "Datos", "Nelson-Siegel", "Svensson", "Cubic spline"]
)

with tab_about:
    st.subheader("Qué hace la app")
    st.markdown(
        """
        Esta app estima una curva de tasas a partir de observaciones efectivas de mercado.

        Usa varios enfoques:

        - `Nelson-Siegel clásico`: ajusta factores `level`, `slope` y `curvature` por fecha.
        - `Nelson-Siegel-Svensson`: extiende Nelson-Siegel con un segundo factor de curvatura.
        - `Cubic spline`: interpola una curva suave directamente sobre los nodos observados.
        """
    )

    st.subheader("Cómo entran los datos")
    st.markdown(
        """
        La app trabaja solo con datos efectivos:

        - `BCCh`: descarga series desde el servicio `SieteRestWS` usando tus credenciales.
        - `CSV`: carga un archivo local con columna `Date` y columnas de tasas.

        Las series disponibles vienen del catálogo normalizado del proyecto y usan alias como:
        `spc_pesos_2y`, `spc_pesos_3y`, `spc_pesos_4y`, `spc_pesos_5y`, `spc_pesos_10y`.
        """
    )

    st.subheader("Limpieza de datos")
    st.markdown(
        """
        Antes de estimar, la app:

        - convierte `Date` a fecha
        - convierte las columnas de tasas a numéricas
        - elimina cualquier fila que tenga `NA` en alguna tasa seleccionada

        Las curvas se calculan sobre el dataset limpio que ves en la pestaña `Datos`.
        """
    )

    st.subheader("Cómo se calcula cada modelo")
    st.markdown(
        """
        `Nelson-Siegel`:

        - toma una sección transversal de tasas por fecha
        - construye las cargas de `level`, `slope` y `curvature`
        - usa `lambda = 0.0609` fijo, siguiendo el notebook original
        - estima los betas por mínimos cuadrados
        - reconstruye una curva continua sobre la duración

        `Svensson`:

        - agrega un cuarto factor de curvatura
        - usa dos parámetros `lambda`
        - estima betas por mínimos cuadrados

        `Cubic spline`:

        - toma solo las tasas observadas disponibles
        - ajusta una interpolación cúbica natural
        - produce una curva suave sin factores latentes
        """
    )

    st.subheader("Cómo leer los gráficos")
    st.markdown(
        """
        - `Tasas observadas`: puntos efectivos disponibles en la fecha o mes elegido.
        - `Curva estimada`: línea ajustada por el modelo.
        - `Factores`: evolución temporal de los parámetros estimados.
        """
    )

with tab_data:
    st.subheader("Datos limpios usados en la estimación")
    removed_rows = raw_row_count - len(rates_df)
    st.caption(
        f"Filas originales: {raw_row_count} | Filas usadas: {len(rates_df)} | "
        f"Filas eliminadas por NA: {removed_rows}"
    )
    display_df = rates_df.copy()
    display_df["Date"] = display_df["Date"].dt.strftime("%Y-%m-%d")
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    _download_button(rates_df, "Descargar datos limpios", "rates_input_clean.csv")

with tab_ns:
    st.subheader("Ajuste Nelson-Siegel clásico")
    ns_columns = st.multiselect(
        "Columnas para ajuste",
        options=available_columns,
        default=default_curve_columns or available_columns[: min(5, len(available_columns))],
    )
    lambda_value = st.number_input(
        "Lambda",
        min_value=0.001,
        max_value=2.0,
        value=0.0609,
        step=0.001,
        format="%.4f",
    )

    if len(ns_columns) < 3:
        st.info("Selecciona al menos 3 tasas para estimar la curva.")
    else:
        ns_result = fit_nelson_siegel(
            rates_df,
            columns=ns_columns,
            lambda_value=lambda_value,
        )
        available_dates = ns_result.observed["Date"].dt.strftime("%Y-%m-%d").tolist()
        selected_ns_dates = _curve_date_selection(available_dates, "ns")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Factores estimados**")
            fig_factors = go.Figure()
            for name, color in [
                ("level", BLOOMBERG_CURVE),
                ("slope", BLOOMBERG_FACTOR),
                ("curvature", BLOOMBERG_POINTS),
            ]:
                fig_factors.add_trace(
                    go.Scatter(
                        x=ns_result.betas["Date"],
                        y=ns_result.betas[name],
                        mode="lines",
                        name=name,
                        line={"color": color, "width": 2},
                        hovertemplate="Fecha: %{x|%Y-%m-%d}<br>Valor: %{y:.4f}<extra></extra>",
                    )
                )
            _apply_bloomberg_style(fig_factors)
            fig_factors.update_layout(height=320)
            st.plotly_chart(fig_factors, use_container_width=True)
        with col2:
            st.markdown(f"**Curvas Nelson-Siegel**")
            observed_maturities = np.array([RATE_SERIES[column].months for column in ns_columns], dtype=float)
            continuous_months = np.arange(int(observed_maturities.min()), int(observed_maturities.max()) + 1, dtype=float)
            continuous_years = continuous_months / 12.0
            fig_ns = go.Figure()
            ns_curve_exports = []

            def add_ns_curve(observed_row: pd.Series, beta_row: pd.Series, date_label: str, curve_color: str, point_color: str) -> None:
                continuous_curve = reconstruct_nelson_siegel_curve(
                    continuous_years,
                    beta_row,
                    ns_result.lambda_value,
                )
                fig_ns.add_trace(_line_trace(continuous_months, continuous_curve, f"Estimada {date_label}", curve_color))
                fig_ns.add_trace(
                    _marker_trace(
                        observed_maturities,
                        [observed_row[column] for column in ns_columns],
                        f"Observada {date_label}",
                        point_color,
                    )
                )
                ns_curve_exports.append(
                    pd.DataFrame(
                        {
                            "Date": date_label,
                            "MaturityMonths": continuous_months.astype(int),
                            "EstimatedRate": continuous_curve,
                        }
                    )
                )
                ns_curve_exports.append(
                    pd.DataFrame(
                        {
                            "Date": date_label,
                            "MaturityMonths": observed_maturities.astype(int),
                            "ObservedRate": [observed_row[column] for column in ns_columns],
                        }
                    )
                )

            for idx, date_str in enumerate(selected_ns_dates):
                date_value = pd.Timestamp(date_str)
                observed_row = ns_result.observed.loc[ns_result.observed["Date"] == date_value].iloc[-1]
                beta_row = ns_result.betas.loc[ns_result.betas["Date"] == date_value].iloc[-1]
                curve_color, point_color = CURVE_COLOR_PAIRS[idx]
                add_ns_curve(observed_row, beta_row, date_str, curve_color, point_color)
            _apply_bloomberg_style(fig_ns, xaxis_title="Madurez (meses)", yaxis_title="Tasa")
            fig_ns.update_layout(height=320)
            st.plotly_chart(fig_ns, use_container_width=True)
        download_col1, download_col2 = st.columns(2)
        with download_col1:
            _download_button(ns_result.betas, "Descargar betas", "nelson_siegel_betas.csv")
        with download_col2:
            _download_button(
                pd.concat(ns_curve_exports, ignore_index=True),
                "Descargar curvas",
                "nelson_siegel_curves.csv",
            )

with tab_svensson:
    st.subheader("Nelson-Siegel-Svensson")
    sv_columns = st.multiselect(
        "Columnas para Svensson",
        options=available_columns,
        default=default_curve_columns or available_columns[: min(5, len(available_columns))],
        key="sv_columns",
    )
    sv_dates = rates_df["Date"].dt.strftime("%Y-%m-%d").tolist()
    selected_sv_dates = _curve_date_selection(sv_dates, "sv")

    if len(sv_columns) < 3:
        st.info("Selecciona al menos 3 tasas para estimar Svensson.")
    else:
        sv_columns = sorted(sv_columns, key=lambda column: RATE_SERIES[column].months)
        maturities = np.array([RATE_SERIES[column].months for column in sv_columns], dtype=float)
        continuous_months = np.arange(int(maturities.min()), int(maturities.max()) + 1, dtype=float)
        lambda1 = st.number_input("Lambda 1", min_value=0.001, max_value=2.0, value=0.0609, step=0.001, format="%.4f")
        lambda2 = st.number_input("Lambda 2", min_value=0.001, max_value=2.0, value=0.2000, step=0.001, format="%.4f")
        svensson_result = fit_svensson(rates_df, columns=sv_columns, lambda1_value=lambda1, lambda2_value=lambda2)

        fig_sv = go.Figure()
        sv_curve_exports = []
        for idx, date_str in enumerate(selected_sv_dates):
            date_value = pd.Timestamp(date_str)
            source_row = rates_df.loc[rates_df["Date"] == date_value, ["Date", *sv_columns]].iloc[-1]
            beta_row = svensson_result.betas.loc[svensson_result.betas["Date"] == date_value].iloc[-1]
            curve = reconstruct_svensson_curve(continuous_months / 12.0, beta_row, lambda1, lambda2)
            curve_color, point_color = CURVE_COLOR_PAIRS[idx]
            fig_sv.add_trace(_line_trace(continuous_months, curve, f"Estimada {date_str}", curve_color))
            fig_sv.add_trace(
                _marker_trace(maturities, [source_row[column] for column in sv_columns], f"Observada {date_str}", point_color)
            )
            sv_curve_exports.append(
                pd.DataFrame({"Date": date_str, "MaturityMonths": continuous_months.astype(int), "EstimatedRate": curve})
            )
            sv_curve_exports.append(
                pd.DataFrame(
                    {
                        "Date": date_str,
                        "MaturityMonths": maturities.astype(int),
                        "ObservedRate": [source_row[column] for column in sv_columns],
                    }
                )
            )
        sv_display = svensson_result.betas.copy()
        sv_display["Date"] = sv_display["Date"].dt.strftime("%Y-%m-%d")

        col1, col2 = st.columns(2)
        with col1:
            fig_sv_betas = go.Figure()
            for name, color in [
                ("level", BLOOMBERG_CURVE),
                ("slope", BLOOMBERG_FACTOR),
                ("curvature_1", BLOOMBERG_POINTS),
                ("curvature_2", BLOOMBERG_COMPARE),
            ]:
                fig_sv_betas.add_trace(
                    go.Scatter(
                        x=svensson_result.betas["Date"],
                        y=svensson_result.betas[name],
                        mode="lines",
                        name=name,
                        line={"color": color, "width": 2},
                        hovertemplate="Fecha: %{x|%Y-%m-%d}<br>Valor: %{y:.4f}<extra></extra>",
                    )
                )
            _apply_bloomberg_style(fig_sv_betas)
            fig_sv_betas.update_layout(height=320)
            st.plotly_chart(fig_sv_betas, use_container_width=True)
        with col2:
            _apply_bloomberg_style(fig_sv, xaxis_title="Madurez (meses)", yaxis_title="Tasa")
            fig_sv.update_layout(height=320)
            st.plotly_chart(fig_sv, use_container_width=True)
        download_col1, download_col2 = st.columns(2)
        with download_col1:
            _download_button(sv_display, "Descargar betas", "svensson_betas.csv")
        with download_col2:
            _download_button(pd.concat(sv_curve_exports, ignore_index=True), "Descargar curvas", "svensson_curves.csv")

with tab_spline:
    st.subheader("Cubic spline")
    spline_columns = st.multiselect(
        "Columnas para Cubic spline",
        options=available_columns,
        default=default_curve_columns or available_columns[: min(5, len(available_columns))],
        key="spline_columns",
    )
    spline_dates = rates_df["Date"].dt.strftime("%Y-%m-%d").tolist()
    selected_spline_dates = _curve_date_selection(spline_dates, "spline")

    if len(spline_columns) < 3:
        st.info("Selecciona al menos 3 tasas para estimar el spline.")
    else:
        spline_columns = sorted(spline_columns, key=lambda column: RATE_SERIES[column].months)
        maturities = np.array([RATE_SERIES[column].months for column in spline_columns], dtype=float)
        continuous_months = np.arange(int(maturities.min()), int(maturities.max()) + 1, dtype=float)
        fig_spline = go.Figure()
        spline_curve_exports = []
        observed_rates = None
        for idx, date_str in enumerate(selected_spline_dates):
            date_value = pd.Timestamp(date_str)
            source_row = rates_df.loc[rates_df["Date"] == date_value, ["Date", *spline_columns]].iloc[-1]
            rates = source_row[spline_columns].to_numpy(dtype=float)
            curve = reconstruct_cubic_spline_curve(maturities, rates, continuous_months)
            curve_color, point_color = CURVE_COLOR_PAIRS[idx]
            fig_spline.add_trace(_line_trace(continuous_months, curve, f"Interpolada {date_str}", curve_color))
            fig_spline.add_trace(_marker_trace(maturities, rates, f"Observada {date_str}", point_color))
            spline_curve_exports.append(
                pd.DataFrame({"Date": date_str, "MaturityMonths": continuous_months.astype(int), "EstimatedRate": curve})
            )
            spline_curve_exports.append(
                pd.DataFrame({"Date": date_str, "MaturityMonths": maturities.astype(int), "ObservedRate": rates})
            )
            if idx == 0:
                observed_rates = rates

        _apply_bloomberg_style(fig_spline, xaxis_title="Madurez (meses)", yaxis_title="Tasa")
        fig_spline.update_layout(height=420)
        st.plotly_chart(fig_spline, use_container_width=True)
        _download_button(pd.concat(spline_curve_exports, ignore_index=True), "Descargar curvas", "cubic_spline_curves.csv")

template_buffer = io.StringIO()
pd.DataFrame(columns=["Date", *DEFAULT_NS_COLUMNS]).to_csv(template_buffer, index=False)
st.sidebar.download_button(
    "Descargar plantilla CSV",
    data=template_buffer.getvalue().encode("utf-8"),
    file_name="yield_curve_template.csv",
    mime="text/csv",
)
