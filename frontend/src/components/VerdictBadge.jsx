const VERDICT_STYLES = {
  benign: 'bg-emerald-500/15 text-emerald-300 ring-emerald-500/30',
  malicious: 'bg-red-500/15 text-red-300 ring-red-500/30',
  known_attack: 'bg-red-500/15 text-red-300 ring-red-500/30',
  zero_day_suspect: 'bg-purple-500/15 text-purple-300 ring-purple-500/30',
  data_integrity: 'bg-rose-500/15 text-rose-300 ring-rose-500/30',
  uncertain: 'bg-slate-500/15 text-slate-300 ring-slate-500/30',
}

const LABELS = {
  known_attack: 'Known Attack',
  zero_day_suspect: 'Zero-Day Suspect',
  data_integrity: 'Data Integrity',
  benign: 'Benign',
  malicious: 'Malicious',
  uncertain: 'Uncertain',
}

export default function VerdictBadge({ verdict }) {
  const style = VERDICT_STYLES[verdict] || VERDICT_STYLES.uncertain
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${style}`}>
      {LABELS[verdict] || verdict}
    </span>
  )
}
