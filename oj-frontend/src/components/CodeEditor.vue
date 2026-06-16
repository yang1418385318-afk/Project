<template>
  <div class="editor-container" :class="theme === 'vs' ? 'light-border' : 'dark-border'">
    <vue-monaco-editor
      v-model:value="code"
      :language="language === 'python3' ? 'python' : language"
      :theme="theme"
      height="55vh"
      :options="editorOptions"
      @mount="handleMount"
    />
  </div>
</template>

<script setup>
import { ref, watch, shallowRef } from 'vue'
import { createEditorOptions } from '../editorConfig.js'

// 接收父组件传来的语言和主题
const props = defineProps({
  language: { type: String, default: 'python3' },
  theme: { type: String, default: 'vs-dark' }, // 'vs-dark' 是深色, 'vs' 是浅色
  modelValue: { type: String, default: '' }
})
const emit = defineEmits(['update:modelValue'])

const code = ref(props.modelValue)
const editorRef = shallowRef(null)

const editorOptions = createEditorOptions()

watch(() => props.modelValue, (newVal) => { if (newVal !== code.value) code.value = newVal })
watch(code, (newVal) => { emit('update:modelValue', newVal) })

const handleMount = (editor) => { editorRef.value = editor }
</script>

<style scoped>
.editor-container { border-radius: 8px; overflow: hidden; margin-top: 15px; transition: all 0.3s;}
.dark-border { border: 1px solid #333; }
.light-border { border: 1px solid #ccc; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
</style>
