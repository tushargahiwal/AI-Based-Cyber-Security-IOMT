export default function ErrorBanner({ error, label = 'endpoint' }) {
  if (!error) return null
  const status = error?.response?.status
  return (
    <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
      Could not reach the {label}
      {status ? ` (HTTP ${status})` : ''}. The backend route may not be wired up yet.
    </div>
  )
}
