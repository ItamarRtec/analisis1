"""
Exporta TODA la metadata de ONPE desde PostgreSQL a CSVs en store/data/.

Uso:
  python -m analysis.analysis1.export_metadata
  python -m analysis.analysis1.export_metadata --db postgresql://user:pass@host/db

Genera:
  store/data/mesas_geo.csv          — Geografía completa de cada mesa
  store/data/mesa_timeline.csv      — Eventos de estado por mesa (T/D/C/H/E/J)
  store/data/mesa_votos.csv         — Votos por partido por mesa
  store/data/mesa_completa.csv      — JOIN: geo + timeline(C) + votos pivoteados
  store/data/metadata.json          — Resumen de la exportación
"""

import asyncio
import csv
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

DIR = Path(__file__).parent
STORE_DIR = DIR / "store" / "data"
DEFAULT_DB = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/dbname")


def _elapsed(t0):
    s = int(time.time() - t0)
    return f"{s // 60}m {s % 60}s"


async def export_mesas_geo(conn) -> int:
    rows = await conn.fetch("""
        SELECT codigo_mesa, ubigeo, departamento, provincia, distrito,
               nombre_local, codigo_local, electores_habiles,
               total_votos_emitidos, participacion_pct,
               codigo_estado_acta, descripcion_estado_acta,
               id_eleccion, cargado_at, actualizado_at
        FROM onpe_mesas_geo
        ORDER BY codigo_mesa
    """)
    path = STORE_DIR / "mesas_geo.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "codigo_mesa", "ubigeo", "departamento", "provincia", "distrito",
            "nombre_local", "codigo_local", "electores_habiles",
            "votos_emitidos", "participacion_pct",
            "estado_acta", "estado_acta_desc",
            "id_eleccion", "cargado_at", "actualizado_at",
        ])
        for r in rows:
            w.writerow([
                r["codigo_mesa"], r["ubigeo"], r["departamento"],
                r["provincia"], r["distrito"],
                r["nombre_local"] or "", r["codigo_local"] or "",
                r["electores_habiles"] or "",
                r["total_votos_emitidos"] or "",
                r["participacion_pct"] or "",
                r["codigo_estado_acta"] or "",
                r["descripcion_estado_acta"] or "",
                r["id_eleccion"] or "",
                r["cargado_at"].isoformat() if r["cargado_at"] else "",
                r["actualizado_at"].isoformat() if r["actualizado_at"] else "",
            ])
    return len(rows)


async def export_timeline(conn) -> int:
    rows = await conn.fetch("""
        SELECT codigo_mesa, estado_codigo, estado_nombre,
               fecha_registro, electores_habiles,
               total_votos_emitidos, participacion_pct, cargado_at
        FROM onpe_mesa_timeline
        ORDER BY codigo_mesa, fecha_registro
    """)
    path = STORE_DIR / "mesa_timeline.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "codigo_mesa", "estado_codigo", "estado_nombre",
            "fecha_registro", "electores_habiles",
            "votos_emitidos", "participacion_pct", "cargado_at",
        ])
        for r in rows:
            w.writerow([
                r["codigo_mesa"], r["estado_codigo"],
                r["estado_nombre"] or "",
                r["fecha_registro"].isoformat() if r["fecha_registro"] else "",
                r["electores_habiles"] or "",
                r["total_votos_emitidos"] or "",
                r["participacion_pct"] or "",
                r["cargado_at"].isoformat() if r["cargado_at"] else "",
            ])
    return len(rows)


async def export_votos(conn) -> int:
    rows = await conn.fetch("""
        SELECT codigo_mesa, candidato, codigo_partido,
               votos, porcentaje_vv, cargado_at
        FROM onpe_mesa_votos
        ORDER BY codigo_mesa, votos DESC
    """)
    path = STORE_DIR / "mesa_votos.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "codigo_mesa", "candidato", "codigo_partido",
            "votos", "porcentaje_vv", "cargado_at",
        ])
        for r in rows:
            w.writerow([
                r["codigo_mesa"], r["candidato"],
                r["codigo_partido"] or "",
                r["votos"],
                r["porcentaje_vv"] or "",
                r["cargado_at"].isoformat() if r["cargado_at"] else "",
            ])
    return len(rows)


async def export_mesa_completa(conn) -> int:
    """JOIN de geo + timeline(C) + votos pivoteados en una sola fila por mesa."""

    partidos = await conn.fetch("""
        SELECT DISTINCT candidato FROM onpe_mesa_votos
        ORDER BY candidato
    """)
    party_names = [r["candidato"] for r in partidos]

    rows = await conn.fetch("""
        SELECT g.codigo_mesa, g.ubigeo, g.departamento, g.provincia, g.distrito,
               g.nombre_local, g.electores_habiles,
               g.codigo_estado_acta,
               t.estado_codigo AS timeline_estado,
               t.fecha_registro AS fecha_contabilizada,
               t.total_votos_emitidos, t.participacion_pct
        FROM onpe_mesas_geo g
        LEFT JOIN onpe_mesa_timeline t
          ON g.codigo_mesa = t.codigo_mesa AND t.estado_codigo = 'C'
        ORDER BY g.codigo_mesa
    """)

    votos_rows = await conn.fetch("""
        SELECT codigo_mesa, candidato, votos
        FROM onpe_mesa_votos
        ORDER BY codigo_mesa
    """)
    votos_map: dict[str, dict[str, int]] = {}
    for r in votos_rows:
        cm = r["codigo_mesa"]
        if cm not in votos_map:
            votos_map[cm] = {}
        votos_map[cm][r["candidato"]] = int(r["votos"])

    path = STORE_DIR / "mesa_completa.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        header = [
            "codigo_mesa", "ubigeo", "departamento", "provincia", "distrito",
            "nombre_local", "electores_habiles",
            "estado_acta", "contabilizada", "fecha_contabilizada",
            "votos_emitidos", "participacion_pct",
        ] + party_names
        w.writerow(header)

        for r in rows:
            cm = r["codigo_mesa"]
            mesa_votos = votos_map.get(cm, {})
            row = [
                cm, r["ubigeo"], r["departamento"], r["provincia"], r["distrito"],
                r["nombre_local"] or "",
                r["electores_habiles"] or "",
                r["codigo_estado_acta"] or "",
                "SI" if r["timeline_estado"] else "NO",
                r["fecha_contabilizada"].isoformat() if r["fecha_contabilizada"] else "",
                r["total_votos_emitidos"] or "",
                r["participacion_pct"] or "",
            ] + [mesa_votos.get(p, "") for p in party_names]
            w.writerow(row)

    return len(rows)


async def main(db_url: str):
    import asyncpg

    print("=" * 60)
    print("  EXPORT METADATA ONPE → CSV")
    print("=" * 60)
    print()

    STORE_DIR.mkdir(parents=True, exist_ok=True)

    pool = await asyncpg.create_pool(db_url, min_size=2, max_size=5)
    async with pool.acquire() as conn:
        t0 = time.time()

        print("  [1/4] mesas_geo.csv")
        n_geo = await export_mesas_geo(conn)
        print(f"         {n_geo:,} mesas — {_elapsed(t0)}")

        print("  [2/4] mesa_timeline.csv")
        n_tl = await export_timeline(conn)
        print(f"         {n_tl:,} eventos — {_elapsed(t0)}")

        print("  [3/4] mesa_votos.csv")
        n_vt = await export_votos(conn)
        print(f"         {n_vt:,} registros — {_elapsed(t0)}")

        print("  [4/4] mesa_completa.csv (JOIN pivoteado)")
        n_mc = await export_mesa_completa(conn)
        print(f"         {n_mc:,} mesas — {_elapsed(t0)}")

        stats = {
            "total_mesas_geo": await conn.fetchval("SELECT COUNT(*) FROM onpe_mesas_geo"),
            "contabilizadas_geo": await conn.fetchval("SELECT COUNT(*) FROM onpe_mesas_geo WHERE codigo_estado_acta='C'"),
            "pendientes_geo": await conn.fetchval("SELECT COUNT(*) FROM onpe_mesas_geo WHERE codigo_estado_acta='P'"),
            "enviadas_geo": await conn.fetchval("SELECT COUNT(*) FROM onpe_mesas_geo WHERE codigo_estado_acta='E'"),
            "timeline_eventos": n_tl,
            "timeline_contabilizadas": await conn.fetchval("SELECT COUNT(*) FROM onpe_mesa_timeline WHERE estado_codigo='C'"),
            "timeline_digitacion": await conn.fetchval("SELECT COUNT(*) FROM onpe_mesa_timeline WHERE estado_codigo='D'"),
            "timeline_digitalizacion": await conn.fetchval("SELECT COUNT(*) FROM onpe_mesa_timeline WHERE estado_codigo='T'"),
            "timeline_observadas": await conn.fetchval("SELECT COUNT(*) FROM onpe_mesa_timeline WHERE estado_codigo='H'"),
            "timeline_para_envio_jee": await conn.fetchval("SELECT COUNT(*) FROM onpe_mesa_timeline WHERE estado_codigo='E'"),
            "votos_registros": n_vt,
            "mesas_con_votos": await conn.fetchval("SELECT COUNT(DISTINCT codigo_mesa) FROM onpe_mesa_votos"),
            "partidos_unicos": await conn.fetchval("SELECT COUNT(DISTINCT candidato) FROM onpe_mesa_votos"),
            "departamentos": await conn.fetchval("SELECT COUNT(DISTINCT departamento) FROM onpe_mesas_geo"),
            "provincias": await conn.fetchval("SELECT COUNT(DISTINCT provincia) FROM onpe_mesas_geo"),
            "distritos": await conn.fetchval("SELECT COUNT(DISTINCT distrito) FROM onpe_mesas_geo"),
        }

    await pool.close()

    meta = {
        "exportado_at": datetime.now(timezone.utc).isoformat(),
        "db": db_url.split("@")[-1] if "@" in db_url else "local",
        "archivos": {
            "mesas_geo.csv": f"{n_geo:,} filas — geografía completa de cada mesa",
            "mesa_timeline.csv": f"{n_tl:,} filas — eventos de estado (T/D/C/H/E/J) por mesa",
            "mesa_votos.csv": f"{n_vt:,} filas — votos por partido por mesa",
            "mesa_completa.csv": f"{n_mc:,} filas — JOIN: geo + contabilización + votos pivoteados",
        },
        "estadisticas": stats,
    }
    meta_path = STORE_DIR / "metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print()
    print("  Archivos generados:")
    for name in ["mesas_geo.csv", "mesa_timeline.csv", "mesa_votos.csv", "mesa_completa.csv", "metadata.json"]:
        p = STORE_DIR / name
        size = p.stat().st_size
        if size > 1_000_000:
            s = f"{size / 1_000_000:.1f} MB"
        elif size > 1_000:
            s = f"{size / 1_000:.1f} KB"
        else:
            s = f"{size} B"
        print(f"    {name:<25} {s}")

    print()
    print(f"  {stats['total_mesas_geo']:,} mesas · {stats['departamentos']} departamentos · {stats['partidos_unicos']} partidos")
    print(f"  Directorio: {STORE_DIR}/")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=DEFAULT_DB)
    args = parser.parse_args()
    asyncio.run(main(args.db))
