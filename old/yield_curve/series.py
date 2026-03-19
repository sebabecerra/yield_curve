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
    "TPM": RateSeries(
        key="TPM",
        label="TPM",
        code="F022.TPM.TIN.D001.NO.Z.D",
        months=1,
        currency="CLP",
        family="money_market",
    ),
    "SPC_03Y": RateSeries(
        key="SPC_03Y",
        label="SPC 90 días",
        code="F022.SPC.TPR.D090.NO.Z.D",
        months=3,
        currency="CLP",
        family="money_market",
    ),
    "SPC_06Y": RateSeries(
        key="SPC_06Y",
        label="SPC 180 días",
        code="F022.SPC.TPR.D180.NO.Z.D",
        months=6,
        currency="CLP",
        family="money_market",
    ),
    "SPC_1Y": RateSeries(
        key="SPC_1Y",
        label="SPC 360 días",
        code="F022.SPC.TPR.D360.NO.Z.D",
        months=12,
        currency="CLP",
        family="money_market",
    ),
    "SPC_2Y": RateSeries(
        key="SPC_2Y",
        label="SPC en pesos 2 años",
        code="F022.SPC.TIN.AN02.NO.Z.D",
        months=24,
        currency="CLP",
    ),
    "SPC_3Y": RateSeries(
        key="SPC_3Y",
        label="SPC en pesos 3 años",
        code="F022.SPC.TIN.AN03.NO.Z.D",
        months=36,
        currency="CLP",
    ),
    "SPC_4Y": RateSeries(
        key="SPC_4Y",
        label="SPC en pesos 4 años",
        code="F022.SPC.TIN.AN04.NO.Z.D",
        months=48,
        currency="CLP",
    ),
    "SPC_5Y": RateSeries(
        key="SPC_5Y",
        label="SPC en pesos 5 años",
        code="F022.SPC.TIN.AN05.NO.Z.D",
        months=60,
        currency="CLP",
    ),
    "SPC_10Y": RateSeries(
        key="SPC_10Y",
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
    "TPM",
    "SPC_03Y",
    "SPC_06Y",
    "SPC_1Y",
    "SPC_2Y",
    "SPC_3Y",
    "SPC_4Y",
    "SPC_5Y",
    "SPC_10Y",
]

DEFAULT_DISCRETE_COLUMNS = DEFAULT_NS_COLUMNS.copy()

LEGACY_RATE_ALIASES = {
    "tpm": "TPM",
    "scp90": "SPC_03Y",
    "scp180": "SPC_06Y",
    "scp360": "SPC_1Y",
    "SCP90": "SPC_03Y",
    "SCP180": "SPC_06Y",
    "SCP360": "SPC_1Y",
    "spc_pesos_2y": "SPC_2Y",
    "spc_pesos_3y": "SPC_3Y",
    "spc_pesos_4y": "SPC_4Y",
    "spc_pesos_5y": "SPC_5Y",
    "spc_pesos_10y": "SPC_10Y",
}
