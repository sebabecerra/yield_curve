from __future__ import annotations

import io

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from yield_curve import (
    DEFAULT_DISCRETE_COLUMNS,
    DEFAULT_NS_COLUMNS,
    RATE_SERIES,
    fetch_bcch_series,
    fit_discrete_nelson_siegel,
    fit_nelson_siegel,
    reconstruct_nelson_siegel_curve,
    prepare_rates_dataframe,
)

st.set_page_config(page_title="Yield Curve", layout="wide")

BLOOMBERG_BG = "#0b0f14"
BLOOMBERG_PANEL = "#11161d"
BLOOMBERG_GRID = "#2a3441"
BLOOMBERG_TEXT = "#d7dde5"
BLOOMBERG_CURVE = "#f5a623"
BLOOMBERG_POINTS = "#ffd166"
BLOOMBERG_FACTOR = "#00c2ff"


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


st.title("Yield Curve App")
st.caption("App base construida desde los notebooks del proyecto para ajustar y visualizar curvas de tasa.")

bcch_submit = False
with st.sidebar:
    st.header("Datos")
    source_mode = st.radio("Fuente", options=["BCCh", "CSV"], index=0)
    uploaded_file = st.file_uploader("Sube un CSV", type=["csv"], disabled=source_mode != "CSV")
    st.markdown(
        "Formato esperado: columna `Date` más columnas con alias del catálogo, por ejemplo "
        "`spc_pesos_2y`, `spc_pesos_3y`, `spc_pesos_4y`, `spc_pesos_5y`, `spc_pesos_10y`."
    )
    st.caption("Series disponibles: " + ", ".join(RATE_SERIES.keys()))
    if source_mode == "BCCh":
        with st.form("bcch_form"):
            bcch_series = st.multiselect(
                "Series BCCh",
                options=list(RATE_SERIES.keys()),
                default=DEFAULT_NS_COLUMNS,
            )
            bcch_user = st.text_input("Usuario BCCh")
            bcch_password = st.text_input("Contraseña BCCh", type="password")
            start_date = st.date_input("Desde", value=pd.Timestamp("2018-01-01"))
            end_date = st.date_input("Hasta", value=pd.Timestamp.today())
            bcch_submit = st.form_submit_button("Entrar")

if source_mode == "CSV" and uploaded_file is not None:
    source_df = pd.read_csv(uploaded_file)
elif source_mode == "BCCh":
    if not bcch_user or not bcch_password:
        st.info("Ingresa tus credenciales BCCh y selecciona las series para trabajar con datos efectivos.")
        st.stop()
    if not bcch_submit:
        st.info("Completa las credenciales y presiona `Entrar` para cargar los datos de BCCh.")
        st.stop()
    try:
        source_df = fetch_bcch_series(
            series_keys=bcch_series or DEFAULT_NS_COLUMNS,
            user=bcch_user,
            password=bcch_password,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
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

tab_about, tab_data, tab_ns, tab_discrete = st.tabs(
    ["Modelo", "Datos", "Nelson-Siegel", "Modelo discreto"]
)

with tab_about:
    st.subheader("Qué hace la app")
    st.markdown(
        """
        Esta app estima una curva de tasas a partir de observaciones efectivas de mercado.

        Usa dos enfoques:

        - `Nelson-Siegel clásico`: ajusta factores `level`, `slope` y `curvature` por fecha.
        - `Modelo discreto`: ajusta una versión discreta del modelo usando `phi` y reconstruye la curva por madurez.
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

        `Modelo discreto`:

        - usa las madureces discretas definidas en el catálogo
        - calibra `phi` por grilla o usa un valor manual
        - estima betas por mínimos cuadrados
        - reconstruye la curva entre 1 y 120 meses
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
    st.dataframe(rates_df, use_container_width=True, hide_index=True)
    _download_button(rates_df, "Descargar datos limpios", "rates_input_clean.csv")

with tab_ns:
    st.subheader("Ajuste Nelson-Siegel clásico")
    default_ns = [column for column in DEFAULT_NS_COLUMNS if column in available_columns]
    ns_columns = st.multiselect(
        "Columnas para ajuste",
        options=available_columns,
        default=default_ns or available_columns[: min(5, len(available_columns))],
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
        st.metric("Lambda usada", f"{ns_result.lambda_value:.2f}")
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
                    )
                )
            _apply_bloomberg_style(fig_factors)
            fig_factors.update_layout(height=320)
            st.plotly_chart(fig_factors, use_container_width=True)
        with col2:
            st.markdown("**Curva observada vs ajustada en la última fecha**")
            latest_observed = ns_result.observed.iloc[-1]
            latest_betas = ns_result.betas.iloc[-1]
            observed_maturities = np.array(
                [RATE_SERIES[column].months for column in ns_columns],
                dtype=float,
            )
            continuous_months = np.arange(int(observed_maturities.min()), int(observed_maturities.max()) + 1, dtype=float)
            continuous_years = continuous_months / 12.0
            continuous_curve = reconstruct_nelson_siegel_curve(
                continuous_years,
                latest_betas,
                ns_result.lambda_value,
            )
            fig_ns = go.Figure()
            fig_ns.add_trace(
                go.Scatter(
                    x=continuous_months,
                    y=continuous_curve,
                    mode="lines",
                    name="Curva estimada",
                    line={"color": BLOOMBERG_CURVE, "width": 3},
                )
            )
            fig_ns.add_trace(
                go.Scatter(
                    x=observed_maturities,
                    y=[latest_observed[column] for column in ns_columns],
                    mode="markers",
                    name="Tasas observadas",
                    marker={"size": 10, "color": BLOOMBERG_POINTS, "line": {"color": BLOOMBERG_BG, "width": 1}},
                )
            )
            _apply_bloomberg_style(fig_ns, xaxis_title="Madurez (meses)", yaxis_title="Tasa")
            fig_ns.update_layout(height=320)
            st.plotly_chart(fig_ns, use_container_width=True)

        st.dataframe(ns_result.betas, use_container_width=True, hide_index=True)
        _download_button(ns_result.betas, "Descargar betas Nelson-Siegel", "nelson_siegel_betas.csv")

with tab_discrete:
    st.subheader("Modelo discreto con calibración de phi")
    default_discrete = [column for column in DEFAULT_DISCRETE_COLUMNS if column in available_columns]
    discrete_columns = st.multiselect(
        "Columnas para ajuste discreto",
        options=available_columns,
        default=default_discrete or available_columns,
    )
    calibrate_phi = st.toggle("Calibrar phi por grilla", value=True)
    manual_phi = st.slider("Phi manual", min_value=0.10, max_value=0.98, value=0.93, step=0.01, disabled=calibrate_phi)

    if len(discrete_columns) < 3:
        st.info("Selecciona al menos 3 tasas para estimar el modelo discreto.")
    else:
        discrete_result = fit_discrete_nelson_siegel(
            rates_df,
            columns=discrete_columns,
            phi=None if calibrate_phi else manual_phi,
        )
        st.metric("Phi usado", f"{discrete_result.phi:.2f}")

        if not discrete_result.phi_summary.empty:
            st.markdown("**Mejores valores de phi por error medio**")
            st.dataframe(discrete_result.phi_summary.head(10), use_container_width=True, hide_index=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Betas mensuales**")
            fig_betas = go.Figure()
            for name, color in [
                ("Beta_Constante", BLOOMBERG_CURVE),
                ("Beta_lambda2", BLOOMBERG_FACTOR),
                ("Beta_lambda3", BLOOMBERG_POINTS),
            ]:
                fig_betas.add_trace(
                    go.Scatter(
                        x=discrete_result.monthly_betas["DateM"],
                        y=discrete_result.monthly_betas[name],
                        mode="lines",
                        name=name,
                        line={"color": color, "width": 2},
                    )
                )
            _apply_bloomberg_style(fig_betas)
            fig_betas.update_layout(height=320)
            st.plotly_chart(fig_betas, use_container_width=True)
        with col2:
            available_months = discrete_result.reconstructed_curve["DateM"].drop_duplicates().sort_values()
            selected_month = st.selectbox("Mes para curva reconstruida", options=available_months)
            curve_df = discrete_result.reconstructed_curve.loc[
                discrete_result.reconstructed_curve["DateM"] == selected_month,
                ["n", "Tasa_Estimada"],
            ].set_index("n")
            observed_df = discrete_result.observed_monthly.loc[
                discrete_result.observed_monthly["DateM"] == selected_month,
                ["n", "Valor_Tasa"],
            ].set_index("n")
            fig_discrete = go.Figure()
            fig_discrete.add_trace(
                go.Scatter(
                    x=curve_df.index,
                    y=curve_df["Tasa_Estimada"],
                    mode="lines",
                    name="Curva estimada",
                    line={"color": BLOOMBERG_CURVE, "width": 3},
                )
            )
            fig_discrete.add_trace(
                go.Scatter(
                    x=observed_df.index,
                    y=observed_df["Valor_Tasa"],
                    mode="markers",
                    name="Tasas observadas",
                    marker={"size": 9, "color": BLOOMBERG_POINTS, "line": {"color": BLOOMBERG_BG, "width": 1}},
                )
            )
            _apply_bloomberg_style(fig_discrete, xaxis_title="Madurez (meses)", yaxis_title="Tasa")
            fig_discrete.update_layout(height=320)
            st.plotly_chart(fig_discrete, use_container_width=True)
            st.dataframe(
                observed_df.rename(columns={"Valor_Tasa": "Observada"}),
                use_container_width=True,
            )

        st.dataframe(discrete_result.monthly_betas, use_container_width=True, hide_index=True)
        _download_button(discrete_result.monthly_betas, "Descargar betas discretas", "discrete_betas.csv")
        _download_button(
            discrete_result.reconstructed_curve,
            "Descargar curva reconstruida",
            "discrete_curve.csv",
        )

template_buffer = io.StringIO()
pd.DataFrame(columns=["Date", *DEFAULT_NS_COLUMNS]).to_csv(template_buffer, index=False)
st.sidebar.download_button(
    "Descargar plantilla CSV",
    data=template_buffer.getvalue().encode("utf-8"),
    file_name="yield_curve_template.csv",
    mime="text/csv",
)
