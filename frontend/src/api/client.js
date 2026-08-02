import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

const client = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

let isRefreshing = false
let refreshQueue = []

function resolveQueue(token) {
  refreshQueue.forEach((cb) => cb(token))
  refreshQueue = []
}

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const { response, config } = error
    if (!response || response.status !== 401 || config._retry) {
      return Promise.reject(error)
    }

    const refreshToken = localStorage.getItem('refresh_token')
    if (!refreshToken) {
      return Promise.reject(error)
    }

    config._retry = true

    if (isRefreshing) {
      return new Promise((resolve) => {
        refreshQueue.push((token) => {
          config.headers.Authorization = `Bearer ${token}`
          resolve(client(config))
        })
      })
    }

    isRefreshing = true
    try {
      const { data } = await axios.post(`${BASE_URL}/auth/refresh`, {
        refresh_token: refreshToken,
      })
      localStorage.setItem('access_token', data.access_token)
      resolveQueue(data.access_token)
      config.headers.Authorization = `Bearer ${data.access_token}`
      return client(config)
    } catch (refreshError) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      window.location.assign('/login')
      return Promise.reject(refreshError)
    } finally {
      isRefreshing = false
    }
  }
)

export default client

// --- Auth ---
export const login = (username, password) =>
  client.post('/auth/login', { username, password })
export const me = () => client.get('/auth/me')
export const logout = () => client.post('/auth/logout')

// --- Devices ---
export const listDevices = (params) => client.get('/devices', { params })
export const getDevice = (id) => client.get(`/devices/${id}`)
export const updateDevice = (id, body) => client.patch(`/devices/${id}`, body)
export const getDeviceFlows = (id, params) => client.get(`/devices/${id}/flows`, { params })
export const getDeviceVitals = (id, params) => client.get(`/devices/${id}/vitals`, { params })
export const getDeviceTimeline = (id, params) => client.get(`/devices/${id}/timeline`, { params })

// --- Flows & Detections ---
export const listFlows = (params) => client.get('/flows', { params })
export const listDetections = (params) => client.get('/detections', { params })
export const getDetection = (id) => client.get(`/detections/${id}`)

// --- Alerts ---
export const listAlerts = (params) => client.get('/alerts', { params })
export const getAlert = (id) => client.get(`/alerts/${id}`)
export const acknowledgeAlert = (id) => client.post(`/alerts/${id}/acknowledge`)
export const assignAlert = (id, userId) => client.post(`/alerts/${id}/assign`, { user_id: userId })
export const resolveAlert = (id, notes) => client.post(`/alerts/${id}/resolve`, { resolution_notes: notes })
export const markFalsePositive = (id) => client.post(`/alerts/${id}/false-positive`)
export const commentOnAlert = (id, comment) => client.post(`/alerts/${id}/comment`, { comment })

// --- Models ---
export const listModels = () => client.get('/models')
export const getModelMetrics = (id) => client.get(`/models/${id}/metrics`)
export const activateModel = (id) => client.post(`/models/${id}/activate`)
export const retrainModel = (body) => client.post('/models/retrain', body)
export const getFeatureImportance = (id) => client.get(`/models/${id}/feature-importance`)

// --- Stats & Reports ---
export const getStatsOverview = () => client.get('/stats/overview')
export const getAttackDistribution = (params) => client.get('/stats/attack-distribution', { params })
export const getTrafficTimeline = (params) => client.get('/stats/traffic-timeline', { params })
export const generateReport = (body) => client.post('/reports/generate', body)
export const downloadReport = (id) => client.get(`/reports/${id}/download`, { responseType: 'blob' })

// --- Attack Simulator (demo-only; not in the core §12 spec, wraps simulator/attacker_*.py) ---
export const launchAttack = (deviceId, attackCode) =>
  client.post('/simulator/launch', { device_id: deviceId, attack_code: attackCode })
