const SEVERITY_STYLES = {
  info: 'bg-slate-500/15 text-slate-300 ring-slate-500/30',
  low: 'bg-emerald-500/15 text-emerald-300 ring-emerald-500/30',
  medium: 'bg-yellow-500/15 text-yellow-300 ring-yellow-500/30',
  high: 'bg-orange-500/15 text-orange-300 ring-orange-500/30',
  critical: 'bg-red-500/15 text-red-300 ring-red-500/30',
}

export default function SeverityBadge({ severity }) {
  const style = SEVERITY_STYLES[severity] || SEVERITY_STYLES.info
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${style}`}>
      {severity}
    </span>
  )
}
