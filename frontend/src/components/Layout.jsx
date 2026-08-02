import { NavLink, Outlet } from 'react-router-dom'

const NAV_ITEMS = [
  { to: '/', label: 'Overview', end: true },
  { to: '/live', label: 'Live Monitor' },
  { to: '/alerts', label: 'Alerts Console' },
  { to: '/devices', label: 'Devices' },
  { to: '/models', label: 'Models' },
  { to: '/reports', label: 'Reports' },
  { to: '/simulator', label: 'Attack Simulator' },
]

function NavItem({ to, label, end }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        `block rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
          isActive
            ? 'bg-sky-500/10 text-sky-300 ring-1 ring-inset ring-sky-500/30'
            : 'text-slate-400 hover:bg-white/5 hover:text-slate-200'
        }`
      }
    >
      {label}
    </NavLink>
  )
}

export default function Layout() {
  return (
    <div className="flex min-h-screen bg-[#0b0e14] text-slate-100">
      <aside className="hidden w-60 shrink-0 border-r border-white/10 bg-[#0d1017] p-4 md:block">
        <div className="mb-6 flex items-center gap-2 px-2">
          <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-sky-400 to-emerald-400" />
          <div>
            <p className="text-sm font-semibold leading-tight">IoMT IDS</p>
            <p className="text-[11px] leading-tight text-slate-500">Attack Detection</p>
          </div>
        </div>
        <nav className="space-y-1">
          {NAV_ITEMS.map((item) => (
            <NavItem key={item.to} {...item} />
          ))}
        </nav>
      </aside>

      <div className="flex min-h-screen flex-1 flex-col">
        <Topbar />
        <main className="flex-1 overflow-y-auto p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

function Topbar() {
  return (
    <header className="flex h-14 items-center justify-between border-b border-white/10 bg-[#0d1017]/80 px-4 backdrop-blur md:px-6">
      <p className="text-sm text-slate-400">IoMT network-edge intrusion detection</p>
      <div className="flex items-center gap-3">
        <span className="flex items-center gap-1.5 text-xs text-slate-400">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
          Live
        </span>
        <div className="h-7 w-7 rounded-full bg-slate-700" title="Signed-in user" />
      </div>
    </header>
  )
}
