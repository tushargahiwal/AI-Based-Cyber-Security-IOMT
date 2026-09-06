import { extractErrorMessage } from '../api/errors'

export default function ErrorBanner({ error }) {
  if (!error) return null
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 px-3.5 py-2.5 text-sm text-amber-700">
      {extractErrorMessage(error, 'Something went wrong.')}
    </div>
  )
}
