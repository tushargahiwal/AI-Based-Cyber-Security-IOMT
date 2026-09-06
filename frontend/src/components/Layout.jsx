import { useEffect, useMemo, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { clearTokens } from '../api/tokens'
import useCurrentUser from '../hooks/useCurrentUser'
import { logout as logoutApi } from '../api/client'
import {
  ActivityIcon,
  AlertTriangleIcon,
  BanIcon,
  BellIcon,
  ChevronDownIcon,
  CpuIcon,
  FileTextIcon,
  FlaskIcon,
  GearIcon,
  GridIcon,
  HeartPulseIcon,
  HistoryIcon,
  LogoutIcon,
  MonitorIcon,
  NetworkIcon,
  RadarIcon,
  UserIcon,
  UserCheckIcon,
} from './icons'
import Breadcrumb from './Breadcrumb'

function hasPermission(user, permission) {
  const perms = user?.permissions || []
  return perms.includes('*') || perms.includes(permission)
}

/**
 * The navigation, grouped the way the work is grouped rather than as one flat
 * list of eighteen links. Each section answers a different question — what is
 * happening right now, what is on the network, what do I need to write up — so
 * an admin can find a page by reasoning about it instead of scanning.
 *
 * `permission` gates an item; a section with nothing visible is not rendered.
 */
const SECTIONS = [
  {
    title: 'Monitoring',
    items: [
      { to: '/', label: 'Dashboard', icon: GridIcon, end: true },
      { to: '/live', label: 'Live Monitor', icon: RadarIcon, permission: 'devices.read' },
      { to: '/alerts', label: 'Alerts', icon: AlertTriangleIcon, permission: 'alerts.read' },
      { to: '/detections', label: 'Detections', icon: ActivityIcon, permission: 'devices.read' },
      { to: '/notifications', label: 'Notifications', icon: BellIcon, permission: 'alerts.read' },
    ],
  },
  {
    title: 'Estate',
    items: [
      { to: '/devices', label: 'Devices', icon: MonitorIcon, permission: 'devices.read' },
      { to: '/patients', label: 'Patients', icon: HeartPulseIcon, permission: 'patients.read' },
      { to: '/blocklist', label: 'Blocklist', icon: BanIcon, permission: 'devices.read' },
    ],
  },
  {
    title: 'Reports',
    items: [
      {
        to: '/reports',
        label: 'Reports',
        icon: FileTextIcon,
        permission: 'reports.read',
        end: true,
        children: [
          { to: '/reports', label: 'All reports', end: true },
          { to: '/reports/patients', label: 'Patient reports' },
          { to: '/reports/devices', label: 'Device reports' },
          { to: '/reports/wards', label: 'Ward reports' },
          { to: '/reports/schedule', label: 'Daily & weekly' },
        ],
      },
    ],
  },
  {
    title: 'Machine learning',
    items: [
      { to: '/models', label: 'Models', icon: CpuIcon, permission: 'models.read' },
      { to: '/simulator', label: 'Attack Simulator', icon: FlaskIcon, permission: 'models.retrain' },
    ],
  },
  {
    title: 'Administration',
    items: [
      { to: '/users', label: 'Users', icon: UserCheckIcon, permission: 'users.manage' },
      { to: '/audit-logs', label: 'Audit Logs', icon: HistoryIcon, permission: 'users.manage' },
      { to: '/settings', label: 'Settings', icon: GearIcon, permission: 'system_config.write' },
    ],
  },
]

function visibleSections(user) {
  return SECTIONS.map((section) => ({
    ...section,
    items: section.items.filter((item) => !item.permission || hasPermission(user, item.permission)),
  })).filter((section) => section.items.length > 0)
}

const linkClass = (isActive) =>
  `flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors ${
    isActive
      ? 'bg-sky-500/15 font-medium text-sky-300'
      : 'text-slate-300 hover:bg-white/[0.06] hover:text-white'
  }`

function NavGroup({ item, onNavigate }) {
  const { pathname } = useLocation()
  const Icon = item.icon
  const inSection = pathname === item.to || pathname.startsWith(`${item.to}/`)
  // Opens itself when you are already somewhere inside it, so the current page
  // is never hidden behind a collapsed parent after a reload.
  const [open, setOpen] = useState(inSection)
  useEffect(() => {
    if (inSection) setOpen(true)
  }, [inSection])

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors ${
          inSection ? 'text-white' : 'text-slate-300 hover:bg-white/[0.06] hover:text-white'
        }`}
      >
        {Icon && <Icon className="h-4 w-4 shrink-0 opacity-80" />}
        <span className="flex-1 text-left">{item.label}</span>
        <ChevronDownIcon className={`h-3.5 w-3.5 opacity-60 transition-transform ${open ? '' : '-rotate-90'}`} />
      </button>

      {open && (
        <div className="mt-0.5 ml-[1.4rem] space-y-0.5 border-l border-white/10 pl-3">
          {item.children.map((child) => (
            <NavLink
              key={child.to}
              to={child.to}
              end={child.end}
              onClick={onNavigate}
              className={({ isActive }) =>
                `block rounded-md px-2.5 py-1.5 text-[13px] transition-colors ${
                  isActive
                    ? 'bg-sky-500/15 font-medium text-sky-300'
                    : 'text-slate-400 hover:bg-white/[0.06] hover:text-slate-100'
                }`
              }
            >
              {child.label}
            </NavLink>
          ))}
        </div>
      )}
    </div>
  )
}

function SidebarNav({ user, onNavigate }) {
  const sections = useMemo(() => visibleSections(user), [user])

  return (
    <nav className="space-y-5">
      {sections.map((section) => (
        <div key={section.title}>
          <p className="px-3 pb-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
            {section.title}
          </p>
          <div className="space-y-0.5">
            {section.items.map((item) =>
              item.children ? (
                <NavGroup key={item.to} item={item} onNavigate={onNavigate} />
              ) : (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  onClick={onNavigate}
                  className={({ isActive }) => linkClass(isActive)}
                >
                  {item.icon && <item.icon className="h-4 w-4 shrink-0 opacity-80" />}
                  {item.label}
                </NavLink>
              ),
            )}
          </div>
        </div>
      ))}
    </nav>
  )
}

function Brand() {
  return (
    <div className="flex items-center gap-2.5 px-2">
      <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-sky-400 to-emerald-400">
        <NetworkIcon className="h-5 w-5 text-slate-900" />
      </div>
      <div>
        <p className="text-sm font-semibold leading-tight text-white">IoMT IDS</p>
        <p className="text-[11px] leading-tight text-slate-400">Attack Detection</p>
      </div>
    </div>
  )
}

export default function Layout() {
  const { user } = useCurrentUser()
  const { pathname } = useLocation()
  const [mobileOpen, setMobileOpen] = useState(false)

  // A route change with the drawer still open would leave it covering the page
  // the user just asked for.
  useEffect(() => setMobileOpen(false), [pathname])

  return (
    <div className="flex min-h-screen bg-[var(--app-bg)] text-slate-900">
      <aside className="sidebar-scroll hidden w-64 shrink-0 flex-col overflow-y-auto bg-[var(--sidebar-bg)] p-4 md:flex">
        <Brand />
        <div className="mt-6 flex-1">
          <SidebarNav user={user} />
        </div>
        <p className="px-3 pt-6 text-[10px] leading-relaxed text-slate-600">
          Five-stage detection pipeline
          <br />
          WUSTL-EHMS-2020
        </p>
      </aside>

      {mobileOpen && (
        <>
          <div
            className="fixed inset-0 z-30 bg-slate-900/40 md:hidden"
            onClick={() => setMobileOpen(false)}
            aria-hidden
          />
          <aside className="sidebar-scroll fixed inset-y-0 left-0 z-40 w-64 overflow-y-auto bg-[var(--sidebar-bg)] p-4 md:hidden">
            <Brand />
            <div className="mt-6">
              <SidebarNav user={user} onNavigate={() => setMobileOpen(false)} />
            </div>
          </aside>
        </>
      )}

      <div className="flex min-h-screen flex-1 flex-col">
        <Topbar user={user} onMenu={() => setMobileOpen(true)} />
        <main className="flex-1 overflow-y-auto p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

function Topbar({ user, onMenu }) {
  const name = user?.full_name || user?.username

  return (
    <header className="sticky top-0 z-20 flex h-14 items-center justify-between gap-3 border-b border-slate-200 bg-white/85 px-4 backdrop-blur md:px-6">
      <div className="flex min-w-0 items-center gap-3">
        <button
          type="button"
          onClick={onMenu}
          aria-label="Open navigation"
          className="-ml-1 rounded-lg p-2 text-slate-600 hover:bg-slate-100 md:hidden"
        >
          <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8">
            <path d="M4 7h16M4 12h16M4 17h16" strokeLinecap="round" />
          </svg>
        </button>
        <Breadcrumb />
      </div>
      <div className="flex items-center gap-3">
        <span className="hidden items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-xs text-emerald-700 ring-1 ring-inset ring-emerald-200 sm:flex">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
          Live
        </span>
        <UserMenu name={name} role={user?.role} />
      </div>
    </header>
  )
}

function UserMenu({ name, role }) {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const menuRef = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    const onPointerDown = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) setOpen(false)
    }
    const onKeyDown = (e) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  const handleLogout = async () => {
    setOpen(false)
    try {
      await logoutApi()
    } catch {
      // best-effort — clear the local session regardless of the API outcome
    } finally {
      clearTokens()
      navigate('/login', { replace: true })
    }
  }

  return (
    <div className="relative" ref={menuRef}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 rounded-lg py-1 pl-1 pr-2 transition-colors hover:bg-slate-100"
      >
        <div
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-800 text-xs font-medium text-white"
          title={name || 'Signed-in user'}
        >
          {initials(name)}
        </div>
        <span className="hidden text-left sm:block">
          {name && <span className="block text-sm leading-tight text-slate-800">{name}</span>}
          {role && <span className="block text-[11px] capitalize leading-tight text-slate-500">{role.replace(/_/g, ' ')}</span>}
        </span>
        <ChevronDownIcon className={`h-3.5 w-3.5 text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="absolute right-0 top-full z-30 mt-2 w-48 overflow-hidden rounded-lg border border-slate-200 bg-white py-1 shadow-[0_18px_40px_-18px_rgba(15,23,42,0.35)]">
          <NavLink
            to="/profile"
            onClick={() => setOpen(false)}
            className={({ isActive }) =>
              `flex items-center gap-2 px-3 py-2 text-sm transition-colors ${
                isActive ? 'text-sky-700' : 'text-slate-700 hover:bg-slate-100 hover:text-slate-900'
              }`
            }
          >
            <UserIcon className="h-4 w-4" />
            Profile
          </NavLink>
          <button
            type="button"
            onClick={handleLogout}
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-red-700 transition-colors hover:bg-red-50"
          >
            <LogoutIcon className="h-4 w-4" />
            Sign out
          </button>
        </div>
      )}
    </div>
  )
}

function initials(name) {
  if (!name) return ''
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join('')
}
