# api_js

Version 100% estatica del proyecto.

## Qué hace

- usa una base real incrustada directamente en JavaScript
- normaliza aliases del proyecto
- calcula Nelson-Siegel, Svensson y cubic spline en JavaScript
- no necesita backend

## Estructura

- `index.html`: version en espanol
- `index_en.html`: version en ingles
- `css/styles.css`: estilos
- `js/app.js`: interfaz, estado y graficos
- `js/models.js`: modelos de curva
- `data/market_rows.js`: base embebida
- `data/market_rates.csv`: version tabular de apoyo

## Ejecutar local

```bash
cd /Users/sbc/projects/yiled_curve/api_js
python3 -m http.server 8080
```

Abre:

```text
http://127.0.0.1:8080
```

## Subir a GitHub Pages

Puedes publicar esta carpeta como sitio estático sin API adicional.
