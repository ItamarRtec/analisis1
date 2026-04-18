# Analysis 1 - Auditoría Estadística Forense

Elecciones Generales Perú 2026 - Primera vuelta.

Este directorio contiene el pipeline estadístico de `analysis 1`: export de metadata ONPE, tests forenses agregados, análisis heurístico por mesa y export de mesas sospechosas para auditoría documental posterior.

## Qué hace `analysis1`

`analysis1` produce cuatro capas de salida:

1. **Export de metadata ONPE** a CSVs locales.
2. **Tests estadísticos agregados**:
   - Ley de Benford
   - Último dígito
   - Klimek (participación vs porcentaje del candidato)
3. **Heurístico de micro-fraude por mesa** (`micro_fraude.py`).
4. **CSV de mesas sospechosas por partido** para revisión manual (`jp_sospechosas.csv` y equivalentes).

## Script recomendado

La forma recomendada de correr todo `analysis 1` ahora es:

```bash
python3 -m analysis.analysis1.main
```

Ese comando ejecuta, en orden:

1. `export_metadata.py`
2. `run.py` (Benford, último dígito y Klimek)
3. `micro_fraude.py`
4. `export_jp_sospechosas.py`

También funciona por ruta directa:

```bash
python3 analysis/analysis1/main.py
```

## Comandos más útiles

Desde la raíz del repo (`open-elections/`):

### 1. Correr el pipeline completo

```bash
python3 -m analysis.analysis1.main
```

### 2. Correr el pipeline completo sin re-exportar la metadata

Útil si ya existe `analysis/analysis1/store/data/mesa_completa.csv`.

```bash
python3 -m analysis.analysis1.main --skip-export
```

### 3. Correr el pipeline completo con otra base de datos

```bash
python3 -m analysis.analysis1.main --db postgresql://user:pass@host/db
```

### 4. Exportar mesas sospechosas de otro partido

```bash
python3 -m analysis.analysis1.main --party "RENOVACIÓN POPULAR"
```

### 5. Enriquecer el CSV con metadata fresca de ONPE

```bash
python3 -m analysis.analysis1.main --enrich-onpe
```

### 6. Solo correr micro-fraude

Esto genera `resultados/micro_fraude.json` a partir de `store/data/mesa_completa.csv`.

```bash
python3 -m analysis.analysis1.micro_fraude
```

### 7. Solo exportar mesas sospechosas

Esto toma `resultados/micro_fraude.json` y genera `resultados/jp_sospechosas.csv`.

```bash
python3 -m analysis.analysis1.export_jp_sospechosas
```

Opciones frecuentes:

```bash
python3 -m analysis.analysis1.export_jp_sospechosas --party "JUNTOS POR EL PERÚ"
python3 -m analysis.analysis1.export_jp_sospechosas --limit 50
python3 -m analysis.analysis1.export_jp_sospechosas --enrich-onpe
```

### 8. Solo exportar metadata ONPE

```bash
python3 -m analysis.analysis1.export_metadata
```

### 9. Solo correr los análisis estadísticos agregados

```bash
python3 -m analysis.analysis1.run
```

Nota: `run.py` **no** corre `micro_fraude.py`. Para el flujo completo usa `main.py`.

## Qué archivos genera

### Datos exportados

En `analysis/analysis1/store/data/`:

- `mesas_geo.csv`: geografía y estado general por mesa.
- `mesa_timeline.csv`: historial de estados ONPE por mesa.
- `mesa_votos.csv`: votos por partido por mesa.
- `mesa_completa.csv`: dataset pivoteado, una fila por mesa.
- `metadata.json`: resumen estadístico de la exportación.

### Resultados estadísticos

En `analysis/analysis1/resultados/`:

- `benford.json`
- `ultimo_digito.json`
- `klimek.json`
- `resumen.json`

### Resultados heurísticos

También en `analysis/analysis1/resultados/`:

- `micro_fraude.json`: ranking por mesa con score, partido sospechoso, z-score y votos excedentes estimados.
- `jp_sospechosas.csv`: export filtrado de mesas top 0.2% donde el partido sospechoso es JP.

Si cambias `--party`, el contenido exportado corresponde a ese partido aunque el nombre por defecto del output siga siendo `jp_sospechosas.csv`, salvo que luego sobrescribas el path manualmente.

## Qué significa cada script

- `main.py`: entrypoint completo y recomendado.
- `run.py`: exporta metadata y corre Benford, último dígito y Klimek.
- `export_metadata.py`: vuelca la metadata ONPE a CSV.
- `micro_fraude.py`: genera el score heurístico por mesa y marca el top 0.2%.
- `export_jp_sospechosas.py`: filtra `micro_fraude.json` por partido y exporta CSV.
- `benford.py`, `last_digit.py`, `klimek.py`: implementaciones individuales de los tests.
- `stats.py`: utilidades estadísticas compartidas.

## Estructura del directorio

```text
analysis1/
|-- README.md
|-- metodologia.md
|-- main.py
|-- run.py
|-- export_metadata.py
|-- export_jp_sospechosas.py
|-- micro_fraude.py
|-- benford.py
|-- last_digit.py
|-- klimek.py
|-- stats.py
|-- resultados/
`-- store/data/
```

## Cobertura del dataset

Snapshot exportado el `2026-04-18 15:34 UTC`.

| Concepto | Cantidad | % del total |
|---|---:|---:|
| Total mesas descubiertas | 92,766 | 100% |
| Contabilizadas (estado `C`) | 86,664 | 93.42% |
| Con datos de votos verificados | 86,668 | 93.43% |
| Enviadas al JEE (estado `E`) | 5,759 | 6.21% |
| Pendientes (estado `P`) | 343 | 0.37% |
| Observadas (estado `H`) | 5,732 | 6.18% |
| Departamentos | 30 | - |
| Provincias | 273 | - |
| Distritos | 1,928 | - |
| Partidos políticos | 41 | - |

## Fuente de datos

Fuente principal: API pública de ONPE `resultadoelectoral.onpe.gob.pe/presentacion-backend`.

Cada mesa se consulta individualmente por su código vía `/actas/buscar/mesa`. El pipeline no modifica ni reinterpreta los datos fuente; solo los exporta, ordena y analiza.

## Reproducibilidad

Cualquier persona con acceso a la base local o a la metadata exportada puede replicar el proceso:

1. Exportar la metadata con `python3 -m analysis.analysis1.export_metadata`.
2. Correr el pipeline completo con `python3 -m analysis.analysis1.main`.
3. Comparar `resultados/*.json` y `resultados/*.csv`.

El código, la metodología y los outputs son abiertos.
