<script setup>
import { ref, watch, onMounted } from 'vue'
import { Chart, LineController, LineElement, PointElement, LinearScale, TimeScale, Tooltip, Filler, CategoryScale } from 'chart.js'
import 'chartjs-adapter-date-fns'

Chart.register(LineController, LineElement, PointElement, LinearScale, TimeScale, Tooltip, Filler, CategoryScale)

const props = defineProps({
  history: { type: Object, required: false, default: null },
  indicators: { type: Object, required: false, default: () => ({}) },
  average: { type: Number, required: false, default: null }
})

const canvasEl = ref(null)
let chart = null

function buildChart() {
  if (!props.history || !props.history.candles) return
  const labels = props.history.candles.map(c => new Date(c.date))
  const close = props.history.candles.map(c => c.close)
  if (!close.length) return

  const averageClose = Number.isFinite(props.average)
    ? props.average
    : close.reduce((sum, value) => sum + value, 0) / close.length
  const averageLine = close.map(() => averageClose)
  const positiveColor = '#16a34a'
  const negativeColor = '#dc2626'
  const neutralColor = '#64748b'

  const datasets = [
    {
      label: `${props.history.ticker} Close`,
      data: close,
      fill: false,
      tension: 0.1,
      borderWidth: 2,
      borderColor: negativeColor,
      pointRadius: 0,
      pointHitRadius: 8,
      pointHoverRadius: 4,
      pointBackgroundColor: ctx => (ctx.parsed.y >= averageClose ? positiveColor : negativeColor),
      pointBorderWidth: 0,
      segment: {
        borderColor: ctx => (ctx.p1?.parsed?.y ?? averageClose) >= averageClose ? positiveColor : negativeColor
      }
    },
    {
      label: 'Average Close',
      data: averageLine,
      fill: false,
      tension: 0,
      borderColor: neutralColor,
      borderWidth: 1.5,
      borderDash: [6, 6],
      pointRadius: 0
    }
  ]

  if (chart) chart.destroy()
  chart = new Chart(canvasEl.value.getContext('2d'), {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      scales: {
        x: { type: 'time', time: { unit: 'month' } },
        y: { beginAtZero: false }
      },
      plugins: {
        tooltip: { enabled: true },
        legend: { display: true, labels: { usePointStyle: true } }
      }
    }
  })
}

watch([
  () => props.history,
  () => props.average
], buildChart, { deep: true })
onMounted(buildChart)
</script>

<template>
  <div class="chart-wrapper">
    <canvas ref="canvasEl" class="chart-canvas" aria-label="Price chart" />
  </div>
</template>

<style scoped>
.chart-wrapper {
  position: relative;
  width: 100%;
  height: 22rem;
  max-height: 22rem;
  display: flex;
  align-items: center;
  justify-content: center;
}

.chart-canvas {
  width: 100% !important;
  height: 100% !important;
}

@media (min-width: 1024px) {
  .chart-wrapper {
    height: 24rem;
    max-height: 24rem;
  }
}
</style>
