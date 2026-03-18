# yield_curve

App base para calcular y visualizar la yield curve a partir de la lógica que ya existe en los notebooks del proyecto.

## Qué incluye

- Ajuste Nelson-Siegel clásico para tasas observadas por fecha.
- Ajuste discreto con `phi` calibrado por grilla, siguiendo la idea del notebook `MonitorAnimadoTasasdeInteresBCCh.ipynb`.
- App en Streamlit para cargar un CSV, revisar factores y descargar resultados.
- Descarga opcional desde BCCh usando usuario y contraseña del servicio.
- Dataset demo y plantilla de entrada.

## Estructura

- `app.py`: interfaz Streamlit.
- `yield_curve/core.py`: funciones de cálculo reutilizables.
- `sample_data/demo_rates.csv`: ejemplo mínimo.
- `sample_data/template_rates.csv`: plantilla para tus propios datos.

## Formato esperado del CSV

Debe existir una columna `Date` y una o más columnas de tasas. El catálogo maestro quedó normalizado desde `notebooks/series_spc.json` y usa alias internos como:

- `spc_pesos_2y`
- `spc_pesos_3y`
- `spc_pesos_4y`
- `spc_pesos_5y`
- `spc_pesos_10y`
- `spc_uf_1y`
- `spc_uf_2y`
- `spc_uf_3y`
- `spc_uf_4y`
- `spc_uf_5y`
- `spc_uf_10y`
- `spc_uf_20y`

Cada alias tiene asociado:

- `label`: nombre legible
- `code`: código BCCh
- `months`: madurez en meses
- `currency`: moneda o unidad (`CLP` o `UF`)

## Ejecutar

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Web App

Version web real con backend Python:

```bash
uvicorn webapp.main:app --reload
```

Luego abre:

```text
http://127.0.0.1:8000
```

## Generar animacion

Puedes generar un GIF con la evolucion completa de las curvas:

```bash
python3 scripts/generate_curve_animation.py \
  --source csv \
  --csv-path sample_data/demo_rates.csv \
  --start-date 2018-01-01 \
  --end-date 2018-10-01 \
  --model nelson-siegel \
  --columns SPC_2Y SPC_3Y SPC_4Y SPC_5Y SPC_10Y \
  --output outputs/curve_evolution.gif
```

Tambien soporta `--source bcch` usando `--user` y `--password`.

Tambien puedes usar variables de entorno:

```bash
export BCCH_USER="tu_usuario"
export BCCH_PASSWORD="tu_password"
```

## Fuente de datos

La app puede trabajar de tres maneras:

- `Demo`: usa un dataset sintético incluido en el repo.
- `CSV`: carga un archivo local con columnas alineadas al catálogo.
- `BCCh`: consulta directamente las series del catálogo usando tus credenciales del servicio `SieteRestWS`.

## Notas

- La calibración automática de `phi` selecciona el valor con menor error cuadrático medio promedio entre meses.
- La app no descarga datos de BCCh todavía; trabaja con CSV local o con el dataset demo.
