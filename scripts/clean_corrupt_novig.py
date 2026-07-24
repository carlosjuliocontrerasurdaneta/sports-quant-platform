#!/usr/bin/env python
"""Limpieza puntual del served stream (auditoria 2026-07-24, secuela de C-1).

Antes del guard de mercado completo, una cotizacion unilateral se de-vig-eaba
a probabilidad implicita 1.0 y quedaba persistida en served_*.csv (y copiada a
graded_*.csv al gradarse). Esas filas contaminan el baseline `brier_market`
del monitor de degradacion y cualquier entrenamiento de calibradores sobre el
stream servido. Este script las elimina de data/calibration/ (excluye demo/).

Preservacion de datos crudos: antes de reescribir, cada archivo afectado se
respalda completo en data/calibration/archive/<archivo>.<stamp>.bak.csv y las
filas removidas se guardan aparte en <archivo>.<stamp>.removed.csv.

Uso:
  python scripts/clean_corrupt_novig.py           # dry-run: solo reporta
  python scripts/clean_corrupt_novig.py --apply   # respalda y limpia
"""
import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqp.config import ROOT
from sqp.storage.atomic import atomic_write_csv

COLUMN = "implied_probability_novig"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="sin --apply solo reporta (dry-run)")
    args = ap.parse_args()
    cal = ROOT / "data" / "calibration"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    total = 0
    for f in sorted(list(cal.glob("served_*.csv")) + list(cal.glob("graded_*.csv"))):
        try:
            df = pd.read_csv(f)
        except Exception as exc:
            print(f"{f.name}: ilegible ({exc}); omitido")
            continue
        if df.empty or COLUMN not in df.columns:
            continue
        bad = pd.to_numeric(df[COLUMN], errors="coerce") == 1.0
        n = int(bad.sum())
        if not n:
            continue
        total += n
        print(f"{f.name}: {n} de {len(df)} filas con {COLUMN} == 1.0")
        if args.apply:
            arch = cal / "archive"
            arch.mkdir(exist_ok=True)
            shutil.copy2(f, arch / f"{f.stem}.{stamp}.bak.csv")
            df[bad].to_csv(arch / f"{f.stem}.{stamp}.removed.csv", index=False)
            atomic_write_csv(df[~bad], f)
    print(f"{'REMOVIDAS' if args.apply else 'Detectadas (dry-run)'}: {total} filas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
