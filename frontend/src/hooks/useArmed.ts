import { useEffect, useState } from 'react'

export const ARMED_MS = 4000

/**
 * Two-click confirm without dialogs: arm(key) on the first click, act when armed === key on the
 * second. Disarms by itself after `ms`.
 */
export function useArmed<K>(ms: number = ARMED_MS): [K | null, (key: K | null) => void] {
  const [armed, setArmed] = useState<K | null>(null)

  useEffect(() => {
    if (armed === null) return
    const timer = window.setTimeout(() => setArmed(null), ms)
    return () => window.clearTimeout(timer)
  }, [armed, ms])

  return [armed, setArmed]
}
