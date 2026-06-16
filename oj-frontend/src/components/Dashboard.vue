<template>
  <div :class="['dashboard', theme === 'vs-dark' ? 'theme-dark' : 'theme-light']">
    <!-- 概览卡片 -->
    <div class="overview-cards">
      <div class="card">
        <div class="card-icon">📝</div>
        <div class="card-value">{{ overview.total_submissions ?? '-' }}</div>
        <div class="card-label">总提交数</div>
      </div>
      <div class="card">
        <div class="card-icon">✅</div>
        <div class="card-value">{{ overview.ac_rate != null ? overview.ac_rate + '%' : '-' }}</div>
        <div class="card-label">AC 通过率</div>
      </div>
      <div class="card">
        <div class="card-icon">👥</div>
        <div class="card-value">{{ overview.unique_users ?? '-' }}</div>
        <div class="card-label">活跃用户</div>
      </div>
      <div class="card">
        <div class="card-icon">📚</div>
        <div class="card-value">{{ overview.unique_problems ?? '-' }}</div>
        <div class="card-label">题目总数</div>
      </div>
    </div>

    <!-- 图表区 -->
    <div class="charts-grid">
      <div class="chart-panel">
        <div class="chart-header">
          <h3>📈 提交趋势</h3>
          <select v-model="trendDays" @change="fetchTrend" class="days-select">
            <option :value="7">近 7 天</option>
            <option :value="30">近 30 天</option>
            <option :value="90">近 90 天</option>
          </select>
        </div>
        <div ref="trendChart" class="chart-box"></div>
      </div>

      <div class="chart-panel">
        <div class="chart-header">
          <h3>🥧 判题状态分布</h3>
        </div>
        <div ref="pieChart" class="chart-box"></div>
      </div>

      <div class="chart-panel chart-panel-wide">
        <div class="chart-header">
          <h3>🏆 用户 AC 排名 (Top 10)</h3>
        </div>
        <div ref="barChart" class="chart-box"></div>
      </div>
    </div>

    <!-- 自动刷新 -->
    <div class="refresh-bar">
      <label>
        <input type="checkbox" v-model="autoRefresh" @change="toggleAutoRefresh" />
        自动刷新 (30s)
      </label>
      <button class="btn-refresh" @click="fetchAll">🔄 立即刷新</button>
      <span class="refresh-time" v-if="lastRefresh">上次刷新: {{ lastRefresh }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import axios from 'axios'
import * as echarts from 'echarts'

const props = defineProps({
  theme: { type: String, default: 'vs-dark' },
  token: { type: String, default: '' }
})

const DJANGO_API = import.meta.env.VITE_DJANGO_BASE_URL || 'http://127.0.0.1:8000'
const authHeaders = computed(() => props.token ? { Authorization: `Bearer ${props.token}` } : {})

// 概览数据
const overview = ref({})

// 趋势
const trendDays = ref(30)
const trendChart = ref(null)
const pieChart = ref(null)
const barChart = ref(null)

// 自动刷新
const autoRefresh = ref(false)
const isPageVisible = ref(true)
let refreshTimer = null
const lastRefresh = ref('')

// Echarts 实例
let trendInstance = null
let pieInstance = null
let barInstance = null

// 主题色
const isDark = () => props.theme === 'vs-dark'

function chartColors() {
  return isDark()
    ? { bg: '#1e1e1e', text: '#e0e0e0', border: '#333' }
    : { bg: '#ffffff', text: '#2c3e50', border: '#e4e7ed' }
}

// ---------- API 请求 ----------
async function fetchOverview() {
  try {
    const res = await axios.get(`${DJANGO_API}/api/dashboard/overview/`, { headers: authHeaders.value })
    if (res.data.code === 200) overview.value = res.data.data
  } catch (e) { console.error('Dashboard fetch failed', e) }
}

async function fetchTrend() {
  try {
    const res = await axios.get(`${DJANGO_API}/api/dashboard/submissions-trend/?days=${trendDays.value}`, { headers: authHeaders.value })
    if (res.data.code === 200) renderTrend(res.data.data)
  } catch (e) { console.error('Dashboard fetch failed', e) }
}

async function fetchStatusDist() {
  try {
    const res = await axios.get(`${DJANGO_API}/api/dashboard/status-distribution/`, { headers: authHeaders.value })
    if (res.data.code === 200) renderPie(res.data.data)
  } catch (e) { console.error('Dashboard fetch failed', e) }
}

async function fetchRanking() {
  try {
    const res = await axios.get(`${DJANGO_API}/api/dashboard/user-ranking/?limit=10`, { headers: authHeaders.value })
    if (res.data.code === 200) renderBar(res.data.data)
  } catch (e) { console.error('Dashboard fetch failed', e) }
}

async function fetchAll() {
  await Promise.all([fetchOverview(), fetchTrend(), fetchStatusDist(), fetchRanking()])
  lastRefresh.value = new Date().toLocaleTimeString()
}

// ---------- Echarts 渲染 ----------
function makeBaseOption() {
  const c = chartColors()
  return {
    backgroundColor: c.bg,
    textStyle: { color: c.text },
    grid: { top: 40, right: 20, bottom: 40, left: 50 },
  }
}

function renderTrend(data) {
  if (!trendChart.value) return
  if (!trendInstance) trendInstance = echarts.init(trendChart.value)
  const c = chartColors()
  trendInstance.setOption({
    ...makeBaseOption(),
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category', data: data.dates,
      axisLabel: { color: c.text }, axisLine: { lineStyle: { color: c.border } }
    },
    yAxis: {
      type: 'value', name: '提交数',
      axisLabel: { color: c.text }, nameTextStyle: { color: c.text },
      splitLine: { lineStyle: { color: c.border, type: 'dashed' } }
    },
    series: [{
      type: 'line', data: data.counts,
      smooth: true, symbol: 'circle', symbolSize: 6,
      lineStyle: { color: '#409eff', width: 3 },
      itemStyle: { color: '#409eff' },
      areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
        { offset: 0, color: 'rgba(64,158,255,0.3)' },
        { offset: 1, color: 'rgba(64,158,255,0.02)' }
      ])}
    }]
  })
}

const STATUS_COLORS = {
  AC: '#67c23a', WA: '#f56c6c', TLE: '#e6a23c',
  MLE: '#f39c12', CE: '#909399', PENDING: '#409eff', JUDGING: '#00ff66'
}

function renderPie(data) {
  if (!pieChart.value) return
  if (!pieInstance) pieInstance = echarts.init(pieChart.value)
  pieInstance.setOption({
    ...makeBaseOption(),
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    series: [{
      type: 'pie', radius: ['45%', '75%'], center: ['50%', '55%'],
      avoidLabelOverlap: false,
      label: { show: true, position: 'outside', formatter: '{b}\n{d}%' },
      emphasis: { label: { fontSize: 18, fontWeight: 'bold' } },
      data: data.map(d => ({
        name: d.name,
        value: d.value,
        itemStyle: { color: STATUS_COLORS[d.name] || '#999' }
      }))
    }]
  })
}

function renderBar(data) {
  if (!barChart.value) return
  if (!barInstance) barInstance = echarts.init(barChart.value)
  const c = chartColors()
  const names = data.map(d => d.username).reverse()
  const values = data.map(d => d.ac_count).reverse()
  barInstance.setOption({
    ...makeBaseOption(),
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: {
      type: 'value', name: 'AC 数量',
      axisLabel: { color: c.text }, nameTextStyle: { color: c.text },
      splitLine: { lineStyle: { color: c.border, type: 'dashed' } }
    },
    yAxis: {
      type: 'category', data: names,
      axisLabel: { color: c.text }, axisLine: { lineStyle: { color: c.border } }
    },
    series: [{
      type: 'bar', data: values,
      barWidth: 20,
      itemStyle: {
        borderRadius: [0, 4, 4, 0],
        color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
          { offset: 0, color: '#00ff66' }, { offset: 1, color: '#409eff' }
        ])
      }
    }]
  })
}

// ---------- 主题切换 ----------
watch(() => props.theme, async () => {
  await nextTick()
  disposeCharts()
  trendInstance = null; pieInstance = null; barInstance = null
  await fetchAll()
})

function disposeCharts() {
  trendInstance?.dispose()
  pieInstance?.dispose()
  barInstance?.dispose()
}

// ---------- 自动刷新 ----------
function startRefreshTimer() {
  stopRefreshTimer()
  refreshTimer = setInterval(fetchAll, 30000)
}

function stopRefreshTimer() {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}

function toggleAutoRefresh() {
  if (autoRefresh.value && isPageVisible.value) {
    startRefreshTimer()
  } else {
    stopRefreshTimer()
  }
}

function handleVisibility() {
  isPageVisible.value = !document.hidden
  if (autoRefresh.value) {
    if (isPageVisible.value) {
      startRefreshTimer()
      fetchAll()  // 切回页面时立即刷新一次
    } else {
      stopRefreshTimer()
    }
  }
}

// ---------- 生命周期 ----------
onMounted(async () => {
  await nextTick()
  await fetchAll()
  document.addEventListener('visibilitychange', handleVisibility)
})

onUnmounted(() => {
  stopRefreshTimer()
  disposeCharts()
  document.removeEventListener('visibilitychange', handleVisibility)
})
</script>

<style scoped>
.dashboard { padding: 10px 0; }

/* 概览卡片 */
.overview-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}
.card {
  background: #1e1e1e;
  border: 1px solid #333;
  border-radius: 12px;
  padding: 20px 16px;
  text-align: center;
  transition: all 0.3s;
}
.card:hover { transform: translateY(-2px); border-color: #409eff; box-shadow: 0 4px 20px rgba(64,158,255,0.15); }
.card-icon { font-size: 28px; margin-bottom: 6px; }
.card-value { font-size: 32px; font-weight: 900; color: #409eff; }
.card-label { font-size: 13px; color: #a0a0a0; margin-top: 4px; }

/* 浅色卡片 */
.theme-light .card { background: #ffffff; border-color: #e4e7ed; }
.theme-light .card:hover { border-color: #409eff; box-shadow: 0 4px 20px rgba(0,0,0,0.08); }

/* 图表网格 */
.charts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}
.chart-panel-wide { grid-column: 1 / -1; }
.chart-panel {
  background: #1e1e1e;
  border: 1px solid #333;
  border-radius: 12px;
  padding: 16px;
}
.theme-light .chart-panel { background: #ffffff; border-color: #e4e7ed; }

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.chart-header h3 { margin: 0; font-size: 16px; }
.days-select {
  background: #2b2b2b; color: #00ff66; border: 1px solid #555;
  padding: 4px 10px; border-radius: 4px; font-size: 13px; cursor: pointer;
}
.theme-light .days-select { background: #f0f2f5; color: #409eff; border-color: #dcdfe6; }

.chart-box { width: 100%; height: 320px; }

/* 刷新栏 */
.refresh-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 16px;
  background: #1e1e1e;
  border: 1px solid #333;
  border-radius: 8px;
  font-size: 13px;
}
.theme-light .refresh-bar { background: #ffffff; border-color: #e4e7ed; }
.refresh-bar label { display: flex; align-items: center; gap: 6px; cursor: pointer; color: inherit; }
.btn-refresh {
  background: #2b2b2b; color: #00ff66; border: 1px solid #00ff66;
  padding: 6px 14px; border-radius: 4px; cursor: pointer; font-weight: bold; transition: all 0.2s;
}
.btn-refresh:hover { background: #00ff66; color: #121212; }
.theme-light .btn-refresh { background: #f0f2f5; color: #409eff; border-color: #409eff; }
.refresh-time { color: #888; margin-left: auto; }
</style>
