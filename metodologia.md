# Metodología de Auditoría Electoral Estadística

## Open Election — Elecciones Generales Perú 2026

### Fuente de datos

Todos los análisis operan sobre la metadata pública de ONPE, descargada mesa por mesa desde la API `resultadoelectoral.onpe.gob.pe/presentacion-backend/actas/buscar/mesa`. No se modifica, filtra ni reinterpreta ningún dato. Cada registro en nuestra base de datos corresponde exactamente a lo que ONPE publica para esa mesa.

**Universo:** ~86,000+ mesas de sufragio con estado "Contabilizada" (código `C`) en el timeline de ONPE, con datos de votos verificados en nuestra base PostgreSQL.

**Campos por mesa:**
- `codigo_mesa`: identificador único
- `departamento`, `provincia`, `distrito`: ubicación geográfica
- `electores_habiles`: votantes registrados
- `total_votos_emitidos`: votos efectivamente emitidos
- `participacion_pct`: porcentaje de participación
- `votos` por partido: conteo individual para cada agrupación política
- `fecha_registro` del estado `C`: timestamp de contabilización

---

## Análisis 1: Ley de Benford (primer y segundo dígito)

### Fundamento

La Ley de Benford establece que en conjuntos de datos numéricos que surgen naturalmente (poblaciones, áreas, resultados electorales por mesa), el primer dígito significativo no se distribuye uniformemente. El dígito 1 aparece como primer dígito ~30.1% de las veces, el 2 ~17.6%, y así sucesivamente hasta el 9 con ~4.6%.

La distribución teórica del primer dígito `d` (d = 1, 2, ..., 9) es:

```
P(d) = log₁₀(1 + 1/d)
```

| Dígito | Probabilidad esperada |
|--------|----------------------|
| 1      | 30.10%               |
| 2      | 17.61%               |
| 3      | 12.49%               |
| 4      |  9.69%               |
| 5      |  7.92%               |
| 6      |  6.69%               |
| 7      |  5.80%               |
| 8      |  5.12%               |
| 9      |  4.58%               |

Para el segundo dígito (d = 0, 1, ..., 9):

```
P(d₂) = Σ(d₁=1..9) log₁₀(1 + 1/(10·d₁ + d₂))
```

### Aplicación a datos electorales

Extraemos el primer y segundo dígito del conteo de votos de cada partido en cada mesa. Mesas con 0 votos se excluyen (el 0 no tiene primer dígito significativo).

**Unidad de análisis:** votos por partido por mesa (ej: FUERZA POPULAR obtuvo 47 votos en mesa 000123 → primer dígito = 4, segundo dígito = 7).

**Alcance:** se ejecuta el test para cada partido con representación significativa (top 10 por votos nacionales), y también de forma agregada.

### Test estadístico

Se aplica el test **chi-cuadrado (χ²)** comparando frecuencias observadas vs esperadas:

```
χ² = Σ (observado_i - esperado_i)² / esperado_i
```

Con 8 grados de libertad (primer dígito) o 9 (segundo dígito). Un p-valor < 0.05 indica desviación significativa de Benford. Se reporta también la **Distancia media absoluta (MAD)** como medida de efecto:

- MAD < 0.006: conformidad cercana
- MAD 0.006–0.012: conformidad aceptable
- MAD 0.012–0.015: conformidad marginal
- MAD > 0.015: no conformidad

### Limitaciones

- Benford funciona mejor cuando los datos abarcan varios órdenes de magnitud. En mesas electorales peruanas (~200-300 electores), los votos por partido típicamente van de 1 a ~120, lo cual cubre ~2 órdenes de magnitud. Esto es aceptable pero no ideal.
- Un resultado conforme a Benford NO prueba ausencia de fraude. Un resultado no conforme NO prueba fraude. Es un indicador que debe interpretarse junto con los otros análisis.
- Partidos muy pequeños (con muchas mesas en 0-9 votos) pueden mostrar desviaciones naturales.

---

## Análisis 2: Uniformidad del último dígito

### Fundamento

A diferencia del primer dígito, el último dígito de conteos naturales debe distribuirse de forma **uniforme** entre 0 y 9. Cada dígito debería aparecer ~10% de las veces. Esta propiedad es robusta e independiente de la distribución subyacente.

Cuando los números son fabricados o alterados manualmente, los humanos tienden a:
- Evitar el 0 (parece "demasiado redondo")
- Favorecer el 5 (parece "promedio")
- Repetir ciertos dígitos (sesgo cognitivo)

Este test es **más difícil de engañar** que Benford porque no hay una distribución "natural" compleja que imitar — simplemente debe ser plano.

### Aplicación

Para cada partido, extraemos el último dígito del conteo de votos en cada mesa. Mesas con 0 votos se incluyen (el 0 es un último dígito válido).

**Unidad de análisis:** último dígito de votos por partido por mesa.

### Test estadístico

Test **chi-cuadrado (χ²)** contra distribución uniforme:

```
esperado_i = N / 10  (para cada dígito 0-9)
χ² = Σ (observado_i - esperado_i)² / esperado_i
```

Con 9 grados de libertad. p-valor < 0.05 indica desviación significativa de uniformidad.

Se reporta también la **desviación máxima** (max |observado_i/N - 0.10|) como indicador visual de qué dígito es anómalo.

### Limitaciones

- En mesas con pocos votos (0-9), el último dígito ES el número completo, lo que puede generar artefactos. Se puede filtrar mesas con votos ≥ 10 como test de robustez.
- Desviaciones pequeñas pero estadísticamente significativas son comunes en muestras grandes (N > 80,000). Se debe evaluar el tamaño del efecto, no solo el p-valor.

---

## Análisis 3: Klimek — Participación vs porcentaje del candidato

### Fundamento

Este método, desarrollado por Klimek, Yegorov y Thurner (2012) y publicado en *Proceedings of the National Academy of Sciences*, detecta el "fingerprint" estadístico del relleno de urnas (ballot stuffing).

**Principio:** en elecciones limpias, la participación electoral y el porcentaje de un candidato son variables esencialmente independientes. Si alguien agrega boletas fraudulentas a favor de un candidato, ambas variables se inflan simultáneamente: la participación sube (hay más boletas) y el % del candidato sube (las boletas extras son para él). Esto crea una correlación positiva anómala visible en un gráfico 2D.

### Visualización

Se construye un **histograma 2D (heatmap)** donde:
- **Eje X:** participación de la mesa (votos_emitidos / electores_habiles × 100)
- **Eje Y:** porcentaje del candidato en esa mesa (votos_candidato / votos_válidos × 100)
- **Color:** densidad de mesas en cada celda

**Patrón limpio:** una nube concentrada sin cola hacia la esquina superior derecha.

**Patrón sospechoso:** una "cola" o extensión hacia la esquina (100% participación, alto % del candidato), formando una distribución bimodal o una elongación diagonal.

### Aplicación

Para cada uno de los top 5 candidatos, generamos el heatmap participación × porcentaje usando bins de 1 punto porcentual en cada eje.

**Variables por mesa:**
- `participacion = total_votos_emitidos / electores_habiles × 100`
- `pct_candidato = votos_candidato / total_votos_validos × 100`

Se filtra: mesas con electores_habiles > 0 y total_votos_emitidos > 0.

### Métricas complementarias

Además del heatmap visual, calculamos:

1. **Coeficiente de correlación de Pearson** entre participación y % del candidato. En elecciones limpias debería ser cercano a 0.
2. **Exceso de mesas con participación > 90%**: qué porcentaje del total superan este umbral.
3. **Test de simetría**: la distribución de participación debería ser aproximadamente simétrica. Asimetría positiva fuerte (cola derecha) sugiere inflado.

### Desglose geográfico

El análisis se ejecuta:
- **Nacional:** todas las mesas juntas
- **Por departamento:** permite identificar si las anomalías (si las hay) son nacionales o focalizadas en regiones específicas

### Referencia académica

> Klimek, P., Yegorov, Y., Harre, R., & Thurner, S. (2012). Statistical detection of systematic election irregularities. *Proceedings of the National Academy of Sciences*, 109(41), 16469-16473.

Este método fue aplicado exitosamente para documentar irregularidades en:
- Rusia 2011 (elecciones parlamentarias)
- Irán 2009 (elección presidencial)
- Bielorrusia 2020 (elección presidencial)
- Uganda 2011 (elección presidencial)

---

## Análisis 4: Micro-fraude Heurístico y Mesas Sospechosas (`jp_sospechosas.csv`)

### Fundamento

Además de los tests estadísticos globales, se aplica un **análisis heurístico a nivel de cada mesa individual** (`micro_fraude.py`). Su objetivo **no es probar fraude**, sino:

1. Asignar un *score* de anomalía a cada una de las ~86.500 mesas contabilizadas.
2. Identificar el **top 0.2% más sospechosas** (~173 mesas).
3. Estimar un "techo" de votos excedentes comparando el share observado contra el **patrón local** (promedio del distrito, provincia o departamento).
4. Generar cohortes prioritarias (`sospecha_jp`, `sospecha_rp` y control) para la verificación documental en Analysis 2.

### Criterios del Score por Mesa

El score (redondeado a 4 decimales) combina varios factores (ver código para pesos exactos):

- **Participación extrema**: Puntos si >85%, bonus fuerte >90-95%.
- **Dominio del ganador**: Share del winner >55%, puntos adicionales por margen grande.
- **Z-score del share**: Desviación estandarizada del % de un partido top vs **baseline local**. Z > 2.0 es notable; Z > 4-7 extremadamente raro. Se prefiere baseline del distrito si hay suficientes mesas (>25).
- **Dígitos redondos**: Bonus si votos del winner o emitidos terminan en 0 o 5 (posible indicador de manipulación manual).
- **Bonos por combinaciones**: Ej. turnout ≥95% + z≥3.0 da bonus significativo.

**Estimated excess votes** = `(share_observado - baseline_local) × total_válidos`. Indica cuántos votos "extras" parecería haber recibido el partido sospechoso respecto al patrón geográfico cercano.

**flag_top_0_2_pct**: Marca las 173 mesas con mayor score (0.2% del total). Estas son las "mesas sospechosas".

### Qué Significan las Mesas en `jp_sospechosas.csv`

Este CSV exporta las mesas del top 0.2% donde el partido beneficiario (`suspicious_party`) es **JUNTOS POR EL PERÚ**:

- **Características típicas**:
  - 75-97% de los votos válidos para JP (muchas >85-90%).
  - Participación frecuentemente alta (70-95%+).
  - Z-scores de 2.3 a 9.7 (ej: baseline distrito ~10-30% vs observado 85-95%).
  - Estimated excess votes: 20-110 por mesa.
- **Estadísticas agregadas** (del `micro_fraude.json`):
  - Top 0.2% total: 173 mesas.
  - Turnout promedio en top: ~74%.
  - Share ganador promedio en top: ~80%.
  - Votos excedentes estimados totales: ~8,800.

**Uso**: Estas mesas se priorizan para **descargar y verificar las actas originales** (PDFs de ONPE). Se comparan los números en el acta vs los publicados por ONPE para calcular deltas (ver `analysis/analysis2/`).

### Export y Verificación

- `export_jp_sospechosas.py`: Convierte `micro_fraude.json` → CSV filtrado por partido y `flag_top_0_2_pct`. Soporta `--enrich-onpe` para agregar metadata fresca de la API de ONPE.
- Se integra con `analysis/analysis2/verificar_actas.py` y `cohortes.py` para formar cohortes balanceadas y auditar documentalmente.

### Limitaciones

- Un alto score puede deberse a voto geográficamente concentrado legítimo.
- El baseline local podría estar afectado si el fraude es sistemático en la zona.
- **Siempre requiere verificación manual de las actas**. El análisis estadístico solo prioriza.
- No se debe extrapolar automáticamente los resultados de la muestra.

Ver `analysis/analysis2/metodologia.md` para la metodología completa de verificación JP vs RP vs control.

---

## Implementación

Cada análisis se implementa como un módulo Python independiente en `/analysis/analysis1/`:

| Módulo | Función | Output principal |
|--------|---------|------------------|
| `main.py` | Pipeline completo recomendado | Export + JSON + CSV |
| `export_metadata.py` | Export de metadata ONPE a CSV | `store/data/*.csv`, `metadata.json` |
| `run.py` | Benford + último dígito + Klimek | `benford.json`, `ultimo_digito.json`, `klimek.json`, `resumen.json` |
| `micro_fraude.py` | Heurístico por mesa y ranking top 0.2% | `micro_fraude.json` |
| `export_jp_sospechosas.py` | Filtrado/exporte de mesas sospechosas por partido | `jp_sospechosas.csv` |
| `benford.py` | Ley de Benford (1er y 2do dígito) | JSON detallado |
| `last_digit.py` | Uniformidad del último dígito | JSON detallado |
| `klimek.py` | Participación vs % candidato | JSON + heatmaps 2D |
| `stats.py` | Utilidades estadísticas | soporte interno |

### Pipeline operativo

El flujo recomendado de ejecución es:

1. **Exportar metadata ONPE** desde PostgreSQL hacia `store/data/`.
2. **Correr los análisis estadísticos agregados** (`Benford`, `último dígito`, `Klimek`).
3. **Correr `micro_fraude.py`** sobre `store/data/mesa_completa.csv`.
4. **Filtrar y exportar las mesas sospechosas** por partido con `export_jp_sospechosas.py`.

Ese flujo ya está consolidado en `main.py`, que es el entrypoint recomendado.

### Comandos recomendados

Desde la raíz del repositorio:

```bash
# Pipeline completo recomendado
python3 -m analysis.analysis1.main

# Igual, pero reutilizando el CSV ya exportado
python3 -m analysis.analysis1.main --skip-export

# Solo los tests estadísticos agregados
python3 -m analysis.analysis1.run

# Solo micro-fraude
python3 -m analysis.analysis1.micro_fraude

# Solo exportar mesas sospechosas
python3 -m analysis.analysis1.export_jp_sospechosas
```

También se puede correr por ruta directa:

```bash
python3 analysis/analysis1/main.py
```

### Outputs esperados

- `store/data/mesa_completa.csv`: insumo principal para `micro_fraude.py`.
- `resultados/benford.json`, `ultimo_digito.json`, `klimek.json`: resultados agregados.
- `resultados/micro_fraude.json`: ranking por mesa con score, z-score local, partido sospechoso y votos excedentes estimados.
- `resultados/jp_sospechosas.csv`: subconjunto top 0.2% filtrado por partido, listo para auditoría manual o enriquecimiento ONPE.

Los resultados se publican en la sección "Análisis" del dashboard con gráficos interactivos y datos descargables en JSON/CSV. Las mesas sospechosas se usan además como insumo para `analysis/analysis2/`.

---

## Principios de la auditoría

1. **Transparencia total:** el código fuente completo, la metodología detallada, los datos crudos y los scripts de análisis son públicos (ver carpeta `@analysis/`).
2. **Sin interpretación editorial:** reportamos resultados estadísticos, scores heurísticos y deltas documentales. **Nunca declaramos "fraude" ni "elección limpia"** — presentamos evidencia cuantificable y reproducible.
3. **Reproducibilidad:** cualquier persona con acceso a la API de ONPE o los CSVs exportados puede replicar todos los pasos (incluyendo `micro_fraude.py` y verificación de actas).
4. **Screening + Verificación:** Los tests estadísticos (Benford, último dígito, Klimek) y el heurístico de micro-fraude (`top 0.2%` / `jp_sospechosas`) sirven **solo para priorizar**. La evidencia principal viene de la verificación documental de actas en `analysis/analysis2/`.
5. **Neutralidad y múltiples capas:** Ningún test individual es concluyente. Se requiere convergencia entre screening estadístico, cohortes balanceadas (sospecha JP, sospecha RP, control) y deltas netos verificados en las actas físicas/digitales.

Las "mesas sospechosas" son una herramienta de priorización, no una conclusión. Su significado es: **mesas que se desvían fuertemente del patrón local de voto y merecen ser auditadas manualmente comparando el acta original con los datos publicados por ONPE**.
