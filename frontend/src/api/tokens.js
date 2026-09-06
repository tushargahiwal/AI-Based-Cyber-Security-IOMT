/**
 * Where the signed-in session lives.
 *
 * "Keep me signed in" is the difference between localStorage (survives closing
 * the browser) and sessionStorage (gone with the tab). On a shared clinical
 * workstation that distinction matters, so it is a real choice rather than a
 * decorative checkbox — which is what it used to be.
 *
 * Reads check sessionStorage first: if a session-only login is active in this
 * tab, it must win over a stale persistent token left by someone else.
 */

const ACCESS = 'access_token'
const REFRESH = 'refresh_token'

export function getAccessToken() {
  return sessionStorage.getItem(ACCESS) || localStorage.getItem(ACCESS)
}

export function getRefreshToken() {
  return sessionStorage.getItem(REFRESH) || localStorage.getItem(REFRESH)
}

export function saveTokens({ access, refresh, persistent }) {
  // Clear both first so switching modes can't leave a token behind in the other.
  clearTokens()
  const store = persistent ? localStorage : sessionStorage
  store.setItem(ACCESS, access)
  if (refresh) store.setItem(REFRESH, refresh)
}

/** Replaces the access token after a refresh, in whichever store holds the session. */
export function updateAccessToken(access) {
  const store = sessionStorage.getItem(ACCESS) !== null ? sessionStorage : localStorage
  store.setItem(ACCESS, access)
}

export function clearTokens() {
  for (const store of [localStorage, sessionStorage]) {
    store.removeItem(ACCESS)
    store.removeItem(REFRESH)
  }
}
