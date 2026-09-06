import { ChevronDownIcon } from './icons'

export default function SelectField({ label, icon: Icon, error, hint, className = '', children, ...selectProps }) {
  return (
    <label className="block">
      {label && <span className="mb-1.5 block text-sm font-medium text-slate-700">{label}</span>}
      <div className="relative">
        {Icon && (
          <Icon className="pointer-events-none absolute left-3.5 top-1/2 h-[18px] w-[18px] -translate-y-1/2 text-slate-500" />
        )}
        <select
          {...selectProps}
          className={`w-full appearance-none rounded-lg border bg-white py-2.5 text-[15px] text-slate-900 transition-colors focus:outline-none focus:ring-2 ${
            Icon ? 'pl-10' : 'pl-3.5'
          } pr-10 ${
            error
              ? 'border-red-300 focus:border-red-500/50 focus:ring-red-500/20'
              : 'border-slate-200 focus:border-sky-500/50 focus:ring-sky-500/20'
          } ${className}`}
        >
          {children}
        </select>
        <ChevronDownIcon className="pointer-events-none absolute right-3.5 top-1/2 h-[18px] w-[18px] -translate-y-1/2 text-slate-500" />
      </div>
      {error ? (
        <p className="mt-1.5 text-xs text-red-600">{error}</p>
      ) : hint ? (
        <p className="mt-1.5 text-xs text-slate-500">{hint}</p>
      ) : null}
    </label>
  )
}
