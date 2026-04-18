# Interpretación de los Resultados — Analysis 1

**Elecciones Generales Perú 2026 — Primera Vuelta**  
**Fecha del análisis:** 18 de abril de 2026

## Resumen Ejecutivo

El análisis heurístico de micro-fraude (`micro_fraude.py`) sobre 86.554 mesas contabilizadas identificó **173 mesas** (top 0.2%) con patrones estadísticos anómalos.

**JUNTOS POR EL PERÚ** es el principal beneficiario de estas anomalías:

- **133 de las 173 mesas** (77%) tienen a JP como partido sospechoso.
- Acumula **5.906 votos excedentes estimados** (67% del total de 8.799 votos excedentes calculados en el top 0.2%).
- Score promedio en sus mesas: **11.52**.

FUERZA POPULAR (20 mesas) y RENOVACIÓN POPULAR (18 mesas) también aparecen en el ranking, pero con menor presencia.

## Datos Clave

### Top Beneficiarios (de `micro_fraude.json`)

| Partido                        | Mesas Top 0.2% | Votos Excedentes Estimados | Score Promedio |
|-------------------------------|----------------|----------------------------|----------------|
| **JUNTOS POR EL PERÚ**        | **133**        | **5.906,37**               | 11.52          |
| FUERZA POPULAR                | 20             | 1.234,49                   | 11.70          |
| RENOVACIÓN POPULAR            | 18             | 1.650,59                   | 11.42          |
| PARTIDO DEL BUEN GOBIERNO     | 1              | 5,03                       | 10.42          |
| PARTIDO CÍVICO OBRAS          | 1              | 2,57                       | 10.20          |

**Total votos excedentes estimados en el top 0.2%:** 8.799,05

### Distribución real de las 133 mesas JP (`jp_sospechosas.csv`)

**Share de JP:**
- Rango: **10.99% a 97.62%**
- Promedio: 81.64%
- 80 de 133 mesas (60%) están por debajo de 85%
- 53 mesas (40%) están entre 85% y 98%
- 2 mesas están por debajo de 50%

| Rango share JP | Mesas |
|----------------|------:|
| 0–30%          |     1 |
| 30–50%         |     1 |
| 50–65%         |     2 |
| 65–75%         |    22 |
| 75–85%         |    54 |
| 85–95%         |    50 |
| 95–100%        |     3 |

**Participación:**
- Rango: **9.3% a 97.3%**
- Promedio: 71.3%
- 55 mesas (41%) tienen participación menor a 70%
- 15 mesas tienen participación menor a 50%

**Z-scores:** hasta 9.76. El z-score mide la desviación del share de JP respecto al promedio de su propio distrito (no del promedio nacional).

## Nota sobre el score

El score de cada mesa combina cuatro factores:
- **Participación extrema** (>85%)
- **Dominio del ganador** (share y margen del winner)
- **Z-score del partido sospechoso** (desviación vs baseline local)
- **Bonus** por combinaciones y dígitos redondos

Los componentes de dominio y margen se calculan sobre el partido **ganador** de la mesa, no sobre el partido sospechoso. En 132 de 133 mesas JP coinciden (JP es ganador y sospechoso), pero conceptualmente son variables distintas. Esto no invalida el ranking, pero debe tenerse en cuenta al interpretar el score.

## Interpretación

Que 77% de las mesas del top 0.2% más anómalo beneficien a un solo partido, y que este acumule dos tercios de los votos excedentes estimados, es una concentración que merece atención.

Sin embargo, esta señal tiene matices importantes:

- **No todas las mesas muestran el mismo patrón.** La mayoría (60%) tiene un share de JP menor a 85%, y muchas tienen participación baja. No se trata de un bloque homogéneo de mesas con dominio extremo + participación inflada.
- **El baseline local tiene limitaciones.** En distritos con pocas mesas (<25), el análisis usa la provincia o el departamento como referencia, lo que pierde granularidad. Una comunidad rural puede votar legítimamente 90% por un partido sin que eso sea anómalo a escala local.
- **JP tiene presencia fuerte en zonas rurales** (sierra central, selva, Cajamarca), donde el voto concentrado es estructural, no necesariamente sospechoso.

El método heurístico **no constituye prueba de fraude**. Señala mesas que se desvían del patrón local y las prioriza para revisión. La verificación documental (comparar las actas físicas contra lo que ONPE digitó) es lo que puede confirmar o descartar irregularidades.

## Recomendaciones

1. **Verificación documental** de las 133 mesas JP en `jp_sospechosas.csv` — descargar actas y comparar contra datos ONPE.
2. **Aplicar el mismo análisis a otros partidos** para evaluar si la concentración de JP es proporcional a su presencia rural o genuinamente anómala.
3. Realizar comparación sistemática **acta vs ONPE** en cohortes: sospechosas JP, sospechosas RP/FP, y un grupo de control.

## Conclusión

El análisis identifica una concentración de anomalías estadísticas a favor de JUNTOS POR EL PERÚ que justifica una revisión documental prioritaria. No es prueba de fraude. La fase de verificación de actas determinará si las desviaciones reflejan irregularidades reales o patrones legítimos de voto rural concentrado.

El código, la metodología y los datos son abiertos. Cualquiera puede replicar y cuestionar el análisis.

---
