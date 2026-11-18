import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { chooseMatch, errorMessage, getCandidates } from '../api'
import type { Candidate, TrackRecord } from '../types'
import { videoIdFromLink } from '../youtube'
import Spinner from './Spinner'

const CLOSE_DELTA_S = 2

interface Props {
  jobId: number
  record: TrackRecord
  onChosen: () => void
}

function formatSeconds(total: number): string {
  const s = Math.round(total)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

function Delta({ delta }: { delta: number | null }) {
  if (delta === null) return null
  const close = Math.abs(delta) <= CLOSE_DELTA_S
  return (
    <span className={close ? 'text-green-400' : 'text-amber-300'}>
      {' '}({delta > 0 ? '+' : ''}{delta.toFixed(1)} s)
    </span>
  )
}

const SMALL_BUTTON =
  'rounded border border-zinc-700 px-2 py-1 text-xs hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50'

export default function MatchPicker({ jobId, record, onChosen }: Props) {
  const [candidates, setCandidates] = useState<Candidate[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [choosing, setChoosing] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [link, setLink] = useState('')

  useEffect(() => {
    let cancelled = false
    getCandidates(jobId, record.id)
      .then((list) => !cancelled && setCandidates(list))
      .catch((e: unknown) => !cancelled && setLoadError(errorMessage(e)))
    return () => {
      cancelled = true
    }
  }, [jobId, record.id])

  async function pick(videoId: string) {
    setChoosing(videoId)
    setError(null)
    try {
      await chooseMatch(jobId, record.id, videoId)
      onChosen()
    } catch (e: unknown) {
      setError(errorMessage(e))
    } finally {
      setChoosing(null)
    }
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const id = videoIdFromLink(link)
    if (id === null) setError("Not a YouTube link I can read. Paste a watch, youtu.be or shorts link.")
    else void pick(id)
  }

  const busy = choosing !== null
  const loading = candidates === null && loadError === null
  return (
    <div className="mt-2 space-y-3 rounded-md border border-zinc-800 bg-zinc-950/60 p-3 text-xs">
      {loading && (
        <p role="status" aria-busy="true" className="flex items-center gap-2 text-zinc-400">
          <Spinner /> Searching YouTube Music…
        </p>
      )}
      {loadError && <p role="alert" className="text-red-400">{loadError}</p>}
      {candidates?.length === 0 && <p className="text-zinc-400">No candidates found. Paste a link below.</p>}
      {candidates && candidates.length > 0 && (
        <ul aria-label={`Candidates for ${record.title}`} className="space-y-2">
          {candidates.map((c) => (
            <li key={c.video_id} className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm text-zinc-100">{c.title}</p>
                <p className="truncate text-zinc-400">
                  {c.artists.join(', ')}
                  {c.album && ` · ${c.album}`}
                  {c.duration_s !== null && ` · ${formatSeconds(c.duration_s)}`}
                  <Delta delta={c.delta_s} />
                </p>
              </div>
              <span className="text-zinc-400 tabular-nums" title="Match score">
                {c.score.toFixed(2)}
              </span>
              <a
                href={c.url}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={`Listen to ${c.title} on YouTube Music`}
                className="text-green-400 underline-offset-2 hover:underline"
              >
                Listen
              </a>
              <button
                type="button"
                disabled={busy}
                onClick={() => void pick(c.video_id)}
                aria-label={`Use ${c.title} by ${c.artists.join(', ')}`}
                className={SMALL_BUTTON}
              >
                {choosing === c.video_id ? 'Using…' : 'Use this'}
              </button>
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={onSubmit} className="space-y-1">
        <label htmlFor={`link-${record.id}`} className="block text-zinc-400">
          Or paste a YouTube / YouTube Music link
        </label>
        <div className="flex gap-2">
          <input
            id={`link-${record.id}`}
            type="text"
            inputMode="url"
            autoComplete="off"
            value={link}
            onChange={(e) => setLink(e.target.value)}
            placeholder="https://music.youtube.com/watch?v=…"
            className="min-w-0 flex-1 rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-zinc-100"
          />
          <button type="submit" disabled={busy || !link.trim()} className={SMALL_BUTTON}>
            Use link
          </button>
        </div>
      </form>
      {error && <p role="alert" className="text-red-400">{error}</p>}
    </div>
  )
}
