const state = { data: null, resizeObserver: null };
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const formatNumber = (value, digits = 2) =>
  Number.isFinite(value) ? value.toLocaleString('en-IN', { minimumFractionDigits: digits, maximumFractionDigits: digits }) : 'Not available';
const formatMoney = (value, currency = 'INR') =>
  Number.isFinite(value) ? `${currency} ${formatNumber(value)}` : 'Not available';
const formatPercent = (value, digits = 2) =>
  Number.isFinite(value) ? `${(value * 100).toFixed(digits)}%` : 'Not available';
const readableDate = (value) =>
  value ? new Date(`${value}T00:00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : '—';

async function request(url, options) {
  const response = await fetch(url, options);
  const contentType = response.headers.get('content-type') || '';
  const result = contentType.includes('application/json') ? await response.json() : {};
  if (!response.ok) throw new Error(result.detail || `Request failed (${response.status})`);
  return result;
}

function setLoading(loading) {
  $('#loading').classList.toggle('hidden', !loading);
  $('#analyze-button').disabled = loading;
  $('#analyze-button').textContent = loading ? 'Loading…' : '⌕  Analyze stock';
}

function showError(message) {
  const alert = $('#alert');
  alert.textContent = message;
  alert.classList.remove('hidden');
  alert.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function clearError() {
  $('#alert').classList.add('hidden');
  $('#alert').textContent = '';
}

async function analyze() {
  const symbol = $('#symbol-input').value.trim();
  const exchange = $('#exchange-select').value;
  const period = $('#period-select').value;
  const horizon = $('#horizon-select').value;
  if (!symbol) {
    showError('Enter a company name or ticker symbol to begin.');
    $('#symbol-input').focus();
    return;
  }
  clearError();
  setLoading(true);
  try {
    const params = new URLSearchParams({ symbol, exchange, period, horizon });
    const data = await request(`/api/analysis?${params}`);
    state.data = data;
    render(data);
    history.replaceState(null, '', `/?symbol=${encodeURIComponent(symbol)}&exchange=${exchange}&period=${period}&horizon=${horizon}`);
  } catch (error) {
    showError(error.message || 'Could not load this stock. Please try again.');
  } finally {
    setLoading(false);
  }
}

function render(data) {
  const { stock, overview, risk, history: rows, fundamentals, forecast } = data;
  $('#company-name').textContent = stock.name || stock.symbol;
  $('#company-meta').textContent = `${stock.exchange} · ${stock.symbol}  ·  ${stock.currency}`;
  $('#company-monogram').textContent = (stock.name || stock.symbol).slice(0, 1).toUpperCase();
  const fetched = new Date(data.fetched_at);
  const sourceStatus = data.cache_status === 'cached' ? 'Cached response' : 'Provider response';
  $('#data-freshness').textContent = `Latest session ${readableDate(data.latest_session)} · ${sourceStatus} ${Number.isNaN(fetched.getTime()) ? '' : `· fetched ${fetched.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' })} UTC`}`;

  $('#metric-close').textContent = formatMoney(overview.close, stock.currency);
  const change = overview.change;
  const changePct = overview.change_pct;
  const changeNode = $('#metric-change');
  changeNode.textContent = Number.isFinite(change) && Number.isFinite(changePct)
    ? `${change >= 0 ? '+' : ''}${formatNumber(change)} (${changePct >= 0 ? '+' : ''}${formatPercent(changePct)})`
    : 'Not available';
  changeNode.classList.toggle('positive', Number.isFinite(change) && change >= 0);
  changeNode.classList.toggle('negative', Number.isFinite(change) && change < 0);
  $('#metric-range').textContent = Number.isFinite(overview.period_high) && Number.isFinite(overview.period_low)
    ? `${formatNumber(overview.period_high)} / ${formatNumber(overview.period_low)}` : 'Not available';
  $('#metric-52range').textContent = Number.isFinite(overview.high_52) && Number.isFinite(overview.low_52)
    ? `${formatNumber(overview.high_52)} / ${formatNumber(overview.low_52)}` : 'Not available';

  $('#chart-start').textContent = rows.length ? readableDate(rows[0].date) : '—';
  $('#chart-end').textContent = rows.length ? readableDate(rows.at(-1).date) : '—';
  $('#volume-summary').textContent = Number.isFinite(overview.volume)
    ? `${formatNumber(overview.volume, 0)} shares · 20-session average ${formatNumber(overview.volume_ma, 0)}` : 'Not available';
  renderPriceChart(rows, stock.currency);
  renderVolumeChart(rows);
  renderIndicatorStrip(rows.at(-1) || {});
  renderFundamentals(fundamentals, stock.currency);
  renderRisk(risk, rows);
  renderForecast(data, forecast);
  renderResearch(data.research);
}

function renderIndicatorStrip(latest) {
  const keys = ['RSI 14', 'MACD', 'ATR 14', 'Annualized volatility 20'];
  const html = keys.map((name) => {
    let value = latest[name];
    if (name === 'RSI 14') value = Number.isFinite(value) ? value.toFixed(1) : 'Not available';
    else if (name === 'Annualized volatility 20') value = formatPercent(value);
    else value = formatNumber(value);
    return `<span class="indicator-chip">${escapeHtml(name)} <b>${escapeHtml(value)}</b></span>`;
  }).join('');
  $('#indicator-strip').innerHTML = html;
}

function renderFundamentals(metrics, currency) {
  const percentageMetrics = new Set(['Revenue growth', 'Earnings growth', 'Return on equity', 'Dividend yield']);
  $('#fundamentals-grid').innerHTML = metrics.map((metric) => {
    let value = 'Not available';
    if (Number.isFinite(metric.value)) {
      value = percentageMetrics.has(metric.label)
        ? formatPercent(metric.value)
        : formatNumber(metric.value, metric.label.includes('capitalization') || metric.label === 'Free cash flow' ? 0 : 2);
      if (metric.currency) value = `${metric.currency} ${value}`;
      else if (metric.label === 'Market capitalization' || metric.label === 'Free cash flow' || metric.label === 'Earnings per share') {
        value = `${currency} ${value}`;
      }
    }
    return `<div class="fundamental-item"><span class="fundamental-name">${escapeHtml(metric.label)}</span><span class="fundamental-value" title="${escapeHtml([metric.source, metric.period].filter(Boolean).join(' · '))}">${escapeHtml(value)}</span></div>`;
  }).join('');
}

function renderRisk(risk, rows) {
  const badge = $('#risk-badge');
  badge.textContent = risk.classification;
  badge.className = `risk-badge ${String(risk.classification).toLowerCase().replaceAll(' ', '-')}`;
  const items = [
    ['Annualized volatility', formatPercent(risk.volatility)],
    ['Maximum drawdown', formatPercent(risk.drawdown)],
    ['Recent 20-session return', formatPercent(risk.recent_return)],
    ['ATR / latest close', formatPercent(risk.atr_pct)],
  ];
  $('#risk-stats').innerHTML = items.map(([label, value]) =>
    `<div class="risk-row"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`
  ).join('');
  renderDistribution(rows);
}

function renderForecast(data, forecast) {
  const content = $('#forecast-content');
  const empty = $('#forecast-empty');
  if (!forecast) {
    content.classList.add('hidden');
    empty.classList.remove('hidden');
    empty.textContent = data.forecast_error || 'Forecast is not available for this historical series.';
    return;
  }
  empty.classList.add('hidden');
  content.classList.remove('hidden');
  const currency = data.stock.currency;
  $('#forecast-value').textContent = formatMoney(forecast.estimate, currency);
  $('#forecast-date').textContent = `${forecast.horizon}-session estimate · ${readableDate(forecast.target_date)}`;
  $('#forecast-persistence').textContent = formatMoney(forecast.persistence, currency);
  $('#forecast-average').textContent = formatMoney(forecast.moving_average, currency);
  $('#forecast-splits').textContent =
    `Chronological splits — train ${readableDate(forecast.train[0])}–${readableDate(forecast.train[1])} · validation ${readableDate(forecast.validation[0])}–${readableDate(forecast.validation[1])} (${forecast.validation_observations} rows) · test ${readableDate(forecast.test[0])}–${readableDate(forecast.test[1])} (${forecast.test_observations} rows)`;
  const rows = [];
  for (const [period, metrics] of [['Validation', forecast.validation_metrics], ['Test', forecast.test_metrics]]) {
    for (const [model, values] of Object.entries(metrics)) {
      rows.push(`<tr><td>${escapeHtml(period)}</td><td>${escapeHtml(model)}</td><td>${formatNumber(values.MAE)}</td><td>${formatNumber(values.RMSE)}</td><td>${formatPercent(values['Directional accuracy'])}</td></tr>`);
    }
  }
  $('#forecast-metrics').innerHTML = rows.join('');
}

function renderResearch(research) {
  const priority = [
    'Executive summary', 'Recent historical performance', 'Trend and technical interpretation',
    'Fundamental strengths and weaknesses', 'Historical volatility and downside risk',
    'Bullish factors', 'Bearish factors', 'Important uncertainties and missing data',
    'Scenarios to monitor next', 'Conditions that could invalidate the analysis',
  ];
  $('#research-grid').innerHTML = priority.filter((title) => research[title]).map((title) =>
    `<article class="research-section"><h3>${escapeHtml(title)}</h3><ul>${research[title].map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul></article>`
  ).join('');
}

function renderPriceChart(rows) {
  const canvas = $('#price-chart');
  const context = setupCanvas(canvas);
  if (!context || rows.length < 2) return;
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  const dpr = window.devicePixelRatio || 1;
  context.setTransform(dpr, 0, 0, dpr, 0, 0);
  context.clearRect(0, 0, width, height);

  const left = 54, right = 12, top = 12, bottom = 19;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const visible = rows.slice(-Math.min(rows.length, 700));
  const values = visible.map((row) => row.Close).filter(Number.isFinite);
  if (!values.length) return;
  const extraValues = [];
  for (const checkbox of $$('[data-overlay]:checked')) {
    const key = checkbox.dataset.overlay;
    const fields = key === 'Bollinger Bands'
      ? ['Bollinger upper', 'Bollinger lower'] : [key];
    for (const field of fields) {
      for (const row of visible) if (Number.isFinite(row[field])) extraValues.push(row[field]);
    }
  }
  const minValue = Math.min(...values, ...extraValues);
  const maxValue = Math.max(...values, ...extraValues);
  const padding = (maxValue - minValue || maxValue * .02 || 1) * .12;
  const min = minValue - padding, max = maxValue + padding;
  const x = (index) => left + index * plotWidth / (visible.length - 1);
  const y = (value) => top + (max - value) * plotHeight / (max - min);

  context.font = "9px 'DM Mono', monospace";
  context.textAlign = 'right';
  context.textBaseline = 'middle';
  for (let tick = 0; tick <= 4; tick++) {
    const value = max - (max - min) * tick / 4;
    const position = top + plotHeight * tick / 4;
    context.strokeStyle = '#edf0f3';
    context.lineWidth = 1;
    context.beginPath(); context.moveTo(left, position); context.lineTo(width - right, position); context.stroke();
    context.fillStyle = '#99a4b0';
    context.fillText(formatNumber(value, 0), left - 7, position);
  }

  const chartType = $('#chart-type').value;
  if (chartType === 'line') {
    context.beginPath();
    visible.forEach((row, index) => {
      if (!Number.isFinite(row.Close)) return;
      index ? context.lineTo(x(index), y(row.Close)) : context.moveTo(x(index), y(row.Close));
    });
    context.lineTo(x(visible.length - 1), top + plotHeight);
    context.lineTo(x(0), top + plotHeight);
    context.closePath();
    const gradient = context.createLinearGradient(0, top, 0, top + plotHeight);
    gradient.addColorStop(0, 'rgba(44, 118, 99, .17)');
    gradient.addColorStop(1, 'rgba(44, 118, 99, 0)');
    context.fillStyle = gradient;
    context.fill();
  }

  const styles = { 'SMA 20': '#198c67', 'SMA 50': '#6c7ed0', 'SMA 200': '#c88d45', 'EMA 12': '#32a2ad', 'EMA 26': '#bc729e' };
  for (const checkbox of $$('[data-overlay]:checked')) {
    const key = checkbox.dataset.overlay;
    if (key === 'Bollinger Bands') {
      drawLine(context, visible, x, y, 'Bollinger upper', '#98a6b6', [3, 3]);
      drawLine(context, visible, x, y, 'Bollinger lower', '#98a6b6', [3, 3]);
    } else {
      drawLine(context, visible, x, y, key, styles[key] || '#8895a3');
    }
  }
  if (chartType === 'candlestick') {
    const candleWidth = Math.max(2, Math.min(9, plotWidth / visible.length * .68));
    visible.forEach((row, index) => {
      if (![row.Open, row.High, row.Low, row.Close].every(Number.isFinite)) return;
      const color = row.Close >= row.Open ? '#218b67' : '#d16460';
      context.strokeStyle = color;
      context.fillStyle = color;
      context.lineWidth = 1;
      context.beginPath();
      context.moveTo(x(index), y(row.High));
      context.lineTo(x(index), y(row.Low));
      context.stroke();
      const bodyTop = Math.min(y(row.Open), y(row.Close));
      const bodyHeight = Math.max(1, Math.abs(y(row.Open) - y(row.Close)));
      context.fillRect(x(index) - candleWidth / 2, bodyTop, candleWidth, bodyHeight);
    });
  } else {
    context.beginPath();
    visible.forEach((row, index) => {
      if (!Number.isFinite(row.Close)) return;
      index ? context.lineTo(x(index), y(row.Close)) : context.moveTo(x(index), y(row.Close));
    });
    context.strokeStyle = '#263e55';
    context.lineWidth = 2;
    context.lineJoin = 'round';
    context.stroke();
  }

  canvas._chartInfo = { rows: visible, left, right, top, bottom, plotWidth, plotHeight, min, max, x, y };
  canvas.onpointermove = showChartTooltip;
  canvas.onpointerleave = () => $('#chart-tooltip').classList.add('hidden');
}

function drawLine(context, rows, x, y, field, color, dash = []) {
  context.beginPath();
  let started = false;
  rows.forEach((row, index) => {
    if (!Number.isFinite(row[field])) { started = false; return; }
    if (started) context.lineTo(x(index), y(row[field]));
    else { context.moveTo(x(index), y(row[field])); started = true; }
  });
  context.strokeStyle = color;
  context.lineWidth = 1.25;
  context.setLineDash(dash);
  context.stroke();
  context.setLineDash([]);
}

function showChartTooltip(event) {
  const canvas = event.currentTarget;
  const info = canvas._chartInfo;
  if (!info) return;
  const bounds = canvas.getBoundingClientRect();
  const point = event.clientX - bounds.left;
  const index = Math.max(0, Math.min(info.rows.length - 1, Math.round((point - info.left) / info.plotWidth * (info.rows.length - 1))));
  const row = info.rows[index];
  const tooltip = $('#chart-tooltip');
  tooltip.innerHTML = `${escapeHtml(readableDate(row.date))}<br>Close&nbsp; ${escapeHtml(formatNumber(row.Close))}<br>High&nbsp;&nbsp; ${escapeHtml(formatNumber(row.High))}<br>Low&nbsp;&nbsp;&nbsp; ${escapeHtml(formatNumber(row.Low))}<br>Volume ${escapeHtml(formatNumber(row.Volume, 0))}`;
  tooltip.classList.remove('hidden');
  tooltip.style.left = `${Math.min(bounds.width - 155, Math.max(6, info.x(index) + 8))}px`;
  tooltip.style.top = `${Math.max(4, info.y(row.Close) - 35)}px`;
}

function renderVolumeChart(rows) {
  const canvas = $('#volume-chart');
  const context = setupCanvas(canvas);
  if (!context) return;
  const width = canvas.clientWidth, height = canvas.clientHeight, dpr = window.devicePixelRatio || 1;
  context.setTransform(dpr, 0, 0, dpr, 0, 0);
  context.clearRect(0, 0, width, height);
  const visible = rows.slice(-Math.min(rows.length, 700));
  const max = Math.max(...visible.map((row) => row.Volume || 0), 1);
  const gap = Math.max(1, width / visible.length * .2);
  visible.forEach((row, index) => {
    const barWidth = Math.max(1, width / visible.length - gap);
    const barHeight = Math.max(1, ((row.Volume || 0) / max) * (height - 3));
    const prior = index ? visible[index - 1].Close : row.Open;
    context.fillStyle = row.Close >= prior ? '#b4d9c9' : '#ebc3c1';
    context.fillRect(index * width / visible.length, height - barHeight, barWidth, barHeight);
  });
}

function renderDistribution(rows) {
  const canvas = $('#returns-chart');
  const context = setupCanvas(canvas);
  if (!context) return;
  const width = canvas.clientWidth, height = canvas.clientHeight, dpr = window.devicePixelRatio || 1;
  context.setTransform(dpr, 0, 0, dpr, 0, 0);
  context.clearRect(0, 0, width, height);
  const returns = rows.map((row) => row['Daily return']).filter(Number.isFinite);
  if (!returns.length) return;
  const min = Math.min(...returns), max = Math.max(...returns);
  const bins = new Array(18).fill(0);
  const span = max - min || 1;
  returns.forEach((value) => bins[Math.min(bins.length - 1, Math.floor((value - min) / span * bins.length))]++);
  const peak = Math.max(...bins, 1), slot = width / bins.length;
  bins.forEach((count, index) => {
    const barHeight = count / peak * (height - 8);
    const positive = min + span * (index + .5) / bins.length >= 0;
    context.fillStyle = positive ? '#88c7a8' : '#e5aaa7';
    context.fillRect(index * slot + 2, height - barHeight, Math.max(1, slot - 4), barHeight);
  });
  context.strokeStyle = '#dfe5e8';
  context.beginPath(); context.moveTo(width / 2, 0); context.lineTo(width / 2, height); context.stroke();
}

function setupCanvas(canvas) {
  if (!canvas || !canvas.clientWidth || !canvas.clientHeight) return null;
  const dpr = window.devicePixelRatio || 1;
  const width = Math.round(canvas.clientWidth * dpr);
  const height = Math.round(canvas.clientHeight * dpr);
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width; canvas.height = height;
  }
  return canvas.getContext('2d');
}

async function compareStocks(event) {
  event.preventDefault();
  const input = $('#compare-symbols').value.split(',').map((value) => value.trim()).filter(Boolean);
  const symbols = [...new Set([$('#symbol-input').value.trim(), ...input])].filter(Boolean);
  if (symbols.length < 2 || symbols.length > 3) {
    showError('Enter one or two different tickers to compare with the selected stock (2–3 total).');
    return;
  }
  clearError();
  $('#compare-result').innerHTML = '<div class="loading"><span class="spinner"></span> Comparing common trading sessions…</div>';
  try {
    const result = await request('/api/compare', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbols, exchange: $('#exchange-select').value, period: $('#period-select').value }),
    });
    renderComparison(result);
  } catch (error) {
    $('#compare-result').textContent = '';
    showError(error.message);
  }
}

function renderComparison(result) {
  const metrics = result.metrics;
  const range = Math.max(0.05, ...metrics.map((row) => Math.abs(row['Common-period return'] || 0)));
  const bars = metrics.map((row) => {
    const value = row['Common-period return'];
    const width = Number.isFinite(value) ? Math.max(2, Math.abs(value) / range * 100) : 0;
    return `<div class="compare-bar-row"><span>${escapeHtml(row.Symbol)}</span><div class="compare-track"><div class="compare-bar" style="width:${width}%;background:${value < 0 ? '#d47b75' : '#59ad87'}"></div></div><strong>${escapeHtml(formatPercent(value))}</strong></div>`;
  }).join('');
  const rows = metrics.map((row) =>
    `<tr><td>${escapeHtml(row.Symbol)}</td><td>${escapeHtml(formatPercent(row['Common-period return']))}</td><td>${escapeHtml(formatPercent(row['Annualized volatility']))}</td><td>${escapeHtml(formatPercent(row['Maximum drawdown']))}</td><td>${escapeHtml(formatPercent(row['Close vs SMA 50']))}</td><td>${Number.isFinite(row['RSI 14']) ? row['RSI 14'].toFixed(1) : 'Not available'}</td></tr>`
  ).join('');
  const symbols = Object.keys(result.fundamentals);
  const referenceMetrics = Object.values(result.fundamentals)[0] || [];
  const fundamentals = referenceMetrics.map((reference, index) => {
    const cells = symbols.map((symbol) => {
      const metric = result.fundamentals[symbol][index];
      if (!Number.isFinite(metric?.value)) return '<td>Not available</td>';
      const isPercent = ['Revenue growth', 'Earnings growth', 'Return on equity', 'Dividend yield'].includes(reference.label);
      const value = isPercent ? formatPercent(metric.value) : formatNumber(metric.value, 2);
      return `<td>${escapeHtml(metric.currency ? `${metric.currency} ${value}` : value)}</td>`;
    }).join('');
    return `<tr><td>${escapeHtml(reference.label)}</td>${cells}</tr>`;
  }).join('');
  $('#compare-result').innerHTML = `<div class="compare-bars">${bars}</div><canvas id="compare-chart" class="compare-chart" aria-label="Normalized common-period stock performance chart" role="img"></canvas><div class="table-scroll"><table><thead><tr><th>Symbol</th><th>Common-period return</th><th>Annualized volatility</th><th>Max drawdown</th><th>Close vs SMA 50</th><th>RSI 14</th></tr></thead><tbody>${rows}</tbody></table></div><p class="card-footnote">All stocks use the same ${escapeHtml(readableDate(result.dates[0]))}–${escapeHtml(readableDate(result.dates.at(-1)))} common date window. Risk-adjusted returns omitted; no risk-free rate configured.</p><div class="table-scroll"><table><thead><tr><th>Fundamental</th>${symbols.map((symbol) => `<th>${escapeHtml(symbol)}</th>`).join('')}</tr></thead><tbody>${fundamentals}</tbody></table></div>`;
  drawComparisonChart(result);
}

function drawComparisonChart(result) {
  const canvas = $('#compare-chart');
  canvas.style.width = '100%';
  canvas.style.height = '190px';
  const context = setupCanvas(canvas);
  if (!context) return;
  const width = canvas.clientWidth, height = canvas.clientHeight, dpr = window.devicePixelRatio || 1;
  context.setTransform(dpr, 0, 0, dpr, 0, 0);
  context.clearRect(0, 0, width, height);
  const left = 42, right = 70, top = 12, bottom = 20;
  const plotWidth = width - left - right, plotHeight = height - top - bottom;
  const allValues = Object.values(result.normalized).flat().filter(Number.isFinite);
  const minimum = Math.min(...allValues, 100), maximum = Math.max(...allValues, 100);
  const padding = (maximum - minimum || 1) * .1;
  const min = minimum - padding, max = maximum + padding;
  const x = (index) => left + index * plotWidth / Math.max(1, result.dates.length - 1);
  const y = (value) => top + (max - value) * plotHeight / (max - min);
  context.font = "9px 'DM Mono', monospace";
  context.textAlign = 'right';
  context.textBaseline = 'middle';
  for (let tick = 0; tick <= 3; tick++) {
    const value = max - (max - min) * tick / 3;
    const position = top + plotHeight * tick / 3;
    context.strokeStyle = '#e8edef';
    context.beginPath(); context.moveTo(left, position); context.lineTo(width - right, position); context.stroke();
    context.fillStyle = '#99a4b0';
    context.fillText(value.toFixed(0), left - 6, position);
  }
  const colors = ['#218b67', '#687fce', '#d0874e'];
  Object.entries(result.normalized).forEach(([symbol, values], seriesIndex) => {
    context.beginPath();
    values.forEach((value, index) => {
      if (!Number.isFinite(value)) return;
      index ? context.lineTo(x(index), y(value)) : context.moveTo(x(index), y(value));
    });
    const color = colors[seriesIndex % colors.length];
    context.strokeStyle = color;
    context.lineWidth = 1.8;
    context.stroke();
    context.fillStyle = color;
    context.textAlign = 'left';
    context.fillText(symbol, width - right + 8, y(values.at(-1)) + (seriesIndex - 1) * 11);
  });
}

async function loadWatchlist() {
  try {
    const items = await request('/api/watchlist');
    const host = $('#watchlist-content');
    if (!items.length) {
      host.innerHTML = '<div class="watchlist-empty">No saved stocks yet. Save this analysis to keep its period and forecast horizon.</div>';
      return;
    }
    host.innerHTML = items.map((item) => `<div class="watchlist-row"><strong>${escapeHtml(item.symbol)}</strong><span>Period · ${escapeHtml(item.period)}</span><span>Horizon · ${escapeHtml(item.horizon)} sessions</span><button type="button" data-remove-symbol="${escapeHtml(item.symbol)}" aria-label="Remove ${escapeHtml(item.symbol)}">Remove</button></div>`).join('');
    $$('[data-remove-symbol]').forEach((button) => button.addEventListener('click', () => removeWatchlist(button.dataset.removeSymbol)));
  } catch (error) {
    $('#watchlist-content').textContent = `Could not load watchlist: ${error.message}`;
  }
}

async function saveWatchlist() {
  try {
    const items = await request('/api/watchlist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        symbol: $('#symbol-input').value.trim(),
        period: $('#period-select').value,
        horizon: Number($('#horizon-select').value),
      }),
    });
    renderWatchlistItems(items);
  } catch (error) {
    showError(error.message);
  }
}

function renderWatchlistItems(items) {
  const host = $('#watchlist-content');
  if (!items.length) {
    host.innerHTML = '<div class="watchlist-empty">No saved stocks yet. Save this analysis to keep its period and forecast horizon.</div>';
    return;
  }
  host.innerHTML = items.map((item) => `<div class="watchlist-row"><strong>${escapeHtml(item.symbol)}</strong><span>Period · ${escapeHtml(item.period)}</span><span>Horizon · ${escapeHtml(item.horizon)} sessions</span><button type="button" data-remove-symbol="${escapeHtml(item.symbol)}" aria-label="Remove ${escapeHtml(item.symbol)}">Remove</button></div>`).join('');
  $$('[data-remove-symbol]').forEach((button) => button.addEventListener('click', () => removeWatchlist(button.dataset.removeSymbol)));
}

async function removeWatchlist(symbol) {
  try {
    const items = await request(`/api/watchlist/${encodeURIComponent(symbol)}`, { method: 'DELETE' });
    renderWatchlistItems(items);
  } catch (error) {
    showError(error.message);
  }
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[character]);
}

function loadExamples() {
  request('/api/stocks').then((stocks) => {
    $('#stock-suggestions').innerHTML = stocks.map((stock) =>
      `<option value="${escapeHtml(stock.symbol)}">${escapeHtml(stock.name)} · ${escapeHtml(stock.exchange)}</option>`
    ).join('');
  }).catch(() => {});
}

function setTheme(dark) {
  document.body.classList.toggle('dark', dark);
  localStorage.setItem('stockq-theme', dark ? 'dark' : 'light');
}

function initialize() {
  const params = new URLSearchParams(location.search);
  if (params.has('symbol')) $('#symbol-input').value = params.get('symbol');
  if (params.has('exchange') && ['NSE', 'BSE'].includes(params.get('exchange'))) $('#exchange-select').value = params.get('exchange');
  if (params.has('period') && ['1mo', '3mo', '6mo', '1y', '5y', 'max'].includes(params.get('period'))) $('#period-select').value = params.get('period');
  if (params.has('horizon') && ['1', '5', '20'].includes(params.get('horizon'))) $('#horizon-select').value = params.get('horizon');

  setTheme(localStorage.getItem('stockq-theme') === 'dark');
  $('#analyze-button').addEventListener('click', analyze);
  $('#symbol-input').addEventListener('keydown', (event) => { if (event.key === 'Enter') analyze(); });
  $('#period-select').addEventListener('change', analyze);
  $('#horizon-select').addEventListener('change', () => { if (state.data) analyze(); });
  $('#exchange-select').addEventListener('change', () => { if (state.data) analyze(); });
  $$('[data-overlay]').forEach((checkbox) => checkbox.addEventListener('change', () => {
    if (state.data) renderPriceChart(state.data.history, state.data.stock.currency);
  }));
  $('#chart-type').addEventListener('change', () => {
    if (state.data) renderPriceChart(state.data.history, state.data.stock.currency);
  });
  $('#compare-form').addEventListener('submit', compareStocks);
  $('#save-watchlist').addEventListener('click', saveWatchlist);
  $('#theme-toggle').addEventListener('click', () => setTheme(!document.body.classList.contains('dark')));
  window.addEventListener('resize', () => {
    if (state.data) {
      renderPriceChart(state.data.history, state.data.stock.currency);
      renderVolumeChart(state.data.history);
      renderDistribution(state.data.history);
    }
  });
  loadExamples();
  loadWatchlist();
  analyze();
}

document.addEventListener('DOMContentLoaded', initialize);
