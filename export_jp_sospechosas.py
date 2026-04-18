"""
Exporta mesas sospechosas de un partido desde micro_fraude.json a CSV.

Uso:
  python3 -m analysis.analysis1.export_jp_sospechosas
  python3 -m analysis.analysis1.export_jp_sospechosas --party "JUNTOS POR EL PERÚ"
  python3 -m analysis.analysis1.export_jp_sospechosas --limit 50
  python3 -m analysis.analysis1.export_jp_sospechosas --enrich-onpe
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
from pathlib import Path

DIR = Path(__file__).parent
DEFAULT_INPUT = DIR / "resultados" / "micro_fraude.json"
DEFAULT_OUTPUT = DIR / "resultados" / "jp_sospechosas.csv"


def _normalize_codigo_mesa(value: object) -> str:
    return str(value).strip().removesuffix(".0").zfill(6)


def _load_records(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    records = list(data.get("top_mesas", []))
    for row in records:
        row["codigo_mesa"] = _normalize_codigo_mesa(row.get("codigo_mesa", ""))
    return records


def _filter_records(records: list[dict], party: str, limit: int | None) -> list[dict]:
    filtered = [
        row
        for row in records
        if row.get("flag_top_0_2_pct") and row.get("suspicious_party") == party
    ]
    filtered.sort(key=lambda row: (row.get("score", 0), row.get("estimated_excess_votes", 0)), reverse=True)
    if limit:
        filtered = filtered[:limit]
    return filtered


async def _enrich_records(records: list[dict]) -> list[dict]:
    from clara.scraper.actas import ActaDownloader

    downloader = ActaDownloader()
    enriched: list[dict] = []

    async def enrich_one(row: dict) -> dict:
        codigo_mesa = _normalize_codigo_mesa(row["codigo_mesa"])
        metadata = await downloader.obtener_metadata_onpe(codigo_mesa)
        merged = dict(row)
        if not metadata:
            merged["onpe_metadata_ok"] = False
            return merged

        merged["onpe_metadata_ok"] = True
        merged["acta_id"] = metadata.acta_id
        merged["onpe_total_emitidos"] = metadata.total_emitidos
        merged["onpe_total_validos"] = metadata.total_validos
        merged["onpe_blancos"] = metadata.blancos
        merged["onpe_nulos"] = metadata.nulos
        merged["onpe_impugnados"] = metadata.impugnados
        merged["onpe_archivos"] = len(metadata.archivos)
        merged["onpe_departamento"] = metadata.departamento
        merged["onpe_provincia"] = metadata.provincia
        merged["onpe_distrito"] = metadata.distrito

        votos = metadata.votos_por_partido()
        merged["onpe_votos_partido_sospechoso"] = votos.get("JUNTOS POR EL PERU")
        return merged

    tasks = [enrich_one(row) for row in records]
    for row in await asyncio.gather(*tasks):
        enriched.append(row)
    return enriched


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["codigo_mesa"])
        return

    base_fields = [
        "codigo_mesa",
        "departamento",
        "provincia",
        "distrito",
        "participacion_pct",
        "electores_habiles",
        "votos_emitidos",
        "total_validos",
        "winner_party",
        "winner_votes",
        "winner_share_pct",
        "winner_margin_pct",
        "suspicious_party",
        "suspicious_party_share_pct",
        "suspicious_party_z",
        "baseline_mean_share_pct",
        "baseline_source",
        "estimated_excess_votes",
        "winner_last_digit",
        "score",
    ]

    extra_fields = sorted({key for row in rows for key in row.keys() if key not in base_fields})
    fieldnames = base_fields + extra_fields

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--party", default="JUNTOS POR EL PERÚ")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--enrich-onpe", action="store_true")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    limit = args.limit or None

    records = _load_records(input_path)
    filtered = _filter_records(records, args.party, limit)
    if args.enrich_onpe and filtered:
        filtered = await _enrich_records(filtered)

    _write_csv(output_path, filtered)

    print("=" * 60)
    print("  EXPORT DE MESAS SOSPECHOSAS")
    print("=" * 60)
    print(f"Partido: {args.party}")
    print(f"Mesas exportadas: {len(filtered)}")
    print(f"Input:  {input_path}")
    print(f"Output: {output_path}")
    print(f"Con metadata ONPE: {'SI' if args.enrich_onpe else 'NO'}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
