/**
 * Turns an axios error from the FastAPI backend into a single user-facing
 * string. The backend's error shape (see backend/dependencies.py,
 * services/auth_service.py) is either:
 *   - { detail: "plain message" }                    for HTTPException(status, "msg")
 *   - { detail: [{ msg, loc, type }, ...] }           for Pydantic 422 validation errors
 */
export function extractErrorMessage(err, fallback = 'Something went wrong.') {
  const status = err?.response?.status
  const detail = err?.response?.data?.detail

  if (!status) return 'Could not reach the backend. Is the API running?'

  if (typeof detail === 'string' && detail.trim()) return detail

  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0]
    const field = Array.isArray(first?.loc) ? first.loc.at(-1) : null
    return field ? `${field}: ${first.msg}` : first.msg || fallback
  }

  return fallback
}

export function errorStatus(err) {
  return err?.response?.status
}
