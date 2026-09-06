import { Navigate, useLocation } from 'react-router-dom'
import { getAccessToken } from '../api/tokens'

export default function RequireAuth({ children }) {
  const location = useLocation()
  const token = getAccessToken()

  if (!token) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return children
}
