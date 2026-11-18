import type { Health, JobDetail, JobSummary, Preset, Resolved, TrackRecord } from './types'

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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init)
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`.trim()
    try {
      message = detailText(await res.json()) ?? message
    } catch {
      // not JSON (e.g. the dev proxy could not reach the backend)
    }
    throw new Error(message)
  }
  return (await res.json()) as T
}

function post(body: unknown): RequestInit {
  return {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }
}

export const getHealth = (): Promise<Health> => request<Health>('/api/health')

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
