"""
Análisis Klimek — Participación vs porcentaje del candidato.

Genera heatmaps 2D (participación × % candidato) para detectar
el fingerprint estadístico de ballot stuffing.

Referencia: Klimek et al. (2012), PNAS 109(41), 16469-16473.
"""

from dataclasses import dataclass


@dataclass
class KlimekResult:
    partido: str
    n: int
    correlacion_pearson: float
    pct_participacion_gt90: float
    pct_participacion_gt95: float
    media_participacion: float
    media_pct_candidato: float
    heatmap: list[list[int]]  # bins[participacion][pct_candidato]
    bins_x: list[float]  # bordes de bins participación (0-100)
    bins_y: list[float]  # bordes de bins % candidato (0-100)


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sx = sum((x - mx) ** 2 for x in xs) ** 0.5
    sy = sum((y - my) ** 2 for y in ys) ** 0.5
    if sx == 0 or sy == 0:
        return 0.0
    return cov / (sx * sy)


def analizar(
    datos: list[tuple[float, float]],  # [(participacion, pct_candidato), ...]
    partido: str,
    bin_size: int = 2,
) -> KlimekResult:
    n = len(datos)
    if n == 0:
        return KlimekResult(
            partido=partido, n=0, correlacion_pearson=0, pct_participacion_gt90=0,
            pct_participacion_gt95=0, media_participacion=0, media_pct_candidato=0,
            heatmap=[], bins_x=[], bins_y=[],
        )

    participaciones = [d[0] for d in datos]
    pcts = [d[1] for d in datos]

    corr = _pearson(participaciones, pcts)
    gt90 = sum(1 for p in participaciones if p > 90) / n * 100
    gt95 = sum(1 for p in participaciones if p > 95) / n * 100
    media_part = sum(participaciones) / n
    media_pct = sum(pcts) / n

    n_bins = 100 // bin_size
    bins_x = [i * bin_size for i in range(n_bins + 1)]
    bins_y = [i * bin_size for i in range(n_bins + 1)]
    heatmap = [[0] * n_bins for _ in range(n_bins)]

    for part, pct in datos:
        bx = min(int(part // bin_size), n_bins - 1)
        by = min(int(pct // bin_size), n_bins - 1)
        if bx >= 0 and by >= 0:
            heatmap[bx][by] += 1

    return KlimekResult(
        partido=partido,
        n=n,
        correlacion_pearson=round(corr, 6),
        pct_participacion_gt90=round(gt90, 2),
        pct_participacion_gt95=round(gt95, 2),
        media_participacion=round(media_part, 2),
        media_pct_candidato=round(media_pct, 2),
        heatmap=heatmap,
        bins_x=bins_x,
        bins_y=bins_y,
    )


async def run(db_url: str, top_n: int = 5) -> dict:
    import asyncpg

    pool = await asyncpg.create_pool(db_url, min_size=1, max_size=3)
    async with pool.acquire() as conn:
        partidos = await conn.fetch("""
            SELECT v.candidato, SUM(v.votos) AS total
            FROM onpe_mesa_votos v
            JOIN onpe_mesa_timeline t USING(codigo_mesa)
            WHERE t.estado_codigo='C'
              AND v.candidato NOT IN ('VOTOS EN BLANCO','VOTOS NULOS','VOTOS IMPUGNADOS')
            GROUP BY v.candidato ORDER BY total DESC
            LIMIT $1
        """, top_n)

        total_validos_por_mesa = await conn.fetch("""
            SELECT v.codigo_mesa, SUM(v.votos) AS total_vv
            FROM onpe_mesa_votos v
            JOIN onpe_mesa_timeline t USING(codigo_mesa)
            WHERE t.estado_codigo='C'
              AND v.candidato NOT IN ('VOTOS EN BLANCO','VOTOS NULOS','VOTOS IMPUGNADOS')
            GROUP BY v.codigo_mesa
        """)
        vv_map = {r["codigo_mesa"]: int(r["total_vv"]) for r in total_validos_por_mesa}

        resultados = []
        for row in partidos:
            partido = row["candidato"]
            rows = await conn.fetch("""
                SELECT v.codigo_mesa, v.votos,
                       t.electores_habiles, t.total_votos_emitidos
                FROM onpe_mesa_votos v
                JOIN onpe_mesa_timeline t USING(codigo_mesa)
                WHERE t.estado_codigo='C' AND v.candidato=$1
                  AND t.electores_habiles > 0
                  AND t.total_votos_emitidos > 0
            """, partido)

            datos = []
            for r in rows:
                eh = int(r["electores_habiles"])
                em = int(r["total_votos_emitidos"])
                votos = int(r["votos"])
                tvv = vv_map.get(r["codigo_mesa"], 0)
                if eh > 0 and tvv > 0:
                    participacion = min(em / eh * 100, 100)
                    pct_candidato = votos / tvv * 100
                    datos.append((participacion, pct_candidato))

            r = analizar(datos, partido)
            resultados.append(r)

    await pool.close()

    return {
        "analisis": "klimek",
        "partidos": [
            {
                "partido": r.partido,
                "n": r.n,
                "correlacion_pearson": r.correlacion_pearson,
                "pct_participacion_gt90": r.pct_participacion_gt90,
                "pct_participacion_gt95": r.pct_participacion_gt95,
                "media_participacion": r.media_participacion,
                "media_pct_candidato": r.media_pct_candidato,
                "heatmap": r.heatmap,
                "bins_x": r.bins_x,
                "bins_y": r.bins_y,
            }
            for r in resultados
        ],
    }
