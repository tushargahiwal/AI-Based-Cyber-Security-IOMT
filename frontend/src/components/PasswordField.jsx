import { useState } from 'react'
import { LockIcon, EyeIcon, EyeOffIcon } from './icons'

export default function PasswordField({ label, error, hint, value, onChange, ...inputProps }) {
  const [visible, setVisible] = useState(false)

  return (
    <label className="block">
      {label && <span className="mb-1.5 block text-sm font-medium text-slate-700">{label}</span>}
      <div className="relative">
        <LockIcon className="pointer-events-none absolute left-3.5 top-1/2 h-[18px] w-[18px] -translate-y-1/2 text-slate-500" />
        <input
          {...inputProps}
          type={visible ? 'text' : 'password'}
          value={value}
          onChange={onChange}
          className={`w-full rounded-lg border bg-white py-2.5 pl-10 pr-11 text-[15px] text-slate-900 placeholder:text-slate-600 transition-colors focus:outline-none focus:ring-2 ${
            error
              ? 'border-red-300 focus:border-red-500/50 focus:ring-red-500/20'
              : 'border-slate-200 focus:border-sky-500/50 focus:ring-sky-500/20'
          }`}
        />
        <button
          type="button"
          tabIndex={-1}
          onClick={() => setVisible((v) => !v)}
          className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-700"
          aria-label={visible ? 'Hide password' : 'Show password'}
        >
          {visible ? <EyeOffIcon className="h-[18px] w-[18px]" /> : <EyeIcon className="h-[18px] w-[18px]" />}
        </button>
      </div>
      {error ? (
        <p className="mt-1.5 text-xs text-red-600">{error}</p>
      ) : hint ? (
        <p className="mt-1.5 text-xs text-slate-500">{hint}</p>
      ) : null}
    </label>
  )
}
