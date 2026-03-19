# yield_curve

Repositorio para construir, probar y publicar distintas versiones de una app de curvas de tasas basada en la lógica de los notebooks del proyecto.

## Ruta activa

La version activa para publicacion en GitHub Pages es:

- `api_js/`

Esa carpeta contiene:

- frontend estatico
- calculo de modelos en JavaScript puro
- base de mercado incrustada en el sitio
- version en espanol e ingles

Si vas a cambiar la web publica, trabaja solo en:

- `api_js/index.html`
- `api_js/index_en.html`
- `api_js/css/styles.css`
- `api_js/js/app.js`
- `api_js/js/models.js`
- `api_js/data/market_rows.js`

## Como probar la version activa

```bash
cd /Users/sbc/projects/yiled_curve/api_js
python3 -m http.server 8080
```

Luego abre:

- `http://127.0.0.1:8080/index.html`
- `http://127.0.0.1:8080/index_en.html`

## Como publicar en GitHub Pages

GitHub Pages se despliega por GitHub Actions usando:

- `.github/workflows/deploy-pages.yml`

Ese workflow publica la carpeta:

- `./api_js`

Flujo normal:

```bash
cd /Users/sbc/projects/yiled_curve
git add api_js
git commit -m "update api_js"
git push origin main
```

Despues GitHub redeploya Pages automaticamente.

URL publica:

- `https://sebabecerra.github.io/yield_curve/`

## Carpetas del proyecto

Estas carpetas se mantienen, pero no todas son la version publica actual:

- `api_js/`: app estatica actual para GitHub Pages. Esta es la carpeta principal.
- `old/docs/`: respaldo historico usado en despliegues anteriores de Pages.
- `old/html/`: prototipo frontend estatico anterior.
- `old/webapp/`: version web con backend Python y FastAPI.
- `old/public_api/`: backend para base precargada y actualizacion privada de datos.
- `old/yield_curve/`: motor Python original con calculos y utilidades.
- `old/notebooks/`: notebooks de investigacion y preparacion.
- `old/scripts/`: scripts auxiliares, incluyendo animaciones.
- `old/sample_data/`: archivos de ejemplo.
- `old/outputs/`: salidas generadas localmente.
- `papers/`: archivos de trabajo locales.

## Datos de la version activa

La version `api_js/` usa una base incrustada.

Archivos relevantes:

- `api_js/data/market_rows.js`: dataset embebido que consume la app.
- `api_js/data/market_rates.csv`: version tabular legible de esa base.

## Otras versiones

El repo mantiene versiones anteriores o alternativas para no perder trabajo:

- Streamlit: `old/app.py`
- FastAPI con frontend propio: `old/webapp/`
- API publica con refresh privado: `old/public_api/`

Esas rutas no se borran, pero no son la ruta principal actual para la web publica.

## Recomendacion operativa

Para evitar errores:

- no uses `git add .` en este repo
- usa `git add api_js` cuando cambies la web publica
- revisa `git status` antes de commitear
