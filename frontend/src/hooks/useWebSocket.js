import { useEffect, useRef, useState, useCallback } from 'react'

function resolveWsUrl(path) {
  const explicit = import.meta.env.VITE_WS_BASE_URL
  if (explicit) return `${explicit}${path}`
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}${path}`
}

/**
 * Subscribes to a backend WebSocket feed (e.g. /ws/alerts, /ws/traffic) and
 * keeps a rolling buffer of the most recent messages, with auto-reconnect.
 */
export default function useWebSocket(path, { maxItems = 200, enabled = true } = {}) {
  const [messages, setMessages] = useState([])
  const [status, setStatus] = useState('connecting')
  const socketRef = useRef(null)
  const retryRef = useRef(0)
  const timerRef = useRef(null)

  const clear = useCallback(() => setMessages([]), [])

  useEffect(() => {
    if (!enabled) return undefined
    let cancelled = false

    const connect = () => {
      const token = localStorage.getItem('access_token')
      const url = resolveWsUrl(path) + (token ? `?token=${token}` : '')
      const socket = new WebSocket(url)
      socketRef.current = socket
      setStatus('connecting')

      socket.onopen = () => {
        if (cancelled) return
        retryRef.current = 0
        setStatus('open')
      }

      socket.onmessage = (event) => {
        if (cancelled) return
        try {
          const data = JSON.parse(event.data)
          setMessages((prev) => [data, ...prev].slice(0, maxItems))
        } catch {
          // ignore malformed frames
        }
      }

      socket.onclose = () => {
        if (cancelled) return
        setStatus('closed')
        const delay = Math.min(1000 * 2 ** retryRef.current, 15000)
        retryRef.current += 1
        timerRef.current = setTimeout(connect, delay)
      }

      socket.onerror = () => {
        socket.close()
      }
    }

    connect()

    return () => {
      cancelled = true
      clearTimeout(timerRef.current)
      socketRef.current?.close()
    }
  }, [path, enabled, maxItems])

  return { messages, status, clear }
}
