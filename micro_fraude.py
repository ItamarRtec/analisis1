"""
Analisis heuristico de micro-fraude sobre mesas contabilizadas.

Este modulo NO "prueba fraude". Sirve para:
1. Puntuar mesas anomales a escala fina.
2. Identificar clusters geograficos pequenos.
3. Estimar un techo de votos "excedentes" frente al patron local.

La idea central es aislar el 0.2% de mesas mas anomalo, que es el orden
de magnitud que el usuario quiere auditar.

Uso:
  python3 -m analysis.analysis1.micro_fraude
  python3 -m analysis.analysis1.micro_fraude --csv analysis/analysis1/store/data/mesa_completa.csv
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

DIR = Path(__file__).parent
DEFAULT_CSV = DIR / "store" / "data" / "mesa_completa.csv"
RESULTS_DIR = DIR / "resultados"
RESULTS_PATH = RESULTS_DIR / "micro_fraude.json"

BASE_COLS = {
    "codigo_mesa",
    "ubigeo",
    "departamento",
    "provincia",
    "distrito",
    "nombre_local",
    "electores_habiles",
    "estado_acta",
    "contabilizada",
    "fecha_contabilizada",
    "votos_emitidos",
    "participacion_pct",
}

EXCLUDED_VOTE_COLS = {
    "VOTOS EN BLANCO",
    "VOTOS NULOS",
    "VOTOS IMPUGNADOS",
}


def _safe_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def _normalize_codigo_mesa(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.replace(r"\.0$", "", regex=True).str.zfill(6)


def _party_columns(df: pd.DataFrame) -> list[str]:
    cols: list[str] = []
    for col in df.columns:
        if col in BASE_COLS:
            continue
        if col in EXCLUDED_VOTE_COLS:
            continue
        if col.startswith("Unnamed"):
            continue
        cols.append(col)
    return cols


def _stats_by_geo(df: pd.DataFrame, share_col: str, geo_col: str) -> dict[str, tuple[float, float, int]]:
    grouped = df.groupby(geo_col, dropna=False)[share_col].agg(["mean", "std", "count"]).reset_index()
    stats: dict[str, tuple[float, float, int]] = {}
    for _, row in grouped.iterrows():
        key = str(row[geo_col])
        mean = float(row["mean"])
        std = float(row["std"]) if not math.isnan(float(row["std"])) else 0.0
        count = int(row["count"])
        stats[key] = (mean, std, count)
    return stats


def _baseline_for(
    row: dict[str, str],
    geo_stats: dict[str, dict[str, tuple[float, float, int]]],
    global_stats: tuple[float, float, int],
    min_cluster: int,
) -> tuple[float, float, str, int]:
    for geo_col in ("distrito", "provincia", "departamento"):
        key = str(row[geo_col])
        stats = geo_stats[geo_col].get(key)
        if stats is None:
            continue
        mean, std, count = stats
        if count >= min_cluster and std > 0:
            return mean, std, geo_col, count
    mean, std, count = global_stats
    return mean, std if std > 0 else 1e-9, "nacional", count


def _clip(value: float, low: float = 0.0, high: float = 999.0) -> float:
    return max(low, min(value, high))


def run(csv_path: Path, top_n_parties: int = 5, min_cluster: int = 25) -> dict:
    df = pd.read_csv(csv_path, low_memory=False, dtype={"codigo_mesa": str})
    df = df[df["contabilizada"] == "SI"].copy()
    df["codigo_mesa"] = _normalize_codigo_mesa(df["codigo_mesa"])

    party_cols = _party_columns(df)
    for col in party_cols + ["electores_habiles", "votos_emitidos", "participacion_pct"]:
        df[col] = _safe_num(df[col])

    missing_eh = (df["electores_habiles"] <= 0) & (df["participacion_pct"] > 0) & (df["votos_emitidos"] > 0)
    df.loc[missing_eh, "electores_habiles"] = (
        df.loc[missing_eh, "votos_emitidos"] * 100 / df.loc[missing_eh, "participacion_pct"]
    ).round()

    df["total_validos"] = df[party_cols].sum(axis=1)
    df = df[
        (df["total_validos"] > 0)
        & (df["electores_habiles"] > 0)
        & (df["votos_emitidos"] > 0)
        & (df["participacion_pct"] > 0)
    ].copy()

    national_totals = sorted(
        ((party, int(df[party].sum())) for party in party_cols),
        key=lambda item: item[1],
        reverse=True,
    )
    top_parties = [party for party, _ in national_totals[:top_n_parties]]

    share_cols: dict[str, str] = {}
    party_geo_stats: dict[str, dict[str, dict[str, tuple[float, float, int]]]] = {}
    party_global_stats: dict[str, tuple[float, float, int]] = {}

    for idx, party in enumerate(top_parties):
        share_col = f"share_top_{idx + 1}"
        share_cols[party] = share_col
        df[share_col] = df[party] / df["total_validos"]
        party_geo_stats[party] = {
            "departamento": _stats_by_geo(df, share_col, "departamento"),
            "provincia": _stats_by_geo(df, share_col, "provincia"),
            "distrito": _stats_by_geo(df, share_col, "distrito"),
        }
        party_global_stats[party] = (
            float(df[share_col].mean()),
            float(df[share_col].std(ddof=0)) if float(df[share_col].std(ddof=0)) > 0 else 1e-9,
            int(len(df)),
        )

    vote_matrix = df[party_cols].to_numpy(dtype=float)
    winner_indices = vote_matrix.argmax(axis=1)
    winner_votes = vote_matrix[np.arange(len(df)), winner_indices]
    if vote_matrix.shape[1] > 1:
        # Numpy partition keeps this cheap while avoiding a full sort.
        runner_votes = np.partition(vote_matrix, -2, axis=1)[:, -2]
    else:
        runner_votes = winner_votes * 0
    winner_parties = [party_cols[i] for i in winner_indices]

    df["winner_party"] = winner_parties
    df["winner_votes"] = winner_votes
    df["runner_votes"] = runner_votes
    df["winner_share_pct"] = df["winner_votes"] / df["total_validos"] * 100
    df["winner_margin_pct"] = (df["winner_votes"] - df["runner_votes"]) / df["total_validos"] * 100

    records: list[dict] = []
    for row in df.itertuples(index=False):
        row_map = {
            "departamento": str(row.departamento),
            "provincia": str(row.provincia),
            "distrito": str(row.distrito),
        }
        turnout = float(row.participacion_pct)
        total_validos = int(row.total_validos)
        winner_votes_int = int(row.winner_votes)
        winner_margin_pct = float(row.winner_margin_pct)
        winner_share_pct = float(row.winner_share_pct)

        suspicious_party = ""
        suspicious_party_share_pct = 0.0
        suspicious_party_z = 0.0
        baseline_mean_share_pct = 0.0
        baseline_source = "nacional"
        estimated_excess_votes = 0.0

        for party in top_parties:
            share_col = share_cols[party]
            actual_share = float(getattr(row, share_col))
            mean, std, source, _ = _baseline_for(
                row_map,
                party_geo_stats[party],
                party_global_stats[party],
                min_cluster=min_cluster,
            )
            z = (actual_share - mean) / std if std > 0 else 0.0
            if z > suspicious_party_z:
                suspicious_party = party
                suspicious_party_share_pct = actual_share * 100
                suspicious_party_z = z
                baseline_mean_share_pct = mean * 100
                baseline_source = source
                estimated_excess_votes = max(0.0, (actual_share - mean) * total_validos)

        turnout_score = _clip((turnout - 85.0) / 4.0)
        dominance_score = _clip((winner_share_pct - 55.0) / 8.0)
        margin_score = _clip((winner_margin_pct - 20.0) / 10.0)
        anomaly_score = _clip(suspicious_party_z - 1.5)

        combo_bonus = 0.0
        if turnout >= 95.0 and suspicious_party_z >= 3.0:
            combo_bonus += 2.0
        elif turnout >= 90.0 and suspicious_party_z >= 2.0:
            combo_bonus += 1.0
        if winner_votes_int % 10 in (0, 5):
            combo_bonus += 0.35
        if int(row.votos_emitidos) % 10 in (0, 5):
            combo_bonus += 0.15

        score = round(turnout_score + dominance_score + margin_score + anomaly_score + combo_bonus, 4)

        records.append(
            {
                "codigo_mesa": str(row.codigo_mesa),
                "departamento": str(row.departamento),
                "provincia": str(row.provincia),
                "distrito": str(row.distrito),
                "participacion_pct": round(turnout, 2),
                "votos_emitidos": int(row.votos_emitidos),
                "electores_habiles": int(row.electores_habiles),
                "total_validos": total_validos,
                "winner_party": str(row.winner_party),
                "winner_votes": winner_votes_int,
                "winner_share_pct": round(winner_share_pct, 2),
                "winner_margin_pct": round(winner_margin_pct, 2),
                "suspicious_party": suspicious_party,
                "suspicious_party_share_pct": round(suspicious_party_share_pct, 2),
                "suspicious_party_z": round(suspicious_party_z, 4),
                "baseline_mean_share_pct": round(baseline_mean_share_pct, 2),
                "baseline_source": baseline_source,
                "estimated_excess_votes": round(estimated_excess_votes, 2),
                "winner_last_digit": winner_votes_int % 10,
                "score": score,
            }
        )

    mesas_df = pd.DataFrame(records).sort_values(["score", "estimated_excess_votes"], ascending=[False, False])
    top_02_count = max(1, round(len(mesas_df) * 0.002))
    mesas_df["flag_top_0_2_pct"] = False
    mesas_df.loc[mesas_df.index[:top_02_count], "flag_top_0_2_pct"] = True

    district_summary = (
        mesas_df.groupby(["departamento", "provincia", "distrito"], dropna=False)
        .agg(
            mesas=("codigo_mesa", "count"),
            mesas_top_0_2_pct=("flag_top_0_2_pct", "sum"),
            score_total=("score", "sum"),
            score_promedio=("score", "mean"),
            max_score=("score", "max"),
            estimated_excess_votes=("estimated_excess_votes", "sum"),
        )
        .reset_index()
        .sort_values(["mesas_top_0_2_pct", "estimated_excess_votes", "max_score"], ascending=[False, False, False])
    )

    beneficiary_summary = (
        mesas_df[mesas_df["flag_top_0_2_pct"]]
        .groupby("suspicious_party", dropna=False)
        .agg(
            mesas_top_0_2_pct=("codigo_mesa", "count"),
            estimated_excess_votes=("estimated_excess_votes", "sum"),
            score_promedio=("score", "mean"),
        )
        .reset_index()
        .sort_values(["estimated_excess_votes", "mesas_top_0_2_pct"], ascending=[False, False])
    )

    result = {
        "analisis": "micro_fraude",
        "metodo": {
            "tipo": "heuristico",
            "descripcion": (
                "Score por mesa que combina participacion extrema, dominio del ganador, "
                "desvio local del share de partidos principales y pequenos bonos por redondez."
            ),
            "advertencia": (
                "No prueba fraude por si solo. Prioriza mesas para auditoria manual y compara "
                "contra el patron local para estimar un techo de votos excedentes."
            ),
        },
        "dataset": {
            "csv": str(csv_path),
            "mesas_analizadas": int(len(mesas_df)),
            "top_n_parties": int(top_n_parties),
            "top_parties": top_parties,
            "top_0_2_pct_mesas": int(top_02_count),
        },
        "resumen": {
            "score_maximo": round(float(mesas_df["score"].max()), 4),
            "score_promedio": round(float(mesas_df["score"].mean()), 4),
            "turnout_promedio_top_0_2_pct": round(
                float(mesas_df[mesas_df["flag_top_0_2_pct"]]["participacion_pct"].mean()), 2
            ),
            "winner_share_promedio_top_0_2_pct": round(
                float(mesas_df[mesas_df["flag_top_0_2_pct"]]["winner_share_pct"].mean()), 2
            ),
            "estimated_excess_votes_top_0_2_pct": round(
                float(mesas_df[mesas_df["flag_top_0_2_pct"]]["estimated_excess_votes"].sum()), 2
            ),
        },
        "top_mesas": mesas_df.head(200).to_dict(orient="records"),
        "top_distritos": district_summary.head(50).to_dict(orient="records"),
        "top_beneficiarios": beneficiary_summary.to_dict(orient="records"),
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default=str(DEFAULT_CSV))
    parser.add_argument("--top-parties", type=int, default=5)
    parser.add_argument("--min-cluster", type=int, default=25)
    parser.add_argument("--output", default=str(RESULTS_PATH))
    args = parser.parse_args()

    csv_path = Path(args.csv)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    result = run(csv_path=csv_path, top_n_parties=args.top_parties, min_cluster=args.min_cluster)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("=" * 60)
    print("  MICRO-FRAUDE HEURISTICO")
    print("=" * 60)
    print(f"Mesas analizadas: {result['dataset']['mesas_analizadas']:,}")
    print(f"Top 0.2% mesas: {result['dataset']['top_0_2_pct_mesas']:,}")
    print(f"Votos excedentes estimados (top 0.2%): {result['resumen']['estimated_excess_votes_top_0_2_pct']:,}")
    print("Top beneficiarios sospechosos:")
    for row in result["top_beneficiarios"][:5]:
        print(
            f"  {row['suspicious_party'][:35]:<35} "
            f"mesas={row['mesas_top_0_2_pct']:>4} "
            f"exceso={row['estimated_excess_votes']:>9.2f}"
        )
    print(f"Output: {output_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
