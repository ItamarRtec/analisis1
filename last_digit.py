"""
Análisis de uniformidad del último dígito.

El último dígito de conteos de votos debe distribuirse uniformemente (0-9).
Desviaciones indican manipulación manual de cifras.
"""

from dataclasses import dataclass

from analysis.analysis1.stats import chi2_pvalue as _chi2_pvalue


@dataclass
class LastDigitResult:
    partido: str
    n: int
    conteos: dict[int, int]
    distribucion_observada: dict[int, float]
    chi2: float
    p_valor: float
    max_desviacion: float
    digito_max_desviacion: int


def analizar(votos_por_mesa: list[int], partido: str) -> LastDigitResult:
    n = len(votos_por_mesa)

    conteos = {d: 0 for d in range(10)}
    for v in votos_por_mesa:
        conteos[v % 10] += 1

    obs = {d: conteos[d] / n for d in range(10)} if n > 0 else {d: 0.0 for d in range(10)}
    esperado = n / 10

    chi2 = sum((conteos[d] - esperado) ** 2 / esperado for d in range(10)) if esperado > 0 else 0.0
    p = _chi2_pvalue(chi2, 9)

    desviaciones = {d: abs(obs[d] - 0.1) for d in range(10)}
    max_d = max(desviaciones, key=desviaciones.get)

    return LastDigitResult(
        partido=partido,
        n=n,
        conteos=conteos,
        distribucion_observada={d: round(obs[d], 6) for d in range(10)},
        chi2=round(chi2, 4),
        p_valor=round(p, 6),
        max_desviacion=round(desviaciones[max_d], 6),
        digito_max_desviacion=max_d,
    )


async def run(db_url: str, top_n: int = 10) -> dict:
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

        resultados = []
        for row in partidos:
            partido = row["candidato"]
            votos_rows = await conn.fetch("""
                SELECT v.votos FROM onpe_mesa_votos v
                JOIN onpe_mesa_timeline t USING(codigo_mesa)
                WHERE t.estado_codigo='C' AND v.candidato=$1
            """, partido)
            votos = [int(r["votos"]) for r in votos_rows]

            r = analizar(votos, partido)
            resultados.append(r)

    await pool.close()

    return {
        "analisis": "ultimo_digito",
        "partidos": [
            {
                "partido": r.partido,
                "n": r.n,
                "chi2": r.chi2,
                "p_valor": r.p_valor,
                "max_desviacion": r.max_desviacion,
                "digito_max_desviacion": r.digito_max_desviacion,
                "observado": r.distribucion_observada,
                "conteos": r.conteos,
            }
            for r in resultados
        ],
    }
