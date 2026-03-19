from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from yield_curve import DEFAULT_NS_COLUMNS, fetch_bcch_series, normalize_rates_dataframe

from public_api.main import DATA_FILE, META_FILE, _latest_available_date, _sort_columns


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Actualiza la base persistida para public_api.")
    parser.add_argument("--user", help="Usuario BCCh")
    parser.add_argument("--password", help="Password BCCh")
    parser.add_argument("--start-date", default="2005-01-01", help="Fecha inicial YYYY-MM-DD")
    parser.add_argument("--columns", nargs="+", default=DEFAULT_NS_COLUMNS, help="Series a descargar")
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    user = args.user or os.getenv("BCCH_USER")
    password = args.password or os.getenv("BCCH_PASSWORD")
    if not user or not password:
        raise SystemExit("Faltan credenciales. Usa --user/--password o define BCCH_USER y BCCH_PASSWORD en .env.")

    raw_df = fetch_bcch_series(
        series_keys=args.columns,
        user=user,
        password=password,
        start_date=args.start_date,
        end_date="2099-12-31",
    )
    rates_df = normalize_rates_dataframe(raw_df)
    sorted_columns = _sort_columns(args.columns)
    rates_df_to_save = rates_df.copy()
    rates_df_to_save["Date"] = rates_df_to_save["Date"].dt.strftime("%Y-%m-%d")
    DATA_FILE.parent.mkdir(exist_ok=True)
    rates_df_to_save.to_csv(DATA_FILE, index=False)

    meta = {
        "start_date": args.start_date,
        "end_date": _latest_available_date(rates_df),
        "raw_row_count": int(len(raw_df)),
        "rows_used": int(len(rates_df)),
        "removed_rows": int(raw_df["Date"].isna().sum()),
        "columns": sorted_columns,
        "available_dates": rates_df["Date"].drop_duplicates().sort_values().dt.strftime("%Y-%m-%d").tolist(),
        "last_refresh_utc": rates_df["Date"].max().strftime("%Y-%m-%d"),
    }
    META_FILE.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Base actualizada en {Path(DATA_FILE).resolve()}")


if __name__ == "__main__":
    main()
