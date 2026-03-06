import { useEffect, useRef, useState } from 'react'

export function useLogFeed() {
  const [lines, setLines] = useState<string[]>([])
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const socket = new WebSocket(`${protocol}//${window.location.host}/api/ws/log`)
    wsRef.current = socket

    socket.onmessage = (e) => {
      const newLines: string[] = JSON.parse(e.data)
      setLines((prev) => [...prev, ...newLines].slice(-100))
    }

    socket.onerror = () => socket.close()

    return () => socket.close()
  }, [])

  return lines
}
