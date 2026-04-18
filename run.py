"""
Ejecuta los 3 análisis forenses y guarda resultados + data en este directorio.

Uso:
  python -m analysis.analysis1.run
  python -m analysis.analysis1.run --db postgresql://user:pass@host/db
"""

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

DIR = Path(__file__).parent
DATA_DIR = DIR / "store" / "data"
RESULTS_DIR = DIR / "resultados"

DEFAULT_DB = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/dbname")


async def exportar_data(db_url: str):
    """Exporta toda la metadata de ONPE usando export_metadata."""
    from analysis.analysis1.export_metadata import main as export_main
    await export_main(db_url)


async def ejecutar_analisis(db_url: str):
    """Ejecuta los 3 análisis y guarda resultados."""
    from analysis.analysis1.benford import run as run_benford
    from analysis.analysis1.last_digit import run as run_last_digit
    from analysis.analysis1.klimek import run as run_klimek

    ts = datetime.now(timezone.utc).isoformat()

    # Benford
    print("  Ejecutando Ley de Benford...")
    benford = await run_benford(db_url, top_n=10)
    benford["ejecutado_at"] = ts
    path = RESULTS_DIR / "benford.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(benford, f, ensure_ascii=False, indent=2)
    for p in benford["partidos"]:
        d1 = p["primer_digito"]
        print(f"    {p['partido'][:40]:<42} MAD={d1['mad']:.4f}  {d1['conformidad']}")

    # Último dígito
    print("  Ejecutando último dígito...")
    last_digit = await run_last_digit(db_url, top_n=10)
    last_digit["ejecutado_at"] = ts
    path = RESULTS_DIR / "ultimo_digito.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(last_digit, f, ensure_ascii=False, indent=2)
    for p in last_digit["partidos"]:
        print(f"    {p['partido'][:40]:<42} chi2={p['chi2']:>8.1f}  p={p['p_valor']:.6f}  max_desv: d{p['digito_max_desviacion']}")

    # Klimek
    print("  Ejecutando Klimek (participación vs %)...")
    klimek = await run_klimek(db_url, top_n=5)
    klimek["ejecutado_at"] = ts
    path = RESULTS_DIR / "klimek.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(klimek, f, ensure_ascii=False, indent=2)
    for p in klimek["partidos"]:
        r_abs = abs(p["correlacion_pearson"])
        flag = "  *** ALERTA" if r_abs > 0.3 else ""
        print(f"    {p['partido'][:40]:<42} r={p['correlacion_pearson']:+.4f}{flag}")

    # Resumen consolidado
    resumen = {
        "ejecutado_at": ts,
        "analisis": ["benford", "ultimo_digito", "klimek"],
        "benford": [
            {
                "partido": p["partido"],
                "mad_1d": p["primer_digito"]["mad"],
                "conformidad_1d": p["primer_digito"]["conformidad"],
                "chi2_1d": p["primer_digito"]["chi2"],
                "p_valor_1d": p["primer_digito"]["p_valor"],
                "mad_2d": p["segundo_digito"]["mad"],
                "conformidad_2d": p["segundo_digito"]["conformidad"],
            }
            for p in benford["partidos"]
        ],
        "ultimo_digito": [
            {
                "partido": p["partido"],
                "chi2": p["chi2"],
                "p_valor": p["p_valor"],
                "max_desviacion": p["max_desviacion"],
                "digito_max_desviacion": p["digito_max_desviacion"],
            }
            for p in last_digit["partidos"]
        ],
        "klimek": [
            {
                "partido": p["partido"],
                "correlacion_pearson": p["correlacion_pearson"],
                "pct_participacion_gt90": p["pct_participacion_gt90"],
                "pct_participacion_gt95": p["pct_participacion_gt95"],
                "media_participacion": p["media_participacion"],
            }
            for p in klimek["partidos"]
        ],
    }
    path = RESULTS_DIR / "resumen.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)
    print(f"    Resumen guardado en {path}")


async def main(db_url: str):
    print("=" * 60)
    print("  ANALYSIS 1 — Auditoría Estadística Forense")
    print("=" * 60)
    print()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(exist_ok=True)

    print("[1/2] Exportando metadata ONPE completa")
    await exportar_data(db_url)

    print()
    print("[2/2] Ejecutando análisis forenses")
    await ejecutar_analisis(db_url)

    print()
    print("=" * 60)
    print("  Completado.")
    print(f"    Data:       {DATA_DIR}/")
    print(f"    Resultados: {RESULTS_DIR}/")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=DEFAULT_DB)
    args = parser.parse_args()
    asyncio.run(main(args.db))
