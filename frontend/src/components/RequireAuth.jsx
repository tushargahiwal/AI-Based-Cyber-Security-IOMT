import { Navigate, useLocation } from 'react-router-dom'

export default function RequireAuth({ children }) {
  const location = useLocation()
  const token = localStorage.getItem('access_token')

  if (!token) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return children
}
