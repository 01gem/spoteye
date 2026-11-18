import { useEffect, useId, useState } from 'react'
import type { FormEvent } from 'react'
import { createJob, errorMessage, getPresets, resolve } from '../api'
import type { Preset, Resolved } from '../types'

const URL_RE = /open\.spotify\.com\/(?:intl-[a-z]{2,3}(?:[-_][a-z]{2,4})?\/)?(track|playlist|album)\//i
const URI_RE = /^spotify:(track|playlist|album):/i

/** Client-side check; returns an error message or null when the link looks usable. */
function checkLink(url: string): string | null {
  const match = URL_RE.exec(url) ?? URI_RE.exec(url.trim())
  if (!match) return 'Paste a Spotify track or playlist link (open.spotify.com/… or spotify:…).'
  if (match[1].toLowerCase() === 'album') return "Album links aren't supported yet."
  return null
}

interface Props {
  onPreview: (resolved: Resolved) => void
  onCreated: (jobId: number) => void
}

const buttonBase =
  'rounded-md px-4 py-2 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50'

export default function LinkForm({ onPreview, onCreated }: Props) {
  const id = useId()
  const [url, setUrl] = useState('')
  const [presets, setPresets] = useState<Preset[]>([])
  const [preset, setPreset] = useState('best')
  const [acceptReview, setAcceptReview] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getPresets()
      .then(setPresets)
      .catch((e: unknown) => setError(errorMessage(e)))
  }, [])

  async function run(action: () => Promise<void>) {
    const problem = checkLink(url)
    setError(problem)
    if (problem) return
    setBusy(true)
    try {
      await action()
    } catch (e: unknown) {
      setError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  const preview = () => run(async () => onPreview(await resolve(url.trim())))
  const download = () =>
    run(async () => onCreated((await createJob(url.trim(), preset, acceptReview)).job_id))

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    void preview()
  }

  return (
    <form onSubmit={onSubmit} className="space-y-3 rounded-lg border border-zinc-800 bg-zinc-900/60 p-4">
      <div className="space-y-1">
        <label htmlFor={`${id}-url`} className="block text-sm font-medium text-zinc-300">
          Spotify track or playlist link
        </label>
        <input
          id={`${id}-url`}
          type="text"
          inputMode="url"
          autoComplete="off"
          spellCheck={false}
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://open.spotify.com/playlist/…"
          aria-invalid={error !== null}
          aria-describedby={error ? `${id}-error` : undefined}
          className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm placeholder:text-zinc-600"
        />
      </div>
      <div className="flex flex-wrap items-end gap-4">
        <div className="space-y-1">
          <label htmlFor={`${id}-preset`} className="block text-sm font-medium text-zinc-300">
            Format
          </label>
          <select
            id={`${id}-preset`}
            value={preset}
            onChange={(e) => setPreset(e.target.value)}
            className="rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm"
          >
            {presets.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </div>
        <label className="flex items-center gap-2 pb-2 text-sm text-zinc-300">
          <input
            type="checkbox"
            checked={acceptReview}
            onChange={(e) => setAcceptReview(e.target.checked)}
            className="h-4 w-4 accent-sky-500"
          />
          Accept review matches
        </label>
      </div>
      {error && (
        <p id={`${id}-error`} role="alert" className="text-sm text-red-400">
          {error}
        </p>
      )}
      <div className="flex gap-2">
        <button type="submit" disabled={busy} className={`${buttonBase} bg-zinc-800 hover:bg-zinc-700`}>
          Preview
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void download()}
          className={`${buttonBase} bg-green-600 text-white hover:bg-green-500`}
        >
          {busy ? 'Working…' : 'Download'}
        </button>
      </div>
    </form>
  )
}
