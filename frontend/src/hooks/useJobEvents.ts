import { useCallback, useEffect, useState } from 'react'
import type {
  JobDetail,
  JobEvent,
  JobSnapshot,
  JobStatus,
  ProgressEvent,
  ProgressMap,
  TrackEvent,
  TrackRecord,
} from '../types'

const RETRY_MS = 3000
const FINAL_STATUSES: readonly JobStatus[] = ['done', 'partial', 'failed', 'stopped']

export interface JobEvents {
  job: JobDetail | null
  records: TrackRecord[]
  /** Live phase/download progress of the tracks being worked on, by record id. */
  progress: ProgressMap
  /** True after the stream opened, false after an error (it reconnects on its own). */
  connected: boolean
  /** Apply a record returned by another call (e.g. attach) without waiting for the stream. */
  updateRecord: (record: TrackRecord) => void
}

function mergeTrack(record: TrackRecord, event: TrackEvent): TrackRecord {
  const { status, score, source, output, upscaled, file_name, error } = event
  return { ...record, status, score, source, output, upscaled, file_name, error }
}

function without(map: ProgressMap, recordId: number): ProgressMap {
  if (!(recordId in map)) return map
  const next = { ...map }
  delete next[recordId]
  return next
}

/** Live job state from GET /api/jobs/{id}/events (snapshot, then track/job/progress updates). */
export function useJobEvents(jobId: number | null): JobEvents {
  const [job, setJob] = useState<JobDetail | null>(null)
  const [progress, setProgress] = useState<ProgressMap>({})
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    if (jobId === null) return
    let source: EventSource | null = null
    let retryTimer: number | undefined
    let stopped = false

    const connect = () => {
      const es = new EventSource(`/api/jobs/${jobId}/events`)
      source = es
      es.onopen = () => setConnected(true)
      es.onerror = () => {
        setConnected(false)
        // EventSource retries by itself, except after an HTTP error response (e.g. the dev
        // proxy's 502 while uvicorn --reload restarts): then it stays closed, so retry here.
        if (es.readyState === EventSource.CLOSED && !stopped) {
          retryTimer = window.setTimeout(connect, RETRY_MS)
        }
      }
      es.addEventListener('snapshot', (event: MessageEvent<string>) => {
        const { progress: current, ...detail } = JSON.parse(event.data) as JobSnapshot
        setJob(detail)
        setProgress(current ?? {})
      })
      es.addEventListener('track', (event: MessageEvent<string>) => {
        const update = JSON.parse(event.data) as TrackEvent
        setJob((prev) =>
          prev && {
            ...prev,
            records: prev.records.map((r) => (r.id === update.record_id ? mergeTrack(r, update) : r)),
          },
        )
        if (update.status !== 'pending') setProgress((prev) => without(prev, update.record_id))
      })
      es.addEventListener('job', (event: MessageEvent<string>) => {
        const update = JSON.parse(event.data) as JobEvent
        setJob((prev) =>
          prev && { ...prev, status: update.status, done: update.done, total: update.total },
        )
        if (FINAL_STATUSES.includes(update.status)) setProgress({})
      })
      es.addEventListener('progress', (event: MessageEvent<string>) => {
        const update = JSON.parse(event.data) as ProgressEvent
        setProgress((prev) => ({ ...prev, [update.record_id]: update }))
      })
    }

    connect()
    return () => {
      stopped = true
      window.clearTimeout(retryTimer)
      source?.close()
      setJob(null)
      setProgress({})
      setConnected(false)
    }
  }, [jobId])

  const updateRecord = useCallback((record: TrackRecord) => {
    setJob((prev) =>
      prev && { ...prev, records: prev.records.map((r) => (r.id === record.id ? record : r)) },
    )
  }, [])

  return { job, records: job?.records ?? [], progress, connected, updateRecord }
}
