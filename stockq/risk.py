from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from stockq.indicators import annualized_volatility, maximum_drawdown


@dataclass(frozen=True)
class RiskAssessment:
    annualized_volatility: float
    maximum_drawdown: float
    recent_20_session_return: float
    atr_percent: float
    classification: str
    thresholds: str = "Low <20%, Moderate 20%-<40%, High >=40% annualized volatility"


def classify_volatility(volatility: float) -> str:
    if pd.isna(volatility):
        return "Insufficient history"
    return "Low" if volatility < 0.20 else "Moderate" if volatility < 0.40 else "High"


def assess_risk(history: pd.DataFrame, indicators: pd.DataFrame) -> RiskAssessment:
    close = history["Close"].dropna()
    vol = annualized_volatility(close)
    recent_return = float(close.iloc[-1] / close.iloc[-21] - 1) if len(close) > 21 else float("nan")
    atr = indicators["ATR 14"].iloc[-1]
    atr_percent = float(atr / close.iloc[-1]) if pd.notna(atr) and close.iloc[-1] else float("nan")
    return RiskAssessment(
        annualized_volatility=vol,
        maximum_drawdown=maximum_drawdown(close),
        recent_20_session_return=recent_return,
        atr_percent=atr_percent,
        classification=classify_volatility(vol),
    )
