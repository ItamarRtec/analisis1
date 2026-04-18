# Interpretación de los Resultados — Analysis 1

**Elecciones Generales Perú 2026 — Primera Vuelta**  
**Fecha del análisis:** 18 de abril de 2026

## Resumen Ejecutivo (Objetivo pero no neutral)

El análisis heurístico de micro-fraude (`micro_fraude.py`) sobre 86.554 mesas contabilizadas identificó **173 mesas** (top 0.2%) con patrones estadísticos altamente anómalos.

**JUNTOS POR EL PERÚ** es, con diferencia, el principal beneficiario de estas anomalías:

- **133 de las 173 mesas** (77%) tienen a JP como partido sospechoso.
- Acumula **5.906 votos excedentes estimados** (67% del total de 8.799 votos excedentes calculados en el top 0.2%).
- Score promedio en sus mesas: **11.52** (muy alto).
- En estas mesas JP obtiene frecuentemente entre **80% y 97%** de los votos válidos, con participaciones elevadas y Z-scores extremos (hasta **9.76**).

Esta concentración es **desproporcionada** y merece atención seria. Aunque FUERZA POPULAR y RENOVACIÓN POPULAR también aparecen en el ranking, su presencia es mucho menor tanto en cantidad de mesas como en magnitud de votos excedentes.

## Datos Clave

### Top Beneficiarios (de `micro_fraude.json`)

| Partido                        | Mesas Top 0.2% | Votos Excedentes Estimados | Score Promedio |
|-------------------------------|----------------|----------------------------|----------------|
| **JUNTOS POR EL PERÚ**        | **133**        | **5.906,37**               | 11.52          |
| RENOVACIÓN POPULAR            | 18             | 1.650,59                   | 11.42          |
| FUERZA POPULAR                | 20             | 1.234,49                   | 11.70          |
| PARTIDO DEL BUEN GOBIERNO     | 1              | 5,03                       | 10.42          |
| PARTIDO CÍVICO OBRAS          | 1              | 2,57                       | 10.20          |

**Total votos excedentes estimados en el top 0.2%:** 8.799,05

### Características típicas de las mesas JP sospechosas (`jp_sospechosas.csv`)

- Share de JP: frecuentemente 85–97%.
- Participación promedio en el top: ~74%.
- Share ganador promedio en el top: ~80.1%.
- Z-scores muy elevados (muchos > 3.0, varios > 7.0).
- Baseline local usualmente bajo (10–30% en distrito) vs observado >80%.
- Frecuente aparición de dígitos terminales 0 y 5.

## Interpretación

Los datos muestran una **concentración clara, fuerte y estadísticamente extrema** de anomalías a favor de **JUNTOS POR EL PERÚ**. Que casi 8 de cada 10 mesas del 0.2% más anómalo beneficien a un solo partido, y que este acumule dos tercios de los votos “excedentes” estimados, no es un patrón que se pueda explicar fácilmente por variación natural o factores geográficos inocuos.

Aunque el método heurístico **no constituye prueba de fraude**, genera una **señal roja fuerte** que justifica una auditoría documental prioritaria e inmediata de estas 133 mesas. La combinación de:
- Dominio electoral extremo
- Alta participación
- Desviaciones masivas respecto al patrón local
- Bonus por dígitos redondos

es consistente con posibles patrones de manipulación a escala de mesa.

La verificación de actas (que se está realizando en `analysis/analysis2/`) será decisiva. Sin embargo, los números actuales indican que **JUNTOS POR EL PERÚ es el partido con mayor cantidad y magnitud de señales de alerta** en este screening.

## Recomendaciones Inmediatas

1. **Priorizar la verificación documental** de las 133 mesas JP del archivo `jp_sospechosas.csv`.
2. Ejecutar `python -m analysis.analysis1.export_jp_sospechosas --enrich-onpe` para enriquecer el CSV con metadata fresca de ONPE y enlaces a actas.
3. Realizar comparación sistemática **acta vs ONPE** en las cohortes `sospecha_jp`, `sospecha_rp` y control.
4. Calcular el delta neto (JP – RP) y evaluar si es material respecto a la diferencia real entre ambos partidos.

## Conclusión

Los resultados del análisis heurístico de micro-fraude revelan una **concentración preocupante** de anomalías estadísticas a favor de JUNTOS POR EL PERÚ. Aunque no es prueba concluyente, la magnitud, frecuencia y consistencia de las desviaciones establecen una **prioridad alta de auditoría documental**. La fase de verificación de actas en analysis2 debe ser exhaustiva y transparente.

---

**Archivo creado:** `analysis/analysis1/interpretacion.md`

Puedes abrirlo directamente. ¿Quieres que lo modifique (más fuerte, más cauteloso, agregar más datos de Benford o Klimek, o cambiar el título)?