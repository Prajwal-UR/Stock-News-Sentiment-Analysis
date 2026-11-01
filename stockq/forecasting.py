from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error


@dataclass(frozen=True)
class ForecastResult:
    horizon: int
    target_date: pd.Timestamp
    estimate: float
    baseline_persistence: float
    baseline_moving_average: float
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    validation_start: pd.Timestamp
    validation_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    validation_metrics: dict[str, dict[str, float]]
    test_metrics: dict[str, dict[str, float]]
    validation_observations: int
    test_observations: int
    model_name: str = "Random Forest (illustrative estimate)"


def _features(close: pd.Series) -> pd.DataFrame:
    features = pd.DataFrame(index=close.index)
    returns = close.pct_change(fill_method=None)
    for lag in (1, 2, 5, 10, 20):
        features[f"return_{lag}"] = close / close.shift(lag) - 1
    for window in (5, 20):
        features[f"distance_sma_{window}"] = close / close.rolling(window).mean() - 1
    features["volatility_20"] = returns.rolling(20).std(ddof=1)
    return features


def _metrics(actual: np.ndarray, predicted: np.ndarray, previous: np.ndarray) -> dict[str, float]:
    direction = np.sign(predicted - previous) == np.sign(actual - previous)
    return {
        "MAE": float(mean_absolute_error(actual, predicted)),
        "RMSE": float(np.sqrt(mean_squared_error(actual, predicted))),
        "Directional accuracy": float(np.mean(direction)),
    }


def forecast_close(close: pd.Series, horizon: int = 5) -> ForecastResult:
    if horizon not in (1, 5, 20):
        raise ValueError("Forecast horizon must be 1, 5, or 20 trading sessions.")
    prices = pd.to_numeric(close, errors="coerce").dropna().astype(float)
    if len(prices) < max(80, horizon + 45):
        raise ValueError("At least 80 valid daily observations are required for forecasting.")

    features = _features(prices)
    dataset = features.copy()
    dataset["target"] = prices.shift(-horizon)
    dataset["previous_close"] = prices
    dataset = dataset.dropna()
    if len(dataset) < 60:
        raise ValueError("Insufficient complete observations after building forecast features.")

    count = len(dataset)
    train_end_position = int(count * 0.60)
    validation_end_position = int(count * 0.80)
    positions = np.arange(count)
    train_mask = positions < train_end_position - horizon
    validation_mask = (
        (positions >= train_end_position)
        & (positions < validation_end_position - horizon)
    )
    test_mask = positions >= validation_end_position
    if train_mask.sum() < 30 or validation_mask.sum() == 0 or test_mask.sum() == 0:
        raise ValueError("Insufficient observations for chronological train/validation/test splits.")
    x = dataset.drop(columns=["target", "previous_close"])
    y = dataset["target"]
    previous = dataset["previous_close"]
    model = RandomForestRegressor(
        n_estimators=100, max_depth=4, min_samples_leaf=3, random_state=42, n_jobs=1
    )
    model.fit(x.loc[train_mask], y.loc[train_mask])
    validation_x = x.loc[validation_mask]
    validation_actual = y.loc[validation_mask].to_numpy()
    validation_previous = previous.loc[validation_mask].to_numpy()
    validation_prediction = model.predict(validation_x)
    validation_indexes = dataset.index[validation_mask]
    validation_metrics = {
        "Random Forest": _metrics(
            validation_actual, validation_prediction, validation_previous
        ),
        "Persistence": _metrics(
            validation_actual, validation_previous, validation_previous
        ),
        "5-session moving average": _metrics(
            validation_actual,
            prices.rolling(5, min_periods=5).mean().reindex(validation_indexes).to_numpy(),
            validation_previous,
        ),
    }

    test_x = x.loc[test_mask]
    test_actual = y.loc[test_mask].to_numpy()
    test_previous = previous.loc[test_mask].to_numpy()
    validation_train_mask = train_mask | validation_mask
    model.fit(x.loc[validation_train_mask], y.loc[validation_train_mask])
    test_prediction = model.predict(test_x)

    test_indexes = dataset.index[test_mask]
    metrics = {
        "Random Forest": _metrics(test_actual, test_prediction, test_previous),
        "Persistence": _metrics(test_actual, test_previous, test_previous),
        "5-session moving average": _metrics(
            test_actual,
            prices.rolling(5, min_periods=5).mean().reindex(test_indexes).to_numpy(),
            test_previous,
        ),
    }

    current_features = _features(prices).iloc[[-1]]
    if current_features.isna().any(axis=None):
        raise ValueError("Latest observations are insufficient to create forecast features.")
    final_model = RandomForestRegressor(
        n_estimators=100, max_depth=4, min_samples_leaf=3, random_state=42, n_jobs=1
    )
    final_model.fit(x, y)
    estimate = float(final_model.predict(current_features)[0])
    return ForecastResult(
        horizon=horizon,
        target_date=pd.Timestamp(prices.index[-1]) + pd.offsets.BDay(horizon),
        estimate=estimate,
        baseline_persistence=float(prices.iloc[-1]),
        baseline_moving_average=float(prices.tail(5).mean()),
        train_start=pd.Timestamp(dataset.index[0]),
        train_end=pd.Timestamp(dataset.index[train_mask][-1]),
        validation_start=pd.Timestamp(dataset.index[validation_mask][0]),
        validation_end=pd.Timestamp(dataset.index[validation_mask][-1]),
        test_start=pd.Timestamp(dataset.index[test_mask][0]),
        test_end=pd.Timestamp(dataset.index[test_mask][-1]),
        validation_metrics=validation_metrics,
        test_metrics=metrics,
        validation_observations=len(validation_actual),
        test_observations=len(test_actual),
    )
