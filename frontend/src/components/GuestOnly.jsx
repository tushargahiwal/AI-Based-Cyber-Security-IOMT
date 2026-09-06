import { Navigate } from 'react-router-dom'
import { getAccessToken } from '../api/tokens'

export default function GuestOnly({ children }) {
  const token = getAccessToken()

  if (token) {
    return <Navigate to="/" replace />
  }

  return children
}
