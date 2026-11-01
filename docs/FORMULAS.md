# Formulas and analytical assumptions

All calculations operate on validated daily OHLCV observations. Price history is sorted by session date, duplicate sessions are removed, and rows missing required OHLCV fields or with invalid closing prices are excluded. A rolling value is unavailable until its full stated window exists. Indicators use only current and prior observations.

## Technical indicators

- **SMA(n):** arithmetic mean of the most recent `n` closes; `n = 20, 50, 200`.
- **EMA(n):** recursive exponentially weighted close with `alpha = 2 / (n + 1)`; `n = 12, 26`.
- **RSI(14):** Wilder-smoothed average positive close change divided by Wilder-smoothed average negative close change, transformed as `100 - 100 / (1 + RS)`. A positive-only run is 100; zero-history warm-up remains unavailable.
- **MACD:** EMA(12) minus EMA(26); signal is EMA(9) of MACD; histogram is MACD minus signal.
- **Bollinger(20, 2):** 20-session simple close mean plus/minus two population standard deviations (`ddof=0`).
- **ATR(14):** Wilder-smoothed maximum of high-low, absolute high minus prior close, and absolute low minus prior close.
- **Volume MA(20):** 20-session arithmetic mean of volume.
- **Daily return:** `close[t] / close[t-1] - 1`. **Cumulative return:** compounded daily return relative to the first observation.
- **Annualized historical volatility:** sample standard deviation of daily percentage returns multiplied by `sqrt(252)`. This is a convention, not a prediction.
- **Maximum drawdown:** minimum of `close[t] / max(close[0:t]) - 1`.

Yahoo Finance's `dividendYield` field may arrive as a fractional ratio or as a percentage-point number for Indian listings. The fundamental adapter converts values above `0.1` from percentage points to a fraction for display (for example, `1.9` becomes `1.9%`). Verify provider definitions when comparing or exporting this field.

## Risk classification

The displayed classification uses annualized historical volatility alone: Low below 20%, Moderate from 20% to below 40%, and High at or above 40%. With insufficient history the category is unavailable. It is a configurable descriptive threshold, not an objectively validated or personalized risk score. Maximum drawdown, latest 20-session return, and ATR as a fraction of the latest close are displayed separately. Risk is not inferred from forecast direction.

## Forecast

For horizon `h` in `{1, 5, 20}` trading sessions, the target is the adjusted close `h` observations after the feature timestamp. Features comprise lagged close returns (1, 2, 5, 10, 20 sessions), close distance from 5- and 20-session means, and 20-session return volatility. Rows without complete historical features or target are removed. No future value is used to form a feature.

Rows are assigned chronologically by feature timestamp to 60% training, the next 20% validation, and the final 20% test. The final `h` observations before the validation and test boundaries are purged from the preceding partition so their forward-shifted target labels cannot cross into the next partition. Validation metrics are produced by the model fitted on training data only. The test model is then fitted on training plus validation labels and evaluated on the held-out test partition. A final illustrative estimate is fitted after evaluation using all labeled observations available at the latest historical timestamp. The Random Forest has fixed parameters and a fixed random seed; no data-dependent preprocessing is fitted outside the training rows.

Comparators are persistence (current close) and the trailing five-session close mean. MAE and RMSE are in the stock's price units. Directional accuracy compares the predicted target's sign of change from the feature-time close with the observed target's sign. Metrics are descriptive historical out-of-sample estimates, not trading performance. Target dates are approximate business days, not exchange-calendar dates. No confidence interval is presented.

## Interpretive limits

Rule-based research labels and example RSI/SMA conditions are indicators to monitor, not buy/sell recommendations. Fundamentals are provider-reported, may have different periods or definitions, and ratios should not be compared across industries without additional context. Adjusted historical prices may change after corporate actions or source corrections.
