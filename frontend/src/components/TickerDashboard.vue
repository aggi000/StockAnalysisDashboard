<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import PriceChart from './charts/PriceChart.vue'

const apiBase = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

const ticker = ref('AAPL')
const searchTerm = ref('AAPL')
const loading = ref(false)
const error = ref('')
const quote = ref(null)
const candles = ref(null)
const period = ref('1y')

const periods = ['1mo','3mo','6mo','1y','2y','5y','max']
const intervalsByPeriod = {
  '1mo': '1d',
  '3mo': '1d',
  '6mo': '1d',
  '1y': '1d',
  '2y': '1wk',
  '5y': '1wk',
  'max': '1mo'
}

async function fetchAll() {
  if (loading.value) return
  loading.value = true
  error.value = ''
  try {
    const symbol = (ticker.value || 'AAPL').trim().toUpperCase() || 'AAPL'
    ticker.value = symbol
    const [q, h] = await Promise.all([
      axios.get(`${apiBase}/api/quote/${symbol}`),
      axios.get(`${apiBase}/api/history/${symbol}`, {
        params: {
          period: period.value,
          interval: intervalsByPeriod[period.value],
          indicators: ''
        }
      })
    ])
    quote.value = q.data
    candles.value = h.data
    searchTerm.value = symbol
  } catch (e) {
    console.error(e)
    quote.value = null
    candles.value = null
    error.value = 'Failed to fetch data. Check API status and ticker symbol, then try again.'
  } finally {
    loading.value = false
  }
}

onMounted(fetchAll)

function formatNumber(value, options = {}) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  try {
    return Number(value).toLocaleString(undefined, options)
  } catch (err) {
    return String(value)
  }
}

const quoteMetrics = computed(() => {
  if (!quote.value) return []
  return [
    { label: 'Previous Close', value: formatNumber(quote.value.previousClose, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) },
    { label: 'Open', value: formatNumber(quote.value.open, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) },
    { label: 'Day High', value: formatNumber(quote.value.dayHigh, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) },
    { label: 'Day Low', value: formatNumber(quote.value.dayLow, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) },
    { label: '52 Week High', value: formatNumber(quote.value.fiftyTwoWeekHigh, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) },
    { label: '52 Week Low', value: formatNumber(quote.value.fiftyTwoWeekLow, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) },
    { label: 'Trailing P/E', value: formatNumber(quote.value.trailingPE, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) },
    { label: 'Forward P/E', value: formatNumber(quote.value.forwardPE, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) },
    { label: 'EPS (TTM)', value: formatNumber(quote.value.epsTrailing12M, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) },
    { label: 'Beta', value: formatNumber(quote.value.beta, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) },
    { label: 'Dividend Yield', value: quote.value.dividendYield != null ? `${(quote.value.dividendYield * 100).toFixed(2)}%` : '—' },
    { label: 'Market Cap', value: formatNumber(quote.value.marketCap, { maximumFractionDigits: 2, notation: 'compact' }) }
  ]
})

function setPeriod(value) {
  if (period.value === value) return
  period.value = value
  fetchAll()
}

function submitSearch() {
  const symbol = (searchTerm.value || '').trim().toUpperCase()
  if (!symbol) return
  if (symbol === ticker.value) {
    fetchAll()
    return
  }
  ticker.value = symbol
  fetchAll()
}

const displayTicker = computed(() => quote.value?.ticker ?? ticker.value ?? '—')
const displayPrice = computed(() => formatNumber(quote.value?.price, { minimumFractionDigits: 2, maximumFractionDigits: 2 }))
const displayCurrency = computed(() => quote.value?.currency ?? '')

const averageCloseValue = computed(() => {
  const prices = candles.value?.candles?.map(c => Number(c.close)).filter(v => Number.isFinite(v))
  if (!prices || !prices.length) return null
  return prices.reduce((sum, value) => sum + value, 0) / prices.length
})

const averageCloseDisplay = computed(() => {
  if (averageCloseValue.value == null) return null
  return formatNumber(averageCloseValue.value, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
})
</script>

<template>
  <section class="dashboard">
    <div class="search-container">
      <div class="search-inner">
        <form @submit.prevent="submitSearch" class="search-form">
          <input
            v-model="searchTerm"
            type="text"
            placeholder="Search..."
            class="search-input"
          />
          <button
            type="submit"
            aria-label="Search"
            title="Search"
            class="search-button"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              class="search-icon"
            >
              <circle cx="11" cy="11" r="7" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          </button>
        </form>
      </div>
    </div>
    
    <div class="overview-card">
      <div class="overview-grid">
        <div class="overview-details">
          <span class="muted-label">Symbol</span>
          <div class="symbol-row">
            <span class="symbol-text">{{ displayTicker }}</span>
            <span v-if="displayCurrency" class="currency-tag">{{ displayCurrency }}</span>
          </div>
          <p class="muted-text">Selected range: {{ period }}</p>
          <p v-if="error" class="error-text">{{ error }}</p>
        </div>
        <div class="price-details">
          <span class="muted-label">Last Price</span>
          <div class="price-row">
            <span class="price-value">{{ displayPrice }}</span>
            <span v-if="displayCurrency" class="currency-tag">{{ displayCurrency }}</span>
            <span v-if="loading" class="loading-indicator">
              <span class="loading-dot"></span>
              Updating
            </span>
          </div>
        </div>
      </div>
      <div class="divider"></div>
      <div class="range-section">
        <div class="range-group">
          <span class="muted-label">Range</span>
          <div class="range-buttons">
            <button
              v-for="p in periods"
              :key="p"
              type="button"
              @click="setPeriod(p)"
              class="range-button"
              :class="p === period ? 'range-button--active' : 'range-button--inactive'"
            >{{ p }}</button>
          </div>
        </div>
        <div class="refresh-group">
          <button
            @click="fetchAll"
            :disabled="loading"
            type="button"
            class="refresh-button"
          >Refresh</button>
          <span v-if="loading" class="muted-text">Loading latest data…</span>
        </div>
      </div>
    </div>
    <div class="chart-card">
      <header class="chart-header">
        <h2 class="card-title">Price Performance</h2>
        <span v-if="averageCloseDisplay" class="average-chip">Avg {{ averageCloseDisplay }}</span>
      </header>
      <div class="chart-content">
        <div v-if="candles?.candles?.length">
          <PriceChart :history="candles" :indicators="candles?.indicators || {}" :average="averageCloseValue" />
        </div>
        <div v-else-if="loading" class="muted-text">Loading chart…</div>
        <div v-else-if="candles === null" class="muted-text">Choose a ticker and refresh to load price history.</div>
        <div v-else class="muted-text">Historical data unavailable for the selected range.</div>
      </div>
    </div>

    <div v-if="quoteMetrics.length" class="stats-card">
      <header class="card-header">
        <h2 class="card-title">Key Stats</h2>
      </header>
      <div class="stats-grid">
        <div
          v-for="(metric, index) in quoteMetrics"
          :key="metric.label"
          :class="['metric-row', { 'metric-row--striped': Math.floor(index / 2) % 2 }]"
        >
          <span class="metric-label">{{ metric.label }}</span>
          <span class="metric-value">{{ metric.value }}</span>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  width: 100%;
}

.dashboard > * + * {
  margin-top: 2rem;
}

.search-container {
  width: 100%;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: var(--background, #f8fafc);
  padding: 1rem;
}

.search-inner {
  width: 100%;
  max-width: 28rem;
}

.search-form {
  position: relative;
  width: 100%;
}

.search-input {
  width: 100%;
  height: 3rem;
  padding: 0 1.5rem;
  padding-right: 3rem;
  border-radius: 9999px;
  border: 2px solid #e2e8f0;
  background-color: #ffffff;
  color: #1e293b;
  font-size: 1rem;
  line-height: 1.25;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease;
}

.search-input::placeholder {
  color: #94a3b8;
}

.search-input:focus,
.search-input:focus-visible {
  outline: none;
  border-color: #94a3b8;
  box-shadow: 0 0 0 2px rgba(148, 163, 184, 0.35);
  background-color: #ffffff;
}

.search-button {
  position: absolute;
  top: 50%;
  right: 0.5rem;
  transform: translateY(-50%);
  height: 2rem;
  width: 2rem;
  border-radius: 9999px;
  background-color: #0f172a;
  color: #ffffff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  padding: 0;
  box-shadow: 0 2px 4px rgba(15, 23, 42, 0.25);
  cursor: pointer;
  transition: opacity 0.2s ease;
}

.search-button:hover {
  opacity: 0.95;
}

.search-button:active {
  opacity: 0.9;
}

.search-button:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px rgba(148, 163, 184, 0.45);
}

.search-icon {
  width: 1rem;
  height: 1rem;
}

.overview-card {
  border-radius: 1.5rem;
  border: 1px solid rgba(226, 232, 240, 0.8);
  background-color: #ffffff;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08);
  padding: 1.75rem;
  display: flex;
  flex-direction: column;
}

.overview-card > * + * {
  margin-top: 1.75rem;
}

.overview-grid {
  display: grid;
  gap: 1.5rem;
}

.overview-details,
.price-details {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.price-details {
  text-align: left;
  align-items: flex-start;
}

.muted-label {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
}

.muted-text {
  font-size: 0.875rem;
  color: #64748b;
  margin: 0;
}

.error-text {
  font-size: 0.75rem;
  color: #ef4444;
  margin: 0;
}

.symbol-row,
.price-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.symbol-text,
.price-value {
  margin: 0;
  font-size: 1.875rem;
  font-weight: 600;
  letter-spacing: -0.015em;
  color: #0f172a;
}

.currency-tag {
  font-size: 0.875rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #94a3b8;
}

.loading-indicator {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.75rem;
  color: #64748b;
}

.loading-dot {
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 9999px;
  background-color: #94a3b8;
  animation: pulse 1.2s ease-in-out infinite;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 0.3;
    transform: scale(0.9);
  }
  50% {
    opacity: 1;
    transform: scale(1);
  }
}

.divider {
  width: 100%;
  height: 1px;
  background-color: #e2e8f0;
}

.range-section {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.range-group {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
}

.range-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.range-button {
  padding: 0.5rem 0.75rem;
  border-radius: 0.75rem;
  font-size: 0.875rem;
  border: 1px solid transparent;
  background-color: #ffffff;
  color: #475569;
  transition: all 0.2s ease;
  cursor: pointer;
}

.range-button:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px rgba(148, 163, 184, 0.35);
}

.range-button--inactive {
  border-color: #e2e8f0;
  color: #475569;
}

.range-button--inactive:hover {
  border-color: #94a3b8;
}

.range-button--active {
  border-color: #0f172a;
  background-color: #0f172a;
  color: #ffffff;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.2);
}

.refresh-group {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.refresh-button {
  padding: 0.625rem 1.25rem;
  border-radius: 0.75rem;
  background-color: #0f172a;
  color: #ffffff;
  font-size: 0.875rem;
  font-weight: 500;
  border: none;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.2);
  cursor: pointer;
  transition: opacity 0.2s ease;
}

.refresh-button:hover {
  opacity: 0.95;
}

.refresh-button:active {
  opacity: 0.9;
}

.refresh-button:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px rgba(148, 163, 184, 0.4);
}

.refresh-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.stats-card {
  border-radius: 1.5rem;
  border: 1px solid rgba(226, 232, 240, 0.8);
  background-color: #ffffff;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08);
  overflow: hidden;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid #e2e8f0;
}

.card-title {
  margin: 0;
  font-size: 0.875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #334155;
}

.stats-grid {
  display: grid;
  grid-template-columns: 1fr;
}

.metric-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 1rem 1.5rem;
  background-color: #ffffff;
}

.metric-row + .metric-row {
  border-top: 1px solid #e2e8f0;
}

.metric-row--striped {
  background-color: #f8fafc;
}

.metric-label {
  font-size: 0.875rem;
  font-weight: 500;
  color: #475569;
}

.metric-value {
  font-size: 0.875rem;
  color: #0f172a;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}

.chart-card {
  border-radius: 1.5rem;
  border: 1px solid #e2e8f0;
  background-color: #ffffff;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.chart-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid #e2e8f0;
}

.chart-content {
  padding: 1.25rem;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 22rem;
  flex: 1 1 auto;
}

.chart-content .muted-text {
  width: 100%;
  text-align: center;
}

.average-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.35rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.03em;
  color: #14532d;
  background-color: #dcfce7;
  border: 1px solid #bbf7d0;
}

@media (min-width: 768px) {
  .overview-card {
    padding: 2.25rem 2.5rem;
  }

  .overview-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    align-items: flex-start;
  }

  .price-details {
    text-align: right;
    align-items: flex-end;
  }

  .price-row {
    justify-content: flex-end;
  }

  .symbol-text,
  .price-value {
    font-size: 2.25rem;
  }

  .range-section {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
    gap: 1.5rem;
  }

  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .metric-row {
    padding: 1.25rem 1.75rem;
  }

  .metric-row + .metric-row {
    border-top: none;
  }

  .metric-row {
    border-top: none;
  }

  .metric-row:nth-child(odd) {
    border-right: 1px solid #e2e8f0;
  }

  .metric-row:nth-child(n + 3) {
    border-top: 1px solid #e2e8f0;
  }

  .chart-content {
    padding: 1.75rem;
    height: 24rem;
  }
}
</style>
