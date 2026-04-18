"""
Análisis de Ley de Benford — primer y segundo dígito.

Compara la distribución de dígitos en votos por mesa contra
la distribución teórica de Benford. Calcula chi-cuadrado, p-valor y MAD.
"""

import math
from dataclasses import dataclass

from analysis.analysis1.stats import chi2_pvalue as _chi2_pvalue

BENFORD_FIRST = {d: math.log10(1 + 1 / d) for d in range(1, 10)}

BENFORD_SECOND = {}
for d2 in range(10):
    BENFORD_SECOND[d2] = sum(math.log10(1 + 1 / (10 * d1 + d2)) for d1 in range(1, 10))


@dataclass
class BenfordResult:
    partido: str
    digito_tipo: str  # "primero" o "segundo"
    n: int
    distribucion_observada: dict[int, float]
    distribucion_esperada: dict[int, float]
    conteos: dict[int, int]
    chi2: float
    p_valor: float
    mad: float
    conformidad: str  # "cercana", "aceptable", "marginal", "no conforme"


def _mad_conformidad(mad: float) -> str:
    if mad < 0.006:
        return "cercana"
    if mad < 0.012:
        return "aceptable"
    if mad < 0.015:
        return "marginal"
    return "no conforme"


def analizar_primer_digito(votos_por_mesa: list[int], partido: str) -> BenfordResult:
    valores = [v for v in votos_por_mesa if v > 0]
    n = len(valores)

    conteos = {d: 0 for d in range(1, 10)}
    for v in valores:
        d1 = int(str(v)[0])
        conteos[d1] += 1

    obs = {d: conteos[d] / n for d in range(1, 10)} if n > 0 else {d: 0.0 for d in range(1, 10)}

    chi2 = 0.0
    mad_sum = 0.0
    for d in range(1, 10):
        expected = BENFORD_FIRST[d] * n
        chi2 += (conteos[d] - expected) ** 2 / expected if expected > 0 else 0
        mad_sum += abs(obs[d] - BENFORD_FIRST[d])
    mad = mad_sum / 9

    p = _chi2_pvalue(chi2, 8)

    return BenfordResult(
        partido=partido,
        digito_tipo="primero",
        n=n,
        distribucion_observada={d: round(obs[d], 6) for d in range(1, 10)},
        distribucion_esperada={d: round(BENFORD_FIRST[d], 6) for d in range(1, 10)},
        conteos=conteos,
        chi2=round(chi2, 4),
        p_valor=round(p, 6),
        mad=round(mad, 6),
        conformidad=_mad_conformidad(mad),
    )


def analizar_segundo_digito(votos_por_mesa: list[int], partido: str) -> BenfordResult:
    valores = [v for v in votos_por_mesa if v >= 10]
    n = len(valores)

    conteos = {d: 0 for d in range(10)}
    for v in valores:
        d2 = int(str(v)[1])
        conteos[d2] += 1

    obs = {d: conteos[d] / n for d in range(10)} if n > 0 else {d: 0.0 for d in range(10)}

    chi2 = 0.0
    mad_sum = 0.0
    for d in range(10):
        expected = BENFORD_SECOND[d] * n
        chi2 += (conteos[d] - expected) ** 2 / expected if expected > 0 else 0
        mad_sum += abs(obs[d] - BENFORD_SECOND[d])
    mad = mad_sum / 10

    p = _chi2_pvalue(chi2, 9)

    return BenfordResult(
        partido=partido,
        digito_tipo="segundo",
        n=n,
        distribucion_observada={d: round(obs[d], 6) for d in range(10)},
        distribucion_esperada={d: round(BENFORD_SECOND[d], 6) for d in range(10)},
        conteos=conteos,
        chi2=round(chi2, 4),
        p_valor=round(p, 6),
        mad=round(mad, 6),
        conformidad=_mad_conformidad(mad),
    )


async def run(db_url: str, top_n: int = 10) -> dict:
    """Ejecuta análisis de Benford para los top N partidos."""
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

            r1 = analizar_primer_digito(votos, partido)
            r2 = analizar_segundo_digito(votos, partido)
            resultados.append({"primer_digito": r1, "segundo_digito": r2})

    await pool.close()

    return {
        "analisis": "benford",
        "partidos": [
            {
                "partido": r["primer_digito"].partido,
                "primer_digito": {
                    "n": r["primer_digito"].n,
                    "chi2": r["primer_digito"].chi2,
                    "p_valor": r["primer_digito"].p_valor,
                    "mad": r["primer_digito"].mad,
                    "conformidad": r["primer_digito"].conformidad,
                    "observado": r["primer_digito"].distribucion_observada,
                    "esperado": r["primer_digito"].distribucion_esperada,
                    "conteos": r["primer_digito"].conteos,
                },
                "segundo_digito": {
                    "n": r["segundo_digito"].n,
                    "chi2": r["segundo_digito"].chi2,
                    "p_valor": r["segundo_digito"].p_valor,
                    "mad": r["segundo_digito"].mad,
                    "conformidad": r["segundo_digito"].conformidad,
                    "observado": r["segundo_digito"].distribucion_observada,
                    "esperado": r["segundo_digito"].distribucion_esperada,
                    "conteos": r["segundo_digito"].conteos,
                },
            }
            for r in resultados
        ],
    }
