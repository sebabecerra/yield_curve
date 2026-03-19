# public_api

Backend y web publica para trabajar sobre una base ya cargada en el servidor.

## Idea

- Solo el administrador actualiza la base desde BCCh.
- La app publica no pide credenciales.
- Los usuarios solo calculan curvas sobre la base persistida.

## Ejecutar web publica

```bash
cd /Users/sbc/projects/yiled_curve
source .venv/bin/activate
uvicorn public_api.main:app --reload
```

Abre:

```text
http://127.0.0.1:8000
```

## Actualizar base desde BCCh

Con script local:

```bash
cd /Users/sbc/projects/yiled_curve
source .venv/bin/activate
python3 public_api/refresh_data.py \
  --user TU_USUARIO \
  --password TU_PASSWORD \
  --start-date 2005-01-01
```

Eso guarda:

- `public_api/data/market_rates.csv`
- `public_api/data/market_meta.json`

## Refresh privado por API

Opcionalmente puedes usar:

```text
POST /api/admin/refresh
```

Si defines `PUBLIC_API_ADMIN_TOKEN`, el endpoint exige header:

```text
x-admin-token: TU_TOKEN
```
