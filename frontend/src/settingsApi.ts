import { detailText, request } from './api'

/** GET /api/settings. */
export interface Settings {
  spotify_client_id: string
  output_dir: string
  cookies_file: string | null
  max_workers: number
  match_retry_days: number
  /** Where .env, the sign-in, the database and logs live. */
  app_home: string
  frozen: boolean
}

/** PUT /api/settings takes the whole editable form. */
export type SettingsForm = Pick<
  Settings,
  'spotify_client_id' | 'output_dir' | 'cookies_file' | 'max_workers' | 'match_retry_days'
>

export type FieldErrors = Partial<Record<keyof SettingsForm, string>>

export const toForm = (s: Settings): SettingsForm => ({
  spotify_client_id: s.spotify_client_id,
  output_dir: s.output_dir,
  cookies_file: s.cookies_file,
  max_workers: s.max_workers,
  match_retry_days: s.match_retry_days,
})

/** The form as typed (numbers stay text until saved). */
export type Draft = Record<keyof SettingsForm, string>

export const toDraft = (s: Settings): Draft => ({
  spotify_client_id: s.spotify_client_id,
  output_dir: s.output_dir,
  cookies_file: s.cookies_file ?? '',
  max_workers: String(s.max_workers),
  match_retry_days: String(s.match_retry_days),
})

/** Empty number fields become 0 so the server answers with its range message. */
export const fromDraft = (d: Draft): SettingsForm => ({
  spotify_client_id: d.spotify_client_id.trim(),
  output_dir: d.output_dir.trim(),
  cookies_file: d.cookies_file.trim() === '' ? null : d.cookies_file.trim(),
  max_workers: Number(d.max_workers) || 0,
  match_retry_days: Number(d.match_retry_days) || 0,
})

/** A failed save; fieldErrors maps each rejected field to its (already friendly) message. */
export class SettingsError extends Error {
  readonly fieldErrors: FieldErrors

  constructor(message: string, fieldErrors: FieldErrors = {}) {
    super(message)
    this.name = 'SettingsError'
    this.fieldErrors = fieldErrors
  }
}

const FIELDS: readonly string[] = ['spotify_client_id', 'output_dir', 'cookies_file', 'max_workers', 'match_retry_days']

function isField(name: unknown): name is keyof SettingsForm {
  return typeof name === 'string' && FIELDS.includes(name)
}

/** FastAPI 422: detail = [{loc: ["body", field], msg}] -> {field: msg}. */
function fieldErrorsFrom(body: unknown): FieldErrors {
  const errors: FieldErrors = {}
  const detail = typeof body === 'object' && body !== null && 'detail' in body ? body.detail : null
  if (!Array.isArray(detail)) return errors
  for (const item of detail as unknown[]) {
    if (typeof item !== 'object' || item === null || !('loc' in item) || !('msg' in item)) continue
    const field = Array.isArray(item.loc) ? (item.loc as unknown[])[1] : undefined
    if (isField(field) && errors[field] === undefined) errors[field] = String(item.msg)
  }
  return errors
}

export const getSettings = (): Promise<Settings> => request<Settings>('/api/settings')

export async function saveSettings(form: SettingsForm): Promise<Settings> {
  const res = await fetch('/api/settings', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(form),
  })
  let body: unknown = null
  try {
    body = await res.json()
  } catch {
    // not JSON (e.g. the backend is not reachable through the dev proxy)
  }
  if (res.ok) return body as Settings
  const message = detailText(body) ?? `${res.status} ${res.statusText}`.trim()
  throw new SettingsError(message, res.status === 422 ? fieldErrorsFrom(body) : {})
}

export const updateYtDlp = (): Promise<{ output: string }> =>
  request<{ output: string }>('/api/tools/update-ytdlp', { method: 'POST' })
