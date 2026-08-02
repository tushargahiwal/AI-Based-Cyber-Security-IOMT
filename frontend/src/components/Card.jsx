export default function Card({ title, action, children, className = '' }) {
  return (
    <section className={`rounded-xl border border-white/10 bg-white/[0.03] ${className}`}>
      {(title || action) && (
        <header className="flex items-center justify-between border-b border-white/10 px-4 py-3">
          {title && <h2 className="text-sm font-semibold text-slate-200">{title}</h2>}
          {action}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  )
}
