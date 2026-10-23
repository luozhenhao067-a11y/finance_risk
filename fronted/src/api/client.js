import axios from 'axios'

// Spec 8.4 Mock 策略：VITE_USE_MOCK !== 'false' 时走本地 mock，切换后端仅改此开关与 baseURL
export const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false'

export const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api/v1',
  timeout: 15000
})

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('finance-risk-audit-token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

client.interceptors.response.use(
  (response) => {
    const body = response.data
    if (body && typeof body === 'object' && 'code' in body) {
      if (body.code === 0) return body.data
      return Promise.reject(new Error(body.message || '请求失败'))
    }
    return body
  },
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('finance-risk-audit-token')
      if (window.location.pathname !== '/login') window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)
