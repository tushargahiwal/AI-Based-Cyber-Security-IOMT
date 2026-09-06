import { useState } from 'react'
import Card from '../components/Card'
import AttackTypesPanel from './settings/AttackTypesPanel'
import ProtocolsPanel from './settings/ProtocolsPanel'
import SystemConfigPanel from './settings/SystemConfigPanel'
import ThresholdsPanel from './settings/ThresholdsPanel'
import DatasetsPanel from './settings/DatasetsPanel'
import { AlertTriangleIcon, NetworkIcon, KeyIcon, SlidersIcon, DatabaseIcon } from '../components/icons'

const TABS = [
  { key: 'attack-types', label: 'Attack Types', icon: AlertTriangleIcon, Panel: AttackTypesPanel },
  { key: 'protocols', label: 'Protocols', icon: NetworkIcon, Panel: ProtocolsPanel },
  { key: 'system-config', label: 'System Config', icon: KeyIcon, Panel: SystemConfigPanel },
  { key: 'thresholds', label: 'Thresholds', icon: SlidersIcon, Panel: ThresholdsPanel },
  { key: 'datasets', label: 'Datasets', icon: DatabaseIcon, Panel: DatasetsPanel },
]

export default function Settings() {
  const [active, setActive] = useState(TABS[0].key)
  const ActivePanel = TABS.find((t) => t.key === active).Panel

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-2">
        {TABS.map((tab) => {
          const Icon = tab.icon
          const isActive = tab.key === active
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActive(tab.key)}
              className={`flex items-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-sky-50 text-sky-700 ring-1 ring-inset ring-sky-200'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-800'
              }`}
            >
              <Icon className="h-4 w-4" />
              {tab.label}
            </button>
          )
        })}
      </div>

      <Card>
        <ActivePanel />
      </Card>
    </div>
  )
}
