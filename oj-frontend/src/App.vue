<template>
  <div :class="['oj-app', currentTheme === 'vs' ? 'light-mode' : 'dark-mode']">
    <header class="app-header">
      <h1>🚀 Geek OJ 极客评测台</h1>
      <button class="btn-theme" @click="toggleTheme">
        {{ currentTheme === 'vs-dark' ? '☀️ 切换至浅色模式' : '🌙 切换至深色模式' }}
      </button>
    </header>

    <!-- 导航标签 -->
    <nav class="nav-tabs" v-if="token">
      <button :class="['nav-tab', activeTab === 'code' ? 'active' : '']" @click="activeTab = 'code'">
        💻 代码评测台
      </button>
      <button :class="['nav-tab', activeTab === 'dashboard' ? 'active' : '']" @click="activeTab = 'dashboard'">
        📊 运行监控大盘
      </button>
    </nav>

    <div class="auth-section">
      <div v-if="!token" class="login-form">
        <input v-model="username" placeholder="👨‍💻 请输入管理员账号" class="cool-input" />
        <input v-model="password" type="password" placeholder="🔑 请输入密码" class="cool-input" />
        <button class="btn-login" @click="handleLogin">
          ⚡ 验证身份并连接集群
        </button>
      </div>
      <div v-else>
        <button class="btn-login" disabled>
          🟢 已安全连接微服务集群 (当前用户: {{ currentUsername }})
        </button>
      </div>
    </div>

    <div class="main-content" v-if="token && activeTab === 'code'">
      <div class="control-panel">
        <div class="selector-group">
          <label>📁 选择题目：</label>
          <select v-model="currentProblemId" class="cool-select">
            <option v-for="p in problemList" :key="p.id" :value="p.id">
              {{ p.id }}. {{ p.title }}
            </option>
          </select>
        </div>

        <div class="selector-group">
          <label>⚙️ 编译语言：</label>
          <select v-model="currentLang" class="cool-select" @change="setDefaultCode">
            <option value="python3">Python 3.9</option>
            <option value="cpp">C++ (GCC 11)</option>
            <option value="java">Java (OpenJDK 17)</option>
          </select>
        </div>
      </div>

      <CodeEditor v-model="submitCode" :language="currentLang" :theme="currentTheme" />

      <div class="action-bar">
        <button class="btn-submit" @click="handleSubmit" :disabled="loading">
          {{ loading ? '⏳ 正在动态沙箱中编译执行...' : '▶️ 提交至集群评测' }}
        </button>

        <div class="status-box" v-if="judgeStatus !== 'IDLE'">
          <span :class="['status-badge', judgeStatus]">最终判定: {{ judgeStatus }}</span>
        </div>
      </div>

      <div class="logs" v-if="logs.length">
        <h4>📡 分布式流转轨迹：</h4>
        <p v-for="(log, idx) in logs" :key="idx">> {{ log }}</p>
      </div>
    </div>

    <Dashboard v-if="token && activeTab === 'dashboard'" :theme="currentTheme" :token="token" />
  </div>
</template>


<script setup>
import { ref, onMounted, defineAsyncComponent } from 'vue'
import axios from 'axios'

const CodeEditor = defineAsyncComponent(() => import('./components/CodeEditor.vue'))
const Dashboard = defineAsyncComponent(() => import('./components/Dashboard.vue'))

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8080'
const API_DJANGO_BASE = import.meta.env.VITE_DJANGO_BASE_URL || 'http://127.0.0.1:8000'
// 核心状态数据
const token = ref('')
const loading = ref(false)
const judgeStatus = ref('IDLE')
const logs = ref([])

// 新增功能状态
const currentTheme = ref('vs-dark') // 默认深色
const currentLang = ref('python3')
const currentProblemId = ref(1)
const submitCode = ref('')

// 模拟的题库数据（实际可从后端拉取）
// 变成响应式的空数组，等待后端喂数据
const problemList = ref([])

// 新增账号密码的状态绑定
const username = ref('')
const password = ref('')
const currentUsername = ref('')
const activeTab = ref('code')

// 动态拉取真题库
const fetchProblems = async () => {
  try {
    // 注意：去 8000 端口（Django大本营）拉取题库
    const res = await axios.get(`${API_DJANGO_BASE}/api/problems/`)
    if (res.data.code === 200) {
      problemList.value = res.data.data

      // 拉取成功后，默认选中列表里的第一道题
      if (problemList.value.length > 0) {
        currentProblemId.value = problemList.value[0].id
      }
    }
  } catch (err) {
    // 题库拉取失败时静默处理，UI 会显示空列表
  }
}

// 页面一加载，立刻执行拉取动作
onMounted(() => {
  fetchProblems()
})

// 语言对应的初始代码模板 (极其提升用户体验！)
const codeTemplates = {
  cpp: `#include <iostream>
using namespace std;

int main() {
    // 请在此处编写你的代码，处理输入输出

    return 0;
}`,
  java: `import java.util.Scanner;

public class Main {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        // 请在此处编写你的代码，处理输入输出

    }
}`,
  python3: `# 请在此处编写你的代码，处理输入输出
import sys
`
}

// 切换语言时自动填充对应模板
const setDefaultCode = () => { submitCode.value = codeTemplates[currentLang.value] }
// 初始化默认语言模板
setDefaultCode()

// 切换深浅主题
const toggleTheme = () => {
  currentTheme.value = currentTheme.value === 'vs-dark' ? 'vs' : 'vs-dark'
}

const handleLogin = async () => {
  if (!username.value || !password.value) {
    alert('⚠️ 账号和密码不能为空！')
    return
  }

  try {
    // 🚀 核心跨域请求：打向 Django 大本营拿真实的 JWT
    const res = await axios.post(`${API_DJANGO_BASE}/api/login/`, {
      username: username.value,
      password: password.value
    })

    if (res.data.code === 200) {
      // 拿到真钥匙了！
      token.value = res.data.token
      currentUsername.value = res.data.username
      logs.value.push(`[Auth] 鉴权成功！欢迎回来，${currentUsername.value}。`)
    } else {
      alert(`❌ 登录失败：${res.data.message}`)
    }
  } catch (err) {
    if (err.response && err.response.status === 401) {
      alert('❌ 账号或密码错误！')
    } else {
      alert('❌ 网络请求失败，请检查 Django 服务是否正常运行')
    }
  }
}

const handleSubmit = async () => {
  if (!token.value) return
  loading.value = true; judgeStatus.value = 'PENDING'; logs.value = []

  try {
    // 1. 提交时，带上动态选择的语言和题目ID
    const submitRes = await axios.post(`${API_BASE}/submit/`, {
      problem_id: currentProblemId.value,
      code: submitCode.value,
      language: currentLang.value
    }, { headers: { Authorization: `Bearer ${token.value}` } })

    const taskId = submitRes.data.task_id
    logs.value.push(`[Queue] 代码入队成功！TaskID: ${taskId}`)

    // ==========================================
    // 🚀 WebSocket 自动重连：指数退避，最大3次
    // ==========================================
    const MAX_RETRIES = 3
    let wsRetryCount = 0
    let wsResultReceived = false  // 防止收到结果后仍触发重连

    const wsUrl = API_BASE.replace('http://', 'ws://') + `/ws/result/${taskId}?token=${encodeURIComponent(token.value)}`

    function connectWebSocket() {
      if (wsRetryCount >= MAX_RETRIES) {
        logs.value.push(`[Error] ❌ WebSocket 重连失败（已重试 ${MAX_RETRIES} 次），请手动刷新重试`)
        judgeStatus.value = 'SE'
        loading.value = false
        return
      }

      if (wsRetryCount > 0) {
        const delay = Math.pow(2, wsRetryCount - 1) * 1000  // 1s, 2s, 4s
        logs.value.push(`[重连] ⚡ 连接异常，正在第 ${wsRetryCount} 次重连...（等待 ${delay / 1000}s）`)
        setTimeout(() => doConnect(), delay)
      } else {
        doConnect()
      }
    }

    function doConnect() {
      const ws = new WebSocket(wsUrl)

      ws.onopen = () => {
        wsRetryCount = 0  // 连接成功，重置计数
        logs.value.push(`[WebSocket] 🟢 实时通道已建立，坐等后端主动推送...`)
      }

      ws.onmessage = (event) => {
        wsResultReceived = true
        const finalStatus = event.data
        judgeStatus.value = finalStatus
        loading.value = false
        logs.value.push(`[🎯 结束] ${currentLang.value.toUpperCase()} 沙箱执行完毕。结果: ${judgeStatus.value}`)
        ws.close()
      }

      ws.onclose = () => {
        if (!wsResultReceived) {
          // 意外关闭才重连；正常收到结果后的 close 不重连
          wsRetryCount++
          connectWebSocket()
        }
      }

      ws.onerror = () => {
        // onclose 会在 onerror 之后触发，由 onclose 统一处理重连
      }
    }

    connectWebSocket()
    // ==========================================

  } catch (err) {
    // 捕获比如没有登录、接口报错等异常
    const errorMsg = err.response?.data?.detail || '系统异常'
    logs.value.push(`[Error] 提交失败：${errorMsg}`)
    loading.value = false
    judgeStatus.value = 'SE'
  }
}
</script>

<style>
/* 终极暗黑/明亮双生主题样式 */
body { margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; transition: background 0.3s; }

/* 深色模式变量 */
.dark-mode { background: #121212; color: #e0e0e0; min-height: 100vh; }
.dark-mode .app-header { border-bottom: 2px solid #333; }
.dark-mode .control-panel { background: #1e1e1e; border: 1px solid #333; }
.dark-mode .cool-select { background: #2b2b2b; color: #00ff66; border: 1px solid #555; }
.dark-mode .logs { background: #0d0d0d; border: 1px solid #333; color: #a0a0a0; }

/* 浅色模式变量 (极致护眼) */
.light-mode { background: #f5f7fa; color: #2c3e50; min-height: 100vh; }
.light-mode .app-header { border-bottom: 2px solid #e4e7ed; background: #ffffff; padding: 10px 20px;}
.light-mode h1 { color: #2c3e50; }
.light-mode .control-panel { background: #ffffff; border: 1px solid #e4e7ed; box-shadow: 0 2px 12px 0 rgba(0,0,0,0.05); }
.light-mode .cool-select { background: #f0f2f5; color: #409eff; border: 1px solid #dcdfe6; }
.light-mode .logs { background: #ffffff; border: 1px solid #ebeef5; color: #606266; box-shadow: 0 2px 12px 0 rgba(0,0,0,0.05); }

.oj-app { max-width: 1000px; margin: 0 auto; padding: 20px; transition: all 0.3s; }
.app-header { display: flex; justify-content: space-between; align-items: center; padding-bottom: 10px; margin-bottom: 20px;}
.btn-theme { background: transparent; border: 1px solid #888; color: inherit; padding: 8px 15px; border-radius: 20px; cursor: pointer; transition: all 0.3s;}
.btn-theme:hover { transform: scale(1.05); }

.control-panel { display: flex; justify-content: space-between; padding: 15px 25px; border-radius: 8px; margin-bottom: 15px; }
.selector-group { display: flex; align-items: center; gap: 10px; font-weight: bold;}
.cool-select { padding: 8px 15px; border-radius: 4px; font-size: 14px; font-weight: bold; cursor: pointer; outline: none; }

.auth-section { margin-bottom: 20px; }
.btn-login { background: #2b2b2b; color: #00ff66; border: 1px solid #00ff66; padding: 12px 20px; cursor: pointer; border-radius: 4px; font-weight: bold; width: 100%; transition: all 0.3s;}
.btn-login:disabled { background: #1a1a1a; border-color: #00ff66; color: #00ff66; cursor: not-allowed; }

.action-bar { margin-top: 20px; display: flex; align-items: center; justify-content: space-between; gap: 20px; }
.btn-submit { background: #0066ff; color: #fff; border: none; padding: 12px 40px; cursor: pointer; border-radius: 4px; font-weight: bold; font-size: 16px; transition: background 0.3s; box-shadow: 0 4px 6px rgba(0,102,255,0.3);}
.btn-submit:hover { background: #005ce6; }
.btn-submit:disabled { background: #a0cfff; cursor: not-allowed; box-shadow: none;}

.status-box { padding: 10px 20px; border-radius: 4px; font-size: 22px; font-weight: 900;}
.AC { color: #67c23a; } .WA { color: #f56c6c; } .RE { color: #e6a23c; } .PENDING { color: #409eff; animation: pulse 1s infinite;}
.logs { margin-top: 30px; padding: 15px; border-radius: 8px; font-family: monospace; font-size: 13px; }
@keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
.login-form { display: flex; gap: 10px; }
.cool-input { padding: 10px 15px; border-radius: 4px; border: 1px solid #555; background: #2b2b2b; color: #fff; font-size: 14px; outline: none; flex: 1;}
.cool-input:focus { border-color: #00ff66; }
.light-mode .cool-input { background: #fff; color: #333; border-color: #ccc; }

/* 导航标签 */
.nav-tabs { display: flex; gap: 4px; margin-bottom: 20px; }
.nav-tab {
  flex: 1; padding: 10px 20px; border: 1px solid #555; background: #2b2b2b;
  color: #a0a0a0; cursor: pointer; font-size: 15px; font-weight: bold;
  border-radius: 8px; transition: all 0.3s;
}
.nav-tab:hover { border-color: #00ff66; color: #00ff66; }
.nav-tab.active { background: #1a3a1a; color: #00ff66; border-color: #00ff66; box-shadow: 0 0 12px rgba(0,255,102,0.2); }
.light-mode .nav-tab { background: #f0f2f5; border-color: #dcdfe6; color: #606266; }
.light-mode .nav-tab:hover { border-color: #409eff; color: #409eff; }
.light-mode .nav-tab.active { background: #ecf5ff; color: #409eff; border-color: #409eff; }
</style>
