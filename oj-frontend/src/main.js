import { createApp } from 'vue'
import { install as VueMonacoEditorPlugin } from '@guolao/vue-monaco-editor'
import App from './App.vue'
import { setupClipboardPermissionGuard } from './clipboardPermissionGuard.js'

setupClipboardPermissionGuard()

const app = createApp(App)

app.use(VueMonacoEditorPlugin, {
  paths: {
    vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@0.43.0/min/vs',
  },
})

app.mount('#app')
