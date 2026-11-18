// Mirrors backend/app/web/schemas.py and app/web/events.py (Milestone 5A).

export type JobStatus = 'queued' | 'running' | 'done' | 'partial' | 'failed' | 'stopped'

export type RecordStatus =
  | 'pending'
  | 'done'
  | 'skipped'
  | 'not_found'
  | 'review_skipped'
  | 'failed'
  | 'manual'

/** Count as complete. */
export const KEPT_STATUSES: readonly RecordStatus[] = ['done', 'skipped', 'manual']
/** Still need attention (same as the backend's _missing.txt). */
export const MISSING_STATUSES: readonly RecordStatus[] = ['not_found', 'review_skipped', 'failed']
/** The API refuses resume/attach (409) while a job is in one of these. */
export const BUSY_STATUSES: readonly JobStatus[] = ['queued', 'running']
export const RESUMABLE_STATUSES: readonly JobStatus[] = ['partial', 'failed', 'stopped']

export interface Health {
  ffmpeg: boolean
  deno: boolean
  spotify_auth: boolean
  output_dir: string
}

export interface Preset {
  value: string
  label: string
}

export interface ResolvedTrack {
  spotify_id: string
  position: number
  title: string
  artists: string[]
  album: string
  duration_ms: number
  isrc: string | null
  cover_url: string | null
}

export interface Resolved {
  kind: 'track' | 'playlist'
  name: string
  /** Folder the job will save into (same rule as job creation). */
  target_dir: string
  tracks: ResolvedTrack[]
}

export interface JobSummary {
  id: number
  name: string
  kind: string
  preset: string
  status: JobStatus
  /** ISO 8601 UTC, ends in "Z". */
  created_at: string
  done: number
  total: number
}

export interface TrackRecord {
  id: number
  position: number
  spotify_id: string
  title: string
  /** Comma-joined. */
  artists: string
  isrc: string | null
  duration_ms: number
  status: RecordStatus
  video_id: string | null
  score: number | null
  source: string | null
  output: string | null
  upscaled: boolean
  file_name: string | null
  error: string | null
  updated_at: string
}

export interface JobDetail extends JobSummary {
  url: string
  out_dir: string
  finished_at: string | null
  records: TrackRecord[]
}

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
