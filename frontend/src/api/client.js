import axios from 'axios'
import { getAccessToken, getRefreshToken, updateAccessToken, clearTokens } from './tokens'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

const client = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

client.interceptors.request.use((config) => {
  const token = getAccessToken()
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

    const refreshToken = getRefreshToken()
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
      updateAccessToken(data.access_token)
      resolveQueue(data.access_token)
      config.headers.Authorization = `Bearer ${data.access_token}`
      return client(config)
    } catch (refreshError) {
      clearTokens()
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
export const register = (payload) => client.post('/auth/register', payload)
export const me = () => client.get('/auth/me')
export const logout = () => client.post('/auth/logout')

// --- Users ---
export const listUsers = (params) => client.get('/users', { params })
export const getUser = (id) => client.get(`/users/${id}`)
export const updateUser = (id, body) => client.patch(`/users/${id}`, body)
export const deleteUser = (id) => client.delete(`/users/${id}`)

// --- Devices ---
export const listDevices = (params) => client.get('/devices', { params })
export const getDevice = (id) => client.get(`/devices/${id}`)
export const createDevice = (body) => client.post('/devices', body)
export const updateDevice = (id, body) => client.patch(`/devices/${id}`, body)
export const listDeviceTypes = () => client.get('/device-types')
export const listWards = () => client.get('/wards')

export const DEVICE_STATUSES = ['online', 'offline', 'quarantined', 'maintenance']

// --- Patients ---
export const listPatients = (params) => client.get('/patients', { params })
export const getPatient = (id) => client.get(`/patients/${id}`)
export const createPatient = (body) => client.post('/patients', body)
export const updatePatient = (id, body) => client.patch(`/patients/${id}`, body)
export const listPatientAssignments = (id) => client.get(`/patients/${id}/assignments`)
export const assignDeviceToPatient = (id, deviceId) =>
  client.post(`/patients/${id}/assignments`, { device_id: deviceId })
export const releaseAssignment = (patientId, assignmentId) =>
  client.post(`/patients/${patientId}/assignments/${assignmentId}/release`)

export const PATIENT_SEXES = [
  { value: 'U', label: 'Unspecified' },
  { value: 'M', label: 'Male' },
  { value: 'F', label: 'Female' },
  { value: 'O', label: 'Other' },
]

// --- Attack types ---
export const listAttackTypes = () => client.get('/attack-types')
export const createAttackType = (body) => client.post('/attack-types', body)
export const updateAttackType = (id, body) => client.patch(`/attack-types/${id}`, body)

export const ATTACK_FAMILIES = ['BENIGN', 'DDOS', 'DOS', 'RECON', 'MQTT', 'SPOOFING', 'MALWARE', 'UNKNOWN']

// --- Protocols ---
export const listProtocols = () => client.get('/protocols')
export const createProtocol = (body) => client.post('/protocols', body)
export const updateProtocol = (id, body) => client.patch(`/protocols/${id}`, body)

// --- System config ---
export const listSystemConfig = () => client.get('/system-config')
export const createSystemConfig = (body) => client.post('/system-config', body)
export const updateSystemConfig = (key, body) => client.patch(`/system-config/${key}`, body)
export const deleteSystemConfig = (key) => client.delete(`/system-config/${key}`)

export const CONFIG_VALUE_TYPES = ['string', 'int', 'float', 'bool', 'json']

// --- Thresholds ---
export const listThresholds = (params) => client.get('/thresholds', { params })
export const createThreshold = (body) => client.post('/thresholds', body)
export const updateThreshold = (id, body) => client.patch(`/thresholds/${id}`, body)
export const deleteThreshold = (id) => client.delete(`/thresholds/${id}`)

export const THRESHOLD_SCOPES = ['global', 'device_type', 'device', 'patient']

// --- Blocklist ---
export const listBlocklist = (params) => client.get('/blocklist', { params })
export const createBlocklistEntry = (body) => client.post('/blocklist', body)
export const updateBlocklistEntry = (id, body) => client.patch(`/blocklist/${id}`, body)
export const deleteBlocklistEntry = (id) => client.delete(`/blocklist/${id}`)

export const BLOCKLIST_ENTRY_TYPES = ['ip', 'mac', 'mqtt_client']

// --- Datasets ---
export const listDatasets = () => client.get('/datasets')
export const createDataset = (body) => client.post('/datasets', body)
export const updateDataset = (id, body) => client.patch(`/datasets/${id}`, body)

// --- Audit logs ---
export const listAuditLogs = (params) => client.get('/audit-logs', { params })

// --- ML models ---
export const listModels = (params) => client.get('/models', { params })
export const getModel = (id) => client.get(`/models/${id}`)
export const registerModel = (body) => client.post('/models', body)
export const updateModel = (id, body) => client.patch(`/models/${id}`, body)
export const activateModel = (id) => client.post(`/models/${id}/activate`)
export const getModelEvaluation = (id) => client.get(`/models/${id}/evaluation`)

export const MODEL_TASK_TYPES = ['binary', 'multiclass', 'anomaly', 'regression', 'meta']
export const MODEL_STAGES = [1, 2, 3, 4, 5]

// --- Detections ---
export const listDetections = (params) => client.get('/detections', { params })
export const getDetection = (id) => client.get(`/detections/${id}`)

export const explainDetection = (id) => client.post(`/detections/${id}/explain`)
export const getDetectionExplanation = (id) => client.get(`/detections/${id}/explanation`)

export const DETECTION_VERDICTS = ['benign', 'known_attack', 'zero_day_suspect', 'data_integrity', 'uncertain']

// --- Vitals (Stage 4) ---
export const listVitals = (params) => client.get('/vitals', { params })
export const getVital = (id) => client.get(`/vitals/${id}`)
export const ingestVital = (body) => client.post('/vitals', body)

// Order matters: it's the order the Stage 4 LSTM was trained on
// (models/vitals_lstm_results.json -> vitals_order).
export const VITAL_FIELDS = [
  { key: 'heart_rate', label: 'Heart rate', unit: 'bpm', modelKey: 'Heart_rate' },
  { key: 'spo2', label: 'SpO₂', unit: '%', modelKey: 'SpO2' },
  { key: 'systolic_bp', label: 'Systolic BP', unit: 'mmHg', modelKey: 'SYS' },
  { key: 'diastolic_bp', label: 'Diastolic BP', unit: 'mmHg', modelKey: 'DIA' },
  { key: 'body_temp', label: 'Temperature', unit: '°C', modelKey: 'Temp' },
  { key: 'respiration_rate', label: 'Respiration', unit: '/min', modelKey: 'Resp_Rate' },
]

// --- Notifications ---
export const listNotifications = (params) => client.get('/notifications', { params })
export const retryNotification = (id) => client.post(`/notifications/${id}/retry`)
export const getLiveStatus = () => client.get('/notifications/live/status')

export const NOTIFICATION_CHANNELS = ['websocket', 'email', 'sms', 'telegram', 'webhook']

// --- Reports ---
export const listReports = (params) => client.get('/reports', { params })
export const getReport = (id) => client.get(`/reports/${id}`)
export const generateReport = (body) => client.post('/reports', body)
export const deleteReport = (id) => client.delete(`/reports/${id}`)

/**
 * Downloads a report as .xlsx.
 *
 * The endpoint needs the Authorization header, so a plain <a href> won't do —
 * the file comes back through axios as a blob and is handed to the browser via
 * a temporary object URL, which is revoked once the click has been dispatched.
 */
export const downloadReport = async (id) => {
  const response = await client.get(`/reports/${id}/export`, { responseType: 'blob' })

  const disposition = response.headers['content-disposition'] || ''
  const match = /filename="([^"]+)"/.exec(disposition)
  const filename = match ? match[1] : `report-${id}.xlsx`

  const url = URL.createObjectURL(response.data)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
  return filename
}

export const REPORT_TYPES = [
  'daily',
  'weekly',
  'patient',
  'device',
  'ward',
  'incident',
  'compliance',
  'custom',
]

// --- Attack simulator ---
export const startSimulation = (body) => client.post('/simulate', body)
export const stopSimulation = () => client.post('/simulate/stop')
export const getSimulationStatus = () => client.get('/simulate')

// --- Stats ---
export const getStatsOverview = () => client.get('/stats/overview')

// --- Alerts ---
export const listAlerts = (params) => client.get('/alerts', { params })
export const getAlert = (id) => client.get(`/alerts/${id}`)
export const acknowledgeAlert = (id) => client.post(`/alerts/${id}/acknowledge`)
export const assignAlert = (id, userId) => client.post(`/alerts/${id}/assign`, { user_id: userId })
export const resolveAlert = (id, notes) => client.post(`/alerts/${id}/resolve`, { notes })
export const markAlertFalsePositive = (id, notes) => client.post(`/alerts/${id}/false-positive`, { notes })
export const commentOnAlert = (id, comment) => client.post(`/alerts/${id}/comment`, { comment })
export const applyRecommendation = (alertId, recId, confirmLifeCritical = false) =>
  client.post(`/alerts/${alertId}/recommendations/${recId}/apply`, {
    confirm_life_critical: confirmLifeCritical,
  })

// Undo an applied mitigation — releases the device and lifts the blocks it
// raised. Available on resolved alerts too: the mistake is usually spotted
// after the ticket was closed.
export const revertRecommendation = (alertId, recId, reason) =>
  client.post(`/alerts/${alertId}/recommendations/${recId}/revert`, { reason })

// Action types that actually change device or network state when applied.
// Keep in sync with ENFORCING_ACTIONS in backend/services/alert_service.py.
export const ENFORCING_ACTIONS = ['isolate_source', 'block_ip', 'revoke_mqtt_client']

export const ALERT_STATUSES = ['new', 'acknowledged', 'investigating', 'resolved', 'false_positive']
export const ALERT_SEVERITIES = ['info', 'low', 'medium', 'high', 'critical']

// Roles are a small fixed reference set (see database/schema.sql -> roles).
// No dedicated /roles listing endpoint exists yet, so they're described here
// for the registration form; keep in sync with database/schema.sql seed data
// (see backend/seed.py) and the escalation guard in backend/services/auth_service.py:
// self-service registration only ever succeeds for 'viewer' — any other role
// requires an already-authenticated admin (or is a one-time bootstrap for the
// very first account in the system), otherwise the API returns 403.
export const REGISTERABLE_ROLES = [
  {
    value: 'viewer',
    label: 'Viewer',
    description: 'Read-only access to the dashboard.',
    restricted: false,
  },
  {
    value: 'security_analyst',
    label: 'Security Analyst',
    description: 'Investigates alerts, manages detections, responds to incidents.',
    restricted: true,
  },
  {
    value: 'clinician',
    label: 'Clinician',
    description: 'Views device & patient vitals, alerts affecting assigned patients.',
    restricted: true,
  },
  {
    value: 'admin',
    label: 'Administrator',
    description: 'Full system access — RBAC, model registry, retraining.',
    restricted: true,
  },
]
