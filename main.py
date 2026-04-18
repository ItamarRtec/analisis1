"""
Entry point completo para Analysis 1.

Por defecto ejecuta:
1. Export de metadata ONPE a CSV
2. Benford
3. Último dígito
4. Klimek
5. Micro-fraude heurístico
6. Export de mesas sospechosas por partido

Uso:
  python -m analysis.analysis1.main
  python -m analysis.analysis1.main --db postgresql://user:pass@host/db
  python -m analysis.analysis1.main --skip-export
  python -m analysis.analysis1.main --party "RENOVACIÓN POPULAR"
  python -m analysis.analysis1.main --enrich-onpe
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

if __package__ in {None, ""}:
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

from analysis.analysis1.export_jp_sospechosas import (
    _enrich_records,
    _filter_records,
    _load_records,
    _write_csv,
)
from analysis.analysis1.micro_fraude import RESULTS_PATH as MICRO_FRAUDE_RESULTS_PATH
from analysis.analysis1.micro_fraude import run as run_micro_fraude
from analysis.analysis1.run import (
    DATA_DIR,
    RESULTS_DIR,
    ejecutar_analisis,
    exportar_data,
)
import os
DEFAULT_DB = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/dbname")

DIR = Path(__file__).parent
DEFAULT_JP_OUTPUT = DIR / "resultados" / "jp_sospechosas.csv"


async def exportar_mesas_sospechosas(
    input_path: Path,
    output_path: Path,
    party: str,
    limit: int | None = None,
    enrich_onpe: bool = False,
) -> int:
    records = _load_records(input_path)
    filtered = _filter_records(records, party=party, limit=limit)
    if enrich_onpe and filtered:
        filtered = await _enrich_records(filtered)
    _write_csv(output_path, filtered)
    return len(filtered)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument(
        "--skip-export",
        action="store_true",
        help="No re-exportar metadata ONPE; reutiliza store/data/mesa_completa.csv existente.",
    )
    parser.add_argument(
        "--skip-forensics",
        action="store_true",
        help="No correr Benford / último dígito / Klimek.",
    )
    parser.add_argument(
        "--party",
        default="JUNTOS POR EL PERÚ",
        help="Partido a exportar desde micro_fraude.json.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Límite opcional de mesas sospechosas a exportar.",
    )
    parser.add_argument(
        "--enrich-onpe",
        action="store_true",
        help="Agrega metadata fresca de ONPE al CSV exportado.",
    )
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(exist_ok=True)

    print("=" * 60)
    print("  ANALYSIS 1 — PIPELINE COMPLETO")
    print("=" * 60)

    if not args.skip_export:
        print()
        print("[1/4] Exportando metadata ONPE")
        await exportar_data(args.db)
    else:
        print()
        print("[1/4] Exportando metadata ONPE")
        print("      Omitido (--skip-export)")

    if not args.skip_forensics:
        print()
        print("[2/4] Ejecutando análisis estadísticos")
        await ejecutar_analisis(args.db)
    else:
        print()
        print("[2/4] Ejecutando análisis estadísticos")
        print("      Omitido (--skip-forensics)")

    print()
    print("[3/4] Ejecutando micro-fraude heurístico")
    micro_fraude = run_micro_fraude(csv_path=DATA_DIR / "mesa_completa.csv")
    with open(MICRO_FRAUDE_RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(micro_fraude, f, ensure_ascii=False, indent=2)
    print(f"      Output: {MICRO_FRAUDE_RESULTS_PATH}")
    print(f"      Mesas analizadas: {micro_fraude['dataset']['mesas_analizadas']:,}")
    print(f"      Top 0.2%: {micro_fraude['dataset']['top_0_2_pct_mesas']:,}")

    print()
    print("[4/4] Exportando mesas sospechosas")
    exported = await exportar_mesas_sospechosas(
        input_path=MICRO_FRAUDE_RESULTS_PATH,
        output_path=DEFAULT_JP_OUTPUT,
        party=args.party,
        limit=args.limit or None,
        enrich_onpe=args.enrich_onpe,
    )
    print(f"      Partido: {args.party}")
    print(f"      Mesas exportadas: {exported}")
    print(f"      Output: {DEFAULT_JP_OUTPUT}")

    print()
    print("=" * 60)
    print("  Completado.")
    print(f"    Data:       {DATA_DIR}/")
    print(f"    Resultados: {RESULTS_DIR}/")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
