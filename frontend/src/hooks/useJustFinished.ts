import { useEffect, useRef, useState } from 'react'
import { BUSY_STATUSES } from '../types'
import type { JobStatus } from '../types'

const APP_TITLE = 'Spoteye'

/**
 * True after this view saw the job go from queued/running to done/partial (not when an
 * already-finished job is opened). Also marks the tab title, restored on unmount.
 */
export function useJustFinished(
  status: JobStatus | undefined,
  name: string | undefined,
): [boolean, () => void] {
  const [finished, setFinished] = useState(false)
  const prevStatus = useRef<JobStatus | null>(null)

  useEffect(() => {
    const prev = prevStatus.current
    prevStatus.current = status ?? null
    if (prev && BUSY_STATUSES.includes(prev) && (status === 'done' || status === 'partial')) {
      setFinished(true)
    }
  }, [status])

  useEffect(() => {
    if (finished && name) document.title = `✓ ${name} · ${APP_TITLE}`
  }, [finished, name])

  useEffect(
    () => () => {
      document.title = APP_TITLE
    },
    [],
  )

  return [finished, () => setFinished(false)]
}
