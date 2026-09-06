import { useCallback, useEffect, useRef, useState } from 'react'
import { getAccessToken } from '../api/tokens'

// Vite proxies /api in dev; in production the socket lives on the same origin.
function socketUrl(token) {
  const base = import.meta.env.VITE_WS_URL
  if (base) return `${base}?token=${encodeURIComponent(token)}`
  const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${scheme}://${window.location.host}/api/v1/ws?token=${encodeURIComponent(token)}`
}

const RECONNECT_MS = 3000

/**
 * Subscribes to the live detection/alert feed.
 *
 * The server sends `{type, data}` frames and never replays history, so this
 * keeps only the most recent `limit` events — the live view is a tail, and the
 * full record is always available over REST.
 */
export default function useWebSocket({ enabled = true, limit = 100 } = {}) {
  const [events, setEvents] = useState([])
  const [status, setStatus] = useState('idle')
  const socketRef = useRef(null)
  const retryRef = useRef(null)
  // Kept in a ref so an unmount can stop the reconnect loop without the effect
  // depending on state that changes on every message.
  const closedRef = useRef(false)

  const clear = useCallback(() => setEvents([]), [])

  useEffect(() => {
    if (!enabled) {
      setStatus('idle')
      return undefined
    }
    const token = getAccessToken()
    if (!token) {
      setStatus('unauthenticated')
      return undefined
    }

    closedRef.current = false

    const connect = () => {
      if (closedRef.current) return
      setStatus('connecting')
      const ws = new WebSocket(socketUrl(token))
      socketRef.current = ws

      ws.onopen = () => setStatus('connected')
      ws.onmessage = (e) => {
        let parsed
        try {
          parsed = JSON.parse(e.data)
        } catch {
          return // a frame we can't read is not worth tearing the feed down for
        }
        setEvents((prev) => [{ ...parsed, receivedAt: Date.now() }, ...prev].slice(0, limit))
      }
      ws.onerror = () => setStatus('error')
      ws.onclose = () => {
        socketRef.current = null
        if (closedRef.current) return
        setStatus('reconnecting')
        retryRef.current = setTimeout(connect, RECONNECT_MS)
      }
    }

    connect()

    return () => {
      closedRef.current = true
      clearTimeout(retryRef.current)
      socketRef.current?.close()
      socketRef.current = null
    }
  }, [enabled, limit])

  return { events, status, clear }
}
