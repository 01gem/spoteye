// SSE events of GET /api/jobs/{id}/events; mirrors backend/app/web/events.py and
// app/services/progress.py. Re-exported by types.ts.
import type { JobDetail, JobStatus, RecordStatus } from './types'

/** SSE "track": one record changed. */
export interface TrackEvent {
  type: 'track'
  job_id: number
  record_id: number
  position: number
  status: RecordStatus
  score: number | null
  source: string | null
  output: string | null
  upscaled: boolean
  file_name: string | null
  error: string | null
}

/** SSE "job": status and kept/total counts. */
export interface JobEvent {
  type: 'job'
  job_id: number
  status: JobStatus
  done: number
  total: number
}

export type ProgressPhase = 'matching' | 'waiting' | 'downloading' | 'converting' | 'tagging'

/** SSE "progress": live state of one running track (throttled; null = unknown). */
export interface ProgressEvent {
  type: 'progress'
  job_id: number
  record_id: number
  phase: ProgressPhase
  /** 0-100. */
  percent: number | null
  downloaded_bytes: number | null
  /** May be yt-dlp's estimate. */
  total_bytes: number | null
  /** Bytes per second. */
  speed: number | null
  /** Seconds left. */
  eta: number | null
}

/** Latest progress per running record; keys are record ids. */
export type ProgressMap = Record<string, ProgressEvent>

/** SSE "snapshot": the job plus the current progress (absent from the REST JobDetail). */
export type JobSnapshot = JobDetail & { progress?: ProgressMap }
