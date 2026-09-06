const FEATURES = [
  {
    title: 'Five-stage detection pipeline',
    body: 'Binary gate → attack classifier → zero-day autoencoder → physiological plausibility → SHAP explainer.',
  },
  {
    title: 'Physiological plausibility',
    body: 'Cross-checks vitals against an LSTM forecast so injected or altered readings never reach a clinician unflagged.',
  },
  {
    title: 'Explainable by default',
    body: 'Every alert ships with the top SHAP features that drove the verdict — never a black box.',
  },
]

export default function AuthLayout({
  eyebrow,
  title,
  subtitle,
  children,
  footer,
  showBranding = true,
  showLogo = true,
  maxWidth = 'max-w-md',
}) {
  return (
    <div className="relative flex min-h-screen overflow-hidden bg-[#f4f6fb] text-slate-900">
      <BackgroundGlow />

      {/* Branding panel */}
      {showBranding && (
        <aside className="relative hidden w-[46%] flex-col justify-between overflow-hidden border-r border-slate-200 bg-slate-900/[0.03] p-10 lg:flex">
          <div className="relative z-10">
            <div className="flex items-center gap-2.5">
              <div className="h-9 w-9 rounded-lg bg-gradient-to-br from-sky-400 to-emerald-400 shadow-[0_0_24px_rgba(56,189,248,0.35)]" />
              <div>
                <p className="text-sm font-semibold leading-tight">IoMT IDS</p>
                <p className="text-[11px] leading-tight text-slate-500">Attack Detection Console</p>
              </div>
            </div>

            <h1 className="mt-16 max-w-md text-3xl font-semibold leading-tight text-slate-900">
              Explainable, real-time
              <br />
              intrusion detection for
              <br />
              <span className="bg-gradient-to-r from-sky-600 to-emerald-600 bg-clip-text text-transparent">
                medical device networks
              </span>
            </h1>
            <p className="mt-4 max-w-sm text-sm text-slate-600">
              Network telemetry and patient vitals, fused into one hybrid AI pipeline — built for hospitals where
              availability outranks confidentiality.
            </p>
          </div>

          <ul className="relative z-10 space-y-5">
            {FEATURES.map((f) => (
              <li key={f.title} className="flex gap-3">
                <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-sky-400" />
                <div>
                  <p className="text-sm font-medium text-slate-800">{f.title}</p>
                  <p className="text-xs text-slate-500">{f.body}</p>
                </div>
              </li>
            ))}
          </ul>

          <p className="relative z-10 text-xs text-slate-600">
            Safety rule: this system never auto-disconnects a life-critical device. Alert &amp; recommend only.
          </p>
        </aside>
      )}

      {/* Form panel */}
      <main className="relative z-10 flex flex-1 items-center justify-center px-4 py-10 sm:px-8">
        <div className={`w-full ${maxWidth}`}>
          {showLogo && (
            <div className={`mb-6 flex items-center gap-2.5 ${showBranding ? 'lg:hidden' : ''}`}>
              <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-sky-400 to-emerald-400" />
              <div>
                <p className="text-sm font-semibold leading-tight">IoMT IDS</p>
                <p className="text-[11px] leading-tight text-slate-500">Attack Detection Console</p>
              </div>
            </div>
          )}

          <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-[0_18px_50px_-24px_rgba(15,23,42,0.25)] backdrop-blur sm:p-10">
            {title ? (
              <>
                {eyebrow && (
                  <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-sky-600">{eyebrow}</p>
                )}
                <h2 className="text-2xl font-semibold tracking-tight text-slate-900">{title}</h2>
              </>
            ) : (
              eyebrow && <h2 className="text-2xl font-semibold tracking-tight text-slate-900">{eyebrow}</h2>
            )}
            {subtitle && <p className="mt-2 text-sm leading-relaxed text-slate-600">{subtitle}</p>}

            <div className="mt-7">{children}</div>
          </div>

          {footer && <div className="mt-6 text-center text-sm text-slate-600">{footer}</div>}
        </div>
      </main>
    </div>
  )
}

function BackgroundGlow() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden">
      <div className="absolute -left-40 -top-40 h-96 w-96 rounded-full bg-sky-50 blur-[120px]" />
      <div className="absolute bottom-0 right-0 h-[28rem] w-[28rem] rounded-full bg-emerald-50 blur-[140px]" />
      <div
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage:
            'linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px)',
          backgroundSize: '48px 48px',
        }}
      />
    </div>
  )
}
