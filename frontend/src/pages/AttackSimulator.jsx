import { useState } from 'react'
import useApi from '../hooks/useApi'
import { listDevices, launchAttack } from '../api/client'
import Card from '../components/Card'
import ErrorBanner from '../components/ErrorBanner'

const ATTACKS = [
  { code: 'DDOS_ICMP_FLOOD', label: 'DDoS — ICMP flood', family: 'DDoS' },
  { code: 'DOS_SYN_FLOOD', label: 'DoS — SYN flood', family: 'DoS' },
  { code: 'RECON_PORT_SCAN', label: 'Recon — Nmap port scan', family: 'Recon' },
  { code: 'MQTT_CONNECT_FLOOD', label: 'MQTT — CONNECT flood', family: 'MQTT' },
  { code: 'ARP_SPOOF', label: 'Spoofing — ARP spoof / MITM', family: 'Spoofing' },
  { code: 'DATA_INJECTION', label: 'Spoofing — vitals data injection', family: 'Spoofing' },
]

export default function AttackSimulator() {
  const devices = useApi(listDevices, [])
  const rows = devices.data?.items || devices.data || []
  const [deviceId, setDeviceId] = useState('')
  const [log, setLog] = useState([])
  const [busyCode, setBusyCode] = useState(null)

  const fire = async (attack) => {
    if (!deviceId) return
    setBusyCode(attack.code)
    const entry = { id: Date.now(), attack: attack.label, device: deviceId, status: 'launching' }
    setLog((l) => [entry, ...l])
    try {
      await launchAttack(deviceId, attack.code)
      updateEntry(entry.id, 'launched')
    } catch (err) {
      updateEntry(entry.id, err?.response?.status ? `failed (HTTP ${err.response.status})` : 'failed — simulator not reachable')
    } finally {
      setBusyCode(null)
    }
  }

  const updateEntry = (id, status) =>
    setLog((l) => l.map((e) => (e.id === id ? { ...e, status } : e)))

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-slate-100">Attack Simulator</h1>
        <p className="text-sm text-slate-500">
          Demo-only. Launches attacker scripts against your own isolated testbed — never point this at a network you
          do not own.
        </p>
      </div>

      <Card title="Target device">
        <ErrorBanner error={devices.error} label="device list" />
        <select
          value={deviceId}
          onChange={(e) => setDeviceId(e.target.value)}
          className="w-full max-w-sm rounded-lg border border-white/10 bg-[#0d1017] px-3 py-2 text-sm text-slate-200 focus:border-sky-500/50 focus:outline-none"
        >
          <option value="">Select a device…</option>
          {rows.map((d) => (
            <option key={d.id} value={d.id}>
              {d.device_uid}
            </option>
          ))}
        </select>
      </Card>

      <Card title="Attacks">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {ATTACKS.map((attack) => (
            <button
              key={attack.code}
              disabled={!deviceId || busyCode === attack.code}
              onClick={() => fire(attack)}
              className="rounded-xl border border-white/10 bg-white/[0.03] p-4 text-left transition-colors hover:bg-white/[0.06] disabled:cursor-not-allowed disabled:opacity-40"
            >
              <p className="text-xs uppercase tracking-wide text-slate-500">{attack.family}</p>
              <p className="mt-1 text-sm font-medium text-slate-200">
                {busyCode === attack.code ? 'Launching…' : attack.label}
              </p>
            </button>
          ))}
        </div>
        {!deviceId && <p className="mt-3 text-xs text-slate-500">Select a device above to enable attacks.</p>}
      </Card>

      <Card title="Launch log">
        {log.length === 0 ? (
          <p className="text-sm text-slate-500">No attacks launched this session.</p>
        ) : (
          <ul className="divide-y divide-white/5 text-sm">
            {log.map((entry) => (
              <li key={entry.id} className="flex items-center justify-between py-2">
                <span className="text-slate-300">
                  {entry.attack} → device {entry.device}
                </span>
                <span className={entry.status === 'launched' ? 'text-emerald-300' : entry.status === 'launching' ? 'text-slate-500' : 'text-amber-300'}>
                  {entry.status}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
