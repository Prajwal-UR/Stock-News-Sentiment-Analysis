from __future__ import annotations

import pandas as pd

from stockq.indicators import maximum_drawdown
from stockq.risk import RiskAssessment


def build_research_summary(
    symbol: str,
    history: pd.DataFrame,
    indicators: pd.DataFrame,
    risk: RiskAssessment,
    fundamentals: dict[str, object] | None = None,
) -> dict[str, list[str]]:
    close = history["Close"].dropna()
    latest = float(close.iloc[-1])
    total_return = float(latest / close.iloc[0] - 1) if len(close) > 1 else float("nan")
    sma50 = indicators["SMA 50"].iloc[-1]
    rsi = indicators["RSI 14"].iloc[-1]
    positives: list[str] = []
    negatives: list[str] = []
    technical_observations: list[str] = []
    if pd.notna(sma50):
        (positives if latest > sma50 else negatives).append(
            f"Close is {'above' if latest > sma50 else 'below'} SMA 50 "
            f"({float(sma50):.2f}); latest close {latest:.2f}."
        )
    if pd.notna(rsi):
        if rsi < 30:
            technical_observations.append(
                f"RSI 14 is {float(rsi):.1f}, below the commonly monitored 30 level; "
                "this is a monitoring signal, not a directional conclusion."
            )
        elif rsi > 70:
            technical_observations.append(
                f"RSI 14 is {float(rsi):.1f}, above the commonly monitored 70 level; "
                "this is a monitoring signal, not a directional conclusion."
            )
        else:
            technical_observations.append(
                f"RSI 14 is {float(rsi):.1f}, inside the conventional 30-70 range."
            )
    if risk.maximum_drawdown < -0.20:
        negatives.append(f"Selected-period maximum drawdown was {risk.maximum_drawdown:.1%}.")
    fundamental_findings = []
    provider_info = fundamentals or {}
    for field, label in (
        ("revenueGrowth", "Revenue growth"),
        ("earningsGrowth", "Earnings growth"),
        ("returnOnEquity", "Return on equity"),
    ):
        value = provider_info.get(field)
        if isinstance(value, (int, float)):
            direction = "positive" if value > 0 else "negative" if value < 0 else "flat"
            fundamental_findings.append(
                f"Provider-reported {label.lower()} is {value:.1%} ({direction}); "
                "period and provider definitions may vary."
            )
    debt_to_equity = provider_info.get("debtToEquity")
    if isinstance(debt_to_equity, (int, float)):
        fundamental_findings.append(
            f"Provider-reported debt-to-equity is {debt_to_equity:.2f}; no universal "
            "strength/weakness threshold is applied because industry context matters."
        )
    if not fundamental_findings:
        fundamental_findings.append(
            "No applicable growth, return-on-equity, or debt-to-equity values are available."
        )
    result = {
        "Executive summary": [
            f"Rule-based research summary for {symbol}; not personalized financial advice.",
            f"Selected-period historical return: {total_return:.1%}." if pd.notna(total_return)
            else "Insufficient observations to calculate selected-period return.",
        ],
        "Recent historical performance": [
            f"Historical closes: {len(close)}; first {close.index[0].date()}, latest {close.index[-1].date()}.",
            f"Annualized historical volatility: {risk.annualized_volatility:.1%}."
            if pd.notna(risk.annualized_volatility) else "Annualized volatility unavailable.",
        ],
        "Trend and technical interpretation": positives + negatives + technical_observations or [
            "Insufficient history for the selected trend indicators."
        ],
        "Fundamental strengths and weaknesses": fundamental_findings,
        "Historical volatility and downside risk": [
            f"Risk category: {risk.classification} using documented volatility thresholds.",
            f"Maximum drawdown: {risk.maximum_drawdown:.1%}; recent 20-session return: "
            f"{risk.recent_20_session_return:.1%}."
            if pd.notna(risk.recent_20_session_return) else "Recent downside return unavailable."
        ],
        "Bullish factors": positives or ["No positive technical condition met the displayed rules."],
        "Bearish factors": negatives or ["No negative technical condition met the displayed rules."],
        "Important uncertainties and missing data": [
            "Yahoo Finance data is unofficial, may be delayed, incomplete, or revised.",
            "Historical indicators and simple models do not establish future performance.",
        ],
        "Scenarios to monitor next": [
            "Observe whether price remains above or below its 50-session moving average.",
            "Reassess volatility, drawdown, and provider data freshness after new sessions.",
        ],
        "Conditions that could invalidate the analysis": [
            "New company disclosures, market regime changes, corporate actions, or corrected source data."
        ],
    }
    return result
