# GitHub Pages Frontend

`html/` ahora es un frontend estático real pensado para GitHub Pages.

## Cómo funciona

- `html/` se publica en GitHub Pages
- `webapp/` se despliega como API Python en otro hosting
- el frontend llama a la API con `fetch`

## Configuración

Edita [config.js](/Users/sbc/projects/yiled_curve/html/config.js) y cambia:

```js
window.YIELD_API_BASE_URL = "http://127.0.0.1:8000";
```

por la URL pública de tu backend, por ejemplo:

```js
window.YIELD_API_BASE_URL = "https://tu-api.onrender.com";
```

## Publicar en GitHub Pages

Publica el contenido de `html/` como sitio estático.

Opciones típicas:

- copiar `html/` a una rama `gh-pages`
- usar GitHub Actions para publicar `html/`
- configurar Pages desde una carpeta publicada si prefieres otro flujo

## Backend

La API debe exponer al menos:

- `POST /api/login`
- `POST /api/calculate`
- `POST /api/plot`
- `GET /api/data/{data_id}/download`
- `GET /api/health`

En [webapp/main.py](/Users/sbc/projects/yiled_curve/webapp/main.py) quedó CORS habilitado para permitir llamadas desde GitHub Pages.
