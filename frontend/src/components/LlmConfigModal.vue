<template>
  <Teleport to="body">
    <Transition name="llm-modal">
      <div v-if="visible" class="llm-overlay" @click.self="close">
        <section class="llm-modal" role="dialog" aria-modal="true">
          <header class="llm-header">
            <div>
              <div class="llm-kicker">{{ $t('llm.kicker') }}</div>
              <h2>{{ $t('llm.title') }}</h2>
              <p>{{ $t('llm.description') }}</p>
            </div>
            <button class="llm-close" type="button" @click="close">×</button>
          </header>

          <form class="llm-form" @submit.prevent="handleSave">
            <label class="llm-field">
              <span>{{ $t('llm.graphBackend') }}</span>
              <select v-model="form.graph_backend" :disabled="loading">
                <option value="local">{{ $t('llm.localBackend') }}</option>
                <option value="zep">{{ $t('llm.zepBackend') }}</option>
              </select>
              <small>{{ $t('llm.graphBackendHint') }}</small>
            </label>

            <label v-if="form.graph_backend === 'zep'" class="llm-field">
              <span>{{ $t('llm.zepApiKey') }}</span>
              <input
                v-model="form.zep_api_key"
                type="password"
                autocomplete="new-password"
                :placeholder="config.zep_api_key_masked || $t('llm.zepApiKeyPlaceholder')"
                :disabled="loading"
              />
              <small>{{ $t('llm.zepApiKeyHint') }}</small>
            </label>

            <label class="llm-field">
              <span>{{ $t('llm.apiKey') }}</span>
              <input
                v-model="form.api_key"
                type="password"
                autocomplete="new-password"
                :placeholder="config.api_key_masked || $t('llm.apiKeyPlaceholder')"
                :disabled="loading"
              />
              <small>{{ $t('llm.apiKeyHint') }}</small>
            </label>

            <label class="llm-field">
              <span>{{ $t('llm.baseUrl') }}</span>
              <input
                v-model="form.base_url"
                type="url"
                autocomplete="url"
                placeholder="https://api.openai.com/v1"
                :disabled="loading"
              />
            </label>

            <label class="llm-field">
              <span>{{ $t('llm.modelName') }}</span>
              <input
                v-model="form.model_name"
                type="text"
                autocomplete="off"
                placeholder="gpt-4o-mini"
                :disabled="loading"
              />
            </label>

            <div v-if="message" class="llm-message" :class="messageType">
              {{ message }}
            </div>

            <footer class="llm-actions">
              <button class="llm-button secondary" type="button" :disabled="loading" @click="handleTest">
                {{ testing ? $t('llm.testing') : $t('llm.testConnection') }}
              </button>
              <button class="llm-button primary" type="submit" :disabled="loading">
                {{ saving ? $t('llm.saving') : $t('llm.save') }}
              </button>
            </footer>
          </form>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { getLlmConfig, saveLlmConfig, testLlmConnection } from '../api/llm'

const emit = defineEmits(['close'])

const visible = ref(true)
const loading = ref(false)
const testing = ref(false)
const saving = ref(false)
const message = ref('')
const messageType = ref('')
const config = reactive({
  api_key_configured: false,
  api_key_masked: '',
  base_url: '',
  model_name: '',
  graph_backend: 'local',
  zep_api_key_configured: false,
  zep_api_key_masked: ''
})
const form = reactive({
  api_key: '',
  base_url: '',
  model_name: '',
  graph_backend: 'local',
  zep_api_key: ''
})

const close = () => {
  if (loading.value) return
  visible.value = false
  emit('close')
}

const setMessage = (text, type) => {
  message.value = text
  messageType.value = type
}

const loadConfig = async () => {
  loading.value = true
  try {
    const res = await getLlmConfig()
    Object.assign(config, res.data || {})
    form.base_url = config.base_url
    form.model_name = config.model_name
    form.graph_backend = config.graph_backend || 'local'
  } catch (error) {
    setMessage(error.message || 'Failed to load LLM configuration', 'error')
  } finally {
    loading.value = false
  }
}

const handleTest = async () => {
  testing.value = true
  loading.value = true
  setMessage('', '')
  try {
    const res = await testLlmConnection(form)
    setMessage(res.message || 'LLM connection succeeded', 'success')
  } catch (error) {
    setMessage(error.message || 'LLM connection failed', 'error')
  } finally {
    testing.value = false
    loading.value = false
  }
}

const handleSave = async () => {
  saving.value = true
  loading.value = true
  setMessage('', '')
  try {
    const res = await saveLlmConfig(form)
    Object.assign(config, res.data || {})
    form.api_key = ''
    form.zep_api_key = ''
    setMessage('LLM configuration saved', 'success')
  } catch (error) {
    setMessage(error.message || 'Failed to save LLM configuration', 'error')
  } finally {
    saving.value = false
    loading.value = false
  }
}

onMounted(loadConfig)
</script>

<style scoped>
.llm-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(0, 0, 0, 0.58);
}

.llm-modal {
  width: min(520px, 100%);
  background: #fff;
  border: 1px solid #111;
  box-shadow: 10px 10px 0 #ff4500;
  color: #111;
}

.llm-header {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  padding: 28px 30px 20px;
  border-bottom: 1px solid #e5e5e5;
}

.llm-kicker {
  margin-bottom: 8px;
  color: #ff4500;
  font: 700 11px/1.2 'JetBrains Mono', monospace;
  letter-spacing: 1px;
}

.llm-header h2 {
  margin: 0 0 8px;
  font-size: 25px;
  font-weight: 600;
}

.llm-header p {
  margin: 0;
  color: #777;
  font-size: 13px;
  line-height: 1.5;
}

.llm-close {
  width: 30px;
  height: 30px;
  border: 1px solid #ddd;
  background: #fff;
  color: #111;
  cursor: pointer;
  font-size: 22px;
  line-height: 1;
}

.llm-form {
  display: grid;
  gap: 18px;
  padding: 26px 30px 30px;
}

.llm-field {
  display: grid;
  gap: 7px;
}

.llm-field > span {
  font: 700 12px/1.2 'JetBrains Mono', monospace;
  letter-spacing: 0.3px;
}

.llm-field input,
.llm-field select {
  width: 100%;
  height: 42px;
  padding: 0 12px;
  border: 1px solid #cfcfcf;
  outline: none;
  color: #111;
  background: #fff;
  font: 13px 'JetBrains Mono', monospace;
}

.llm-field input:focus,
.llm-field select:focus {
  border-color: #ff4500;
  box-shadow: 3px 3px 0 rgba(255, 69, 0, 0.18);
}

.llm-field small {
  color: #888;
  font-size: 11px;
}

.llm-message {
  padding: 10px 12px;
  font-size: 13px;
  line-height: 1.4;
}

.llm-message.success {
  background: #effaf1;
  color: #237a36;
}

.llm-message.error {
  background: #fff1ef;
  color: #bd2d20;
}

.llm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 4px;
}

.llm-button {
  min-width: 120px;
  height: 40px;
  padding: 0 16px;
  border: 1px solid #111;
  cursor: pointer;
  font: 700 12px 'JetBrains Mono', monospace;
}

.llm-button:disabled,
.llm-close:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.llm-button.secondary {
  background: #fff;
  color: #111;
}

.llm-button.primary {
  background: #111;
  color: #fff;
}

.llm-button.primary:hover:not(:disabled) {
  background: #ff4500;
  border-color: #ff4500;
}

.llm-modal-enter-active,
.llm-modal-leave-active {
  transition: opacity 0.18s ease;
}

.llm-modal-enter-active .llm-modal,
.llm-modal-leave-active .llm-modal {
  transition: transform 0.18s ease;
}

.llm-modal-enter-from,
.llm-modal-leave-to {
  opacity: 0;
}

.llm-modal-enter-from .llm-modal,
.llm-modal-leave-to .llm-modal {
  transform: translateY(12px);
}
</style>
