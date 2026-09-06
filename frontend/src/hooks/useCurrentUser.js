import useApi from './useApi'
import { me } from '../api/client'

/**
 * Fetches the signed-in user (GET /auth/me) — used for the home-page welcome
 * banner and the topbar identity. Only meant to be used inside routes behind
 * RequireAuth, where an access token is guaranteed to exist.
 */
export default function useCurrentUser() {
  const { data, loading, error, reload } = useApi(me, [])
  return { user: data, loading, error, reload }
}
