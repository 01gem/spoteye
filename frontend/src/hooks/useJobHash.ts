import { useEffect, useState } from 'react'
import type { Dispatch, SetStateAction } from 'react'
import { HttpError, getJob } from '../api'

const HASH = /^#job=(\d+)$/

function hashJobId(): number | null {
  const match = HASH.exec(window.location.hash)
  return match ? Number(match[1]) : null
}

/**
 * The selected job, kept in location.hash (#job=<id>) so a reload reopens it. The hash is
 * rewritten with history.replaceState (no reload, no history entries); a job id that the
 * server does not know (404) clears the selection.
 */
export function useJobHash(): [number | null, Dispatch<SetStateAction<number | null>>] {
  const [selectedId, setSelectedId] = useState<number | null>(hashJobId)

  useEffect(() => {
    const initial = hashJobId()
    if (initial === null) return
    getJob(initial).catch((e: unknown) => {
      if (e instanceof HttpError && e.status === 404) {
        setSelectedId((current) => (current === initial ? null : current))
      }
    })
  }, [])

  useEffect(() => {
    const hash = selectedId === null ? '' : `#job=${selectedId}`
    if (window.location.hash !== hash) {
      const { pathname, search } = window.location
      window.history.replaceState(window.history.state, '', `${pathname}${search}${hash}`)
    }
  }, [selectedId])

  return [selectedId, setSelectedId]
}
