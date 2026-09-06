import { Link, useLocation, useParams } from 'react-router-dom'
import { ChevronRightIcon } from './icons'

const LABELS = {
  profile: 'Profile',
  users: 'Users',
  devices: 'Devices',
  patients: 'Patients',
  blocklist: 'Blocklist',
  settings: 'Settings',
  'audit-logs': 'Audit Logs',
  models: 'Models',
  detections: 'Detections',
  alerts: 'Alerts',
  new: 'New',
}

const ENTITY_LABELS = {
  users: 'User',
  devices: 'Device',
  patients: 'Patient',
  models: 'Model',
  detections: 'Detection',
  alerts: 'Alert',
}

export default function Breadcrumb() {
  const location = useLocation()
  const params = useParams()
  const segments = location.pathname.split('/').filter(Boolean)

  const crumbs = [{ label: 'Dashboard', to: '/' }]
  let path = ''
  segments.forEach((segment, i) => {
    path += `/${segment}`
    const isLast = i === segments.length - 1
    const label =
      segment === params.id ? `${ENTITY_LABELS[segments[0]] || 'Item'} #${segment}` : LABELS[segment] || segment
    crumbs.push({ label, to: isLast ? null : path })
  })

  return (
    <nav className="flex items-center gap-1.5 text-sm">
      {crumbs.map((crumb, i) => (
        <span key={i} className="flex items-center gap-1.5">
          {i > 0 && <ChevronRightIcon className="h-3.5 w-3.5 text-slate-600" />}
          {crumb.to ? (
            <Link to={crumb.to} className="text-slate-500 transition-colors hover:text-slate-700">
              {crumb.label}
            </Link>
          ) : (
            <span className="font-medium capitalize text-slate-800">{crumb.label}</span>
          )}
        </span>
      ))}
    </nav>
  )
}
