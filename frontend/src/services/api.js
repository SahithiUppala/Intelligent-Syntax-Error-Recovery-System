import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
})

export function getApiErrorMessage(error, fallback = 'Request failed') {
  if (!error) return fallback
  if (error.response?.data?.detail) {
    const detail = error.response.data.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail.map((item) => item.msg || JSON.stringify(item)).join('; ')
    }
  }
  if (error.response?.data?.message) return error.response.data.message
  if (error.code === 'ECONNABORTED') return 'Request timed out — is the backend running?'
  if (error.message === 'Network Error') {
    return 'Cannot reach backend at http://127.0.0.1:8000 — start uvicorn first.'
  }
  return error.message || fallback
}

export async function checkHealth() {
  const { data } = await api.get('/api/health')
  return data
}

export async function tokenize(code) {
  const { data } = await api.post('/api/tokenize', { code })
  return data
}

export async function parse(code) {
  const { data } = await api.post('/api/parse', { code })
  return data
}

export async function analyze(code) {
  const { data } = await api.post('/api/analyze', { code })
  return data
}

export async function fetchExamples() {
  const { data } = await api.get('/api/examples')
  return data
}

export default api
