import type { Candidate, Health, JobDetail, JobSummary, Preset, Resolved, StopResult } from './types'
import type { LoginStatus, TrackRecord } from './types'

/** FastAPI errors: {"detail": "text"} or, for validation, {"detail": [{"msg": ...}, ...]}. */
export function detailText(body: unknown): string | null {
  if (typeof body !== 'object' || body === null || !('detail' in body)) return null
  const { detail } = body as { detail: unknown }
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item: unknown) =>
        typeof item === 'object' && item !== null && 'msg' in item
          ? String((item as { msg: unknown }).msg)
          : String(item),
      )
      .join('; ')
  }
  return null
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

async function fail(res: Response): Promise<never> {
  let message = `${res.status} ${res.statusText}`.trim()
  try {
    message = detailText(await res.json()) ?? message
  } catch {
    // not JSON (e.g. the dev proxy could not reach the backend)
  }
  throw new Error(message)
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init)
  if (!res.ok) await fail(res)
  return (await res.json()) as T
}

/** For 204 No Content endpoints: never calls res.json(). */
async function send(path: string, init?: RequestInit): Promise<void> {
  const res = await fetch(path, init)
  if (!res.ok) await fail(res)
}

function post(body: unknown): RequestInit {
  return {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }
}

export const getHealth = (): Promise<Health> => request<Health>('/api/health')

/** Opens Spotify's sign-in page (via the backend); a pending sign-in is replaced. */
export const startLogin = (): Promise<LoginStatus> =>
  request<LoginStatus>('/api/auth/login', { method: 'POST' })

export const cancelLogin = (): Promise<void> => send('/api/auth/cancel', { method: 'POST' })

export const getLoginStatus = (): Promise<LoginStatus> => request<LoginStatus>('/api/auth/status')

export const getPresets = (): Promise<Preset[]> => request<Preset[]>('/api/presets')

export const resolve = (url: string): Promise<Resolved> =>
  request<Resolved>('/api/resolve', post({ url }))

export const createJob = (
  url: string,
  preset: string,
  acceptReview: boolean,
): Promise<{ job_id: number }> =>
  request<{ job_id: number }>('/api/jobs', post({ url, preset, accept_review: acceptReview }))

export const listJobs = (): Promise<JobSummary[]> => request<JobSummary[]>('/api/jobs')

export const getJob = (id: number): Promise<JobDetail> => request<JobDetail>(`/api/jobs/${id}`)

export const resumeJob = (id: number, acceptReview = false): Promise<{ job_id: number }> =>
  request<{ job_id: number }>(`/api/jobs/${id}/resume`, post({ accept_review: acceptReview }))

export const openFolder = (jobId: number): Promise<void> =>
  send(`/api/jobs/${jobId}/open-folder`, { method: 'POST' })

export const revealFile = (jobId: number, recordId: number): Promise<void> =>
  send(`/api/jobs/${jobId}/tracks/${recordId}/reveal`, { method: 'POST' })

export const stopJob = (id: number): Promise<{ result: StopResult }> =>
  request<{ result: StopResult }>(`/api/jobs/${id}/stop`, { method: 'POST' })

export const deleteJob = (id: number): Promise<void> => send(`/api/jobs/${id}`, { method: 'DELETE' })

export const getCandidates = (jobId: number, recordId: number): Promise<Candidate[]> =>
  request<Candidate[]>(`/api/jobs/${jobId}/tracks/${recordId}/candidates`)

export const chooseMatch = (
  jobId: number,
  recordId: number,
  videoId: string,
): Promise<{ job_id: number }> =>
  request<{ job_id: number }>(
    `/api/jobs/${jobId}/tracks/${recordId}/choose`,
    post({ video_id: videoId }),
  )

export const getMissing = (id: number): Promise<TrackRecord[]> =>
  request<TrackRecord[]>(`/api/jobs/${id}/missing`)

/** Multipart upload via XHR so we get upload progress (0..1). Resolves with the updated record. */
export function attachFile(
  jobId: number,
  recordId: number,
  file: File,
  onProgress: (fraction: number) => void,
): Promise<TrackRecord> {
  return new Promise((resolvePromise, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `/api/jobs/${jobId}/tracks/${recordId}/attach`)
    xhr.responseType = 'json'
    xhr.upload.onprogress = (event: ProgressEvent) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total)
    }
    xhr.onload = () => {
      const body: unknown = xhr.response
      if (xhr.status >= 200 && xhr.status < 300) resolvePromise(body as TrackRecord)
      else reject(new Error(detailText(body) ?? `Upload failed (${xhr.status})`))
    }
    xhr.onerror = () => reject(new Error('Upload failed: could not reach the server.'))
    const form = new FormData()
    form.append('file', file)
    xhr.send(form)
  })
}
