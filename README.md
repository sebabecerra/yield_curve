# Yield Curve Analytics

Plataforma estática para visualizar, comparar y descargar curvas de tasas a partir de una base de mercado ya incorporada en la aplicación.

La versión activa del proyecto está diseñada para:

- ejecutarse 100% en navegador
- publicarse directamente en GitHub Pages
- operar sin backend
- mostrar curvas ajustadas con metodología financiera real
- ofrecer una experiencia bilingüe en español e inglés

## Qué resuelve

Esta app transforma una base de tasas de mercado en una herramienta de análisis lista para uso ejecutivo, comercial y de monitoreo.

Permite:

- construir curvas de rendimiento con modelos reconocidos
- comparar fechas de mercado de forma visual
- revisar factores estimados en el tiempo
- inspeccionar la base usada en la estimación
- descargar curvas, betas y datos limpios

En términos prácticos, sirve para mostrar:

- cómo cambia el nivel de tasas
- cómo cambia la pendiente de la curva
- cómo cambia la curvatura
- cómo se mueve la estructura temporal entre distintas fechas

## Modelos incluidos

La app incorpora tres enfoques de construcción de curva:

- `Nelson-Siegel`
- `Nelson-Siegel-Svensson`
- `Cubic spline`

Cada uno permite:

- seleccionar las series de entrada
- elegir una fecha base
- agregar fechas comparativas
- descargar los resultados

## Propuesta de valor

Esta versión está pensada para ser simple de operar y potente de presentar.

Ventajas principales:

- no depende de login BCCh ni de API externa en tiempo real
- no requiere servidor Python para funcionar
- puede publicarse como sitio estático
- mantiene una base real ya integrada en la app
- tiene interfaz en español e inglés
- puede abrirse localmente o desplegarse en GitHub Pages

## Ruta activa del proyecto

La carpeta activa y oficial para la web pública es:

- `api_js/`

Si vas a modificar la app que hoy se publica, trabaja solo ahí.

Archivos principales:

- `api_js/index.html`
- `api_js/index_en.html`
- `api_js/css/styles.css`
- `api_js/js/app.js`
- `api_js/js/models.js`
- `api_js/data/market_rows.js`
- `api_js/data/market_rates.csv`

## Estructura de la app activa

```text
api_js/
  index.html
  index_en.html
  css/
    styles.css
  js/
    app.js
    models.js
  data/
    market_rows.js
    market_rates.csv
```

## Datos

La app usa una base real embebida.

Archivos de datos:

- `api_js/data/market_rows.js`: dataset que consume directamente la aplicación
- `api_js/data/market_rates.csv`: versión tabular del mismo dataset

Eso significa que la aplicación:

- no pide cargar archivos al usuario
- no necesita backend para estimar
- puede correr completa desde GitHub Pages

## Registro de accesos por email

La app puede registrar accesos en una hoja de Google Sheets sin backend propio.

Archivos relevantes:

- `api_js/config.js`
- `api_js/google_apps_script.gs`

Flujo:

1. crea una hoja de cálculo en Google Sheets
2. abre `Extensions -> Apps Script`
3. pega el contenido de `api_js/google_apps_script.gs`
4. despliega como `Web app`
5. copia la URL pública del script
6. pega la URL pública del script en `api_js/config.js`:

```js
window.YC_ACCESS_LOG_URL = "TU_URL_DE_APPS_SCRIPT";
```

Desde ese momento, cada email válido ingresado en la pantalla de acceso se envía también a la hoja `access_log`.

## Cómo probar localmente

```bash
cd /Users/sbc/projects/yiled_curve/api_js
python3 -m http.server 8080
```

Luego abre:

- `http://127.0.0.1:8080/index.html`
- `http://127.0.0.1:8080/index_en.html`

## Cómo se publica

GitHub Pages se despliega automáticamente mediante:

- `.github/workflows/deploy-pages.yml`

Ese workflow publica:

- `./api_js`

Flujo normal de publicación:

```bash
cd /Users/sbc/projects/yiled_curve
git add api_js
git commit -m "update api_js"
git push origin main
```

Después de eso, GitHub Pages redeploya la aplicación automáticamente.

URL pública:

- `https://sebabecerra.github.io/yield_curve/`

## Estado del repositorio

El proyecto conserva versiones anteriores para no perder trabajo, pero no son la ruta principal actual.

Todo lo histórico quedó agrupado en:

- `old/`

Ahí viven implementaciones anteriores como:

- `old/docs/`
- `old/html/`
- `old/webapp/`
- `old/public_api/`
- `old/yield_curve/`
- `old/notebooks/`
- `old/scripts/`
- `old/sample_data/`
- `old/outputs/`
- `old/app.py`

## Recomendación operativa

Para mantener el repo limpio:

- no uses `git add .`
- usa `git add api_js` cuando cambies la app pública
- revisa `git status` antes de commitear
- evita subir archivos pesados de trabajo local desde `papers/`
