import { useId } from 'react'
import type { Ref } from 'react'
import type { Draft, FieldErrors, SettingsForm } from '../settingsApi'

interface FieldSpec {
  name: keyof SettingsForm
  label: string
  hint?: string
  number?: { min: number; max: number }
  mono?: boolean
}

const FIELDS: readonly FieldSpec[] = [
  { name: 'spotify_client_id', label: 'Spotify Client ID', mono: true },
  { name: 'output_dir', label: 'Output folder', mono: true },
  {
    name: 'cookies_file',
    label: 'YouTube cookies file (optional)',
    hint: 'cookies.txt exported from a browser logged in to YouTube; helps with bot checks',
    mono: true,
  },
  { name: 'max_workers', label: 'Parallel downloads', hint: '1-8', number: { min: 1, max: 8 } },
  {
    name: 'match_retry_days',
    label: 'Retry "not found" after (days)',
    hint: '1-365',
    number: { min: 1, max: 365 },
  },
]

interface Props {
  draft: Draft
  errors: FieldErrors
  onChange: (name: keyof SettingsForm, value: string) => void
  /** Receives the first input, so the panel can focus it on open. */
  firstRef: Ref<HTMLInputElement>
}

export default function SettingsFields({ draft, errors, onChange, firstRef }: Props) {
  const id = useId()
  return (
    <div className="space-y-4">
      {FIELDS.map((field, index) => {
        const inputId = `${id}-${field.name}`
        const error = errors[field.name]
        const describedBy = error ? `${inputId}-error` : field.hint ? `${inputId}-hint` : undefined
        return (
          <div key={field.name} className="space-y-1">
            <label htmlFor={inputId} className="block text-sm font-medium text-zinc-300">
              {field.label}
            </label>
            <input
              id={inputId}
              ref={index === 0 ? firstRef : undefined}
              type={field.number ? 'number' : 'text'}
              min={field.number?.min}
              max={field.number?.max}
              value={draft[field.name]}
              onChange={(e) => onChange(field.name, e.target.value)}
              autoComplete="off"
              spellCheck={false}
              aria-invalid={error !== undefined}
              aria-describedby={describedBy}
              className={`w-full rounded-md border bg-zinc-950 px-3 py-2 text-sm ${
                error ? 'border-red-500/70' : 'border-zinc-700'
              } ${field.mono ? 'font-mono' : ''}`}
            />
            {error ? (
              <p id={`${inputId}-error`} role="alert" className="text-xs text-red-400">
                {error}
              </p>
            ) : (
              field.hint && (
                <p id={`${inputId}-hint`} className="text-xs text-zinc-500">
                  {field.hint}
                </p>
              )
            )}
          </div>
        )
      })}
    </div>
  )
}
