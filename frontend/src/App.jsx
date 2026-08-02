import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import RequireAuth from './components/RequireAuth'
import Login from './pages/Login'
import Overview from './pages/Overview'
import LiveMonitor from './pages/LiveMonitor'
import Alerts from './pages/Alerts'
import Devices from './pages/Devices'
import DeviceDetail from './pages/DeviceDetail'
import Models from './pages/Models'
import Reports from './pages/Reports'
import AttackSimulator from './pages/AttackSimulator'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          element={
            <RequireAuth>
              <Layout />
            </RequireAuth>
          }
        >
          <Route index element={<Overview />} />
          <Route path="live" element={<LiveMonitor />} />
          <Route path="alerts" element={<Alerts />} />
          <Route path="devices" element={<Devices />} />
          <Route path="devices/:id" element={<DeviceDetail />} />
          <Route path="models" element={<Models />} />
          <Route path="reports" element={<Reports />} />
          <Route path="simulator" element={<AttackSimulator />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
