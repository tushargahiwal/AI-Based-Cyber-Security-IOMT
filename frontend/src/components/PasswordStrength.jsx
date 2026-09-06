const LEVELS = [
  { label: 'Very weak', color: 'bg-red-500' },
  { label: 'Weak', color: 'bg-orange-500' },
  { label: 'Okay', color: 'bg-yellow-500' },
  { label: 'Strong', color: 'bg-emerald-500' },
  { label: 'Very strong', color: 'bg-emerald-400' },
]

export function scorePassword(pw) {
  if (!pw) return 0
  let score = 0
  if (pw.length >= 8) score++
  if (pw.length >= 12) score++
  if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) score++
  if (/\d/.test(pw)) score++
  if (/[^a-zA-Z0-9]/.test(pw)) score++
  return Math.min(score, 4)
}

export default function PasswordStrength({ password }) {
  if (!password) return null
  const score = scorePassword(password)
  const level = LEVELS[score]

  return (
    <div className="mt-2">
      <div className="flex gap-1">
        {[0, 1, 2, 3].map((i) => (
          <div
            key={i}
            className={`h-1 flex-1 rounded-full transition-colors ${i <= score ? level.color : 'bg-slate-200'}`}
          />
        ))}
      </div>
      <p className="mt-1 text-[11px] text-slate-500">{level.label}</p>
    </div>
  )
}
