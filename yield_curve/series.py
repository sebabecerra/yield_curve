from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RateSeries:
    key: str
    label: str
    code: str
    months: int
    currency: str
    family: str = "spc"


RATE_SERIES = {
    "spc_pesos_2y": RateSeries(
        key="spc_pesos_2y",
        label="SPC en pesos 2 años",
        code="F022.SPC.TIN.AN02.NO.Z.D",
        months=24,
        currency="CLP",
    ),
    "spc_pesos_3y": RateSeries(
        key="spc_pesos_3y",
        label="SPC en pesos 3 años",
        code="F022.SPC.TIN.AN03.NO.Z.D",
        months=36,
        currency="CLP",
    ),
    "spc_pesos_4y": RateSeries(
        key="spc_pesos_4y",
        label="SPC en pesos 4 años",
        code="F022.SPC.TIN.AN04.NO.Z.D",
        months=48,
        currency="CLP",
    ),
    "spc_pesos_5y": RateSeries(
        key="spc_pesos_5y",
        label="SPC en pesos 5 años",
        code="F022.SPC.TIN.AN05.NO.Z.D",
        months=60,
        currency="CLP",
    ),
    "spc_pesos_10y": RateSeries(
        key="spc_pesos_10y",
        label="SPC en pesos 10 años",
        code="F022.SPC.TIN.AN10.NO.Z.D",
        months=120,
        currency="CLP",
    ),
    "spc_uf_1y": RateSeries(
        key="spc_uf_1y",
        label="SPC en UF 1 año",
        code="F022.SPC.TIN.AN01.UF.Z.D",
        months=12,
        currency="UF",
    ),
    "spc_uf_2y": RateSeries(
        key="spc_uf_2y",
        label="SPC en UF 2 años",
        code="F022.SPC.TIN.AN02.UF.Z.D",
        months=24,
        currency="UF",
    ),
    "spc_uf_3y": RateSeries(
        key="spc_uf_3y",
        label="SPC en UF 3 años",
        code="F022.SPC.TIN.AN03.UF.Z.D",
        months=36,
        currency="UF",
    ),
    "spc_uf_4y": RateSeries(
        key="spc_uf_4y",
        label="SPC en UF 4 años",
        code="F022.SPC.TIN.AN04.UF.Z.D",
        months=48,
        currency="UF",
    ),
    "spc_uf_5y": RateSeries(
        key="spc_uf_5y",
        label="SPC en UF 5 años",
        code="F022.SPC.TIN.AN05.UF.Z.D",
        months=60,
        currency="UF",
    ),
    "spc_uf_10y": RateSeries(
        key="spc_uf_10y",
        label="SPC en UF 10 años",
        code="F022.SPC.TIN.AN10.UF.Z.D",
        months=120,
        currency="UF",
    ),
    "spc_uf_20y": RateSeries(
        key="spc_uf_20y",
        label="SPC en UF 20 años",
        code="F022.SPC.TIN.AN20.UF.Z.D",
        months=240,
        currency="UF",
    ),
}


RATE_MATURITY_MONTHS = {series.key: series.months for series in RATE_SERIES.values()}

DEFAULT_NS_COLUMNS = [
    "spc_pesos_2y",
    "spc_pesos_3y",
    "spc_pesos_4y",
    "spc_pesos_5y",
    "spc_pesos_10y",
]

DEFAULT_DISCRETE_COLUMNS = DEFAULT_NS_COLUMNS.copy()
