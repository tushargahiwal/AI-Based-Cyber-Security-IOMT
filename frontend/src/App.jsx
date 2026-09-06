import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import RequireAuth from './components/RequireAuth'
import GuestOnly from './components/GuestOnly'
import Login from './pages/Login'
import Register from './pages/Register'
import Overview from './pages/Overview'
import Profile from './pages/Profile'
import Users from './pages/Users'
import CreateUser from './pages/CreateUser'
import UserDetail from './pages/UserDetail'
import Devices from './pages/Devices'
import CreateDevice from './pages/CreateDevice'
import DeviceDetail from './pages/DeviceDetail'
import Patients from './pages/Patients'
import CreatePatient from './pages/CreatePatient'
import PatientDetail from './pages/PatientDetail'
import Settings from './pages/Settings'
import Blocklist from './pages/Blocklist'
import AuditLogs from './pages/AuditLogs'
import Models from './pages/Models'
import RegisterModel from './pages/RegisterModel'
import ModelDetail from './pages/ModelDetail'
import Detections from './pages/Detections'
import DetectionDetail from './pages/DetectionDetail'
import Alerts from './pages/Alerts'
import AlertDetail from './pages/AlertDetail'
import LiveMonitor from './pages/LiveMonitor'
import AttackSimulator from './pages/AttackSimulator'
import Reports from './pages/Reports'
import Notifications from './pages/Notifications'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/login"
          element={
            <GuestOnly>
              <Login />
            </GuestOnly>
          }
        />
        <Route
          path="/register"
          element={
            <GuestOnly>
              <Register />
            </GuestOnly>
          }
        />
        <Route
          element={
            <RequireAuth>
              <Layout />
            </RequireAuth>
          }
        >
          <Route index element={<Overview />} />
          <Route path="profile" element={<Profile />} />
          <Route path="users" element={<Users />} />
          <Route path="users/new" element={<CreateUser />} />
          <Route path="users/:id" element={<UserDetail />} />
          <Route path="devices" element={<Devices />} />
          <Route path="devices/new" element={<CreateDevice />} />
          <Route path="devices/:id" element={<DeviceDetail />} />
          <Route path="patients" element={<Patients />} />
          <Route path="patients/new" element={<CreatePatient />} />
          <Route path="patients/:id" element={<PatientDetail />} />
          <Route path="blocklist" element={<Blocklist />} />
          <Route path="settings" element={<Settings />} />
          <Route path="audit-logs" element={<AuditLogs />} />
          <Route path="models" element={<Models />} />
          <Route path="models/new" element={<RegisterModel />} />
          <Route path="models/:id" element={<ModelDetail />} />
          <Route path="detections" element={<Detections />} />
          <Route path="detections/:id" element={<DetectionDetail />} />
          <Route path="alerts" element={<Alerts />} />
          <Route path="alerts/:id" element={<AlertDetail />} />
          <Route path="live" element={<LiveMonitor />} />
          <Route path="simulator" element={<AttackSimulator />} />
          <Route path="reports" element={<Reports />} />
          {/* Sub-sections of the same page: the scope segment presets both the
              list filter and the generator, so each sidebar entry lands on
              exactly the reports it names. */}
          <Route path="reports/:scope" element={<Reports />} />
          <Route path="notifications" element={<Notifications />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
