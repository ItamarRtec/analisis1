"""Utilidades estadísticas compartidas."""

from scipy.stats import chi2


def chi2_pvalue(statistic: float, df: int) -> float:
    return float(chi2.sf(statistic, df))
