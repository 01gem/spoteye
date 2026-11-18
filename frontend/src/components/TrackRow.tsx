import { useRef, useState } from 'react'
import type { ChangeEvent } from 'react'
import { attachFile, errorMessage, revealFile } from '../api'
import { KEPT_STATUSES, MISSING_STATUSES } from '../types'
import type { TrackRecord } from '../types'
import StatusPill from './StatusPill'

const ACCEPT = '.mp3,.m4a,.opus,.flac,.ogg'

interface Props {
  jobId: number
  record: TrackRecord
  /** Job is queued or running: the API would answer 409. */
  attachDisabled: boolean
  onUpdated: (record: TrackRecord) => void
}

export default function TrackRow({ jobId, record, attachDisabled, onUpdated }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [progress, setProgress] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [revealError, setRevealError] = useState<string | null>(null)
  const revealable = KEPT_STATUSES.includes(record.status) && record.file_name !== null
  const missing = MISSING_STATUSES.includes(record.status)
  const uploading = progress !== null

  async function onFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    setError(null)
    setProgress(0)
    try {
      onUpdated(await attachFile(jobId, record.id, file, setProgress))
    } catch (e: unknown) {
      setError(errorMessage(e))
    } finally {
      setProgress(null)
    }
  }

  async function reveal() {
    setRevealError(null)
    try {
      await revealFile(jobId, record.id)
    } catch (e: unknown) {
      setRevealError(errorMessage(e))
    }
  }

  return (
    <li className="flex gap-3 border-b border-zinc-800/80 py-2.5 last:border-b-0">
      <span className="w-7 shrink-0 pt-0.5 text-right text-sm text-zinc-500 tabular-nums">
        {record.position}
      </span>
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <p className="min-w-0 truncate text-sm font-medium">{record.title}</p>
          <StatusPill status={record.status} />
          {record.upscaled && (
            <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-xs text-amber-300">
              upscaled
            </span>
          )}
        </div>
        <p className="truncate text-xs text-zinc-400">{record.artists}</p>
        <p className="text-xs text-zinc-500">
          {(record.source || record.output) && (
            <span className="mr-3">
              {record.source ?? '-'} → {record.output ?? '-'}
            </span>
          )}
          <span className="tabular-nums">score {record.score === null ? '-' : record.score.toFixed(2)}</span>
        </p>
        {record.file_name && (
          <div className="flex items-center gap-2">
            <p className="min-w-0 truncate font-mono text-[11px] text-zinc-500" title={record.file_name}>
              {record.file_name}
            </p>
            {revealable && (
              <button
                type="button"
                onClick={() => void reveal()}
                aria-label={`Show ${record.title} in folder`}
                title={revealError ?? undefined}
                className="shrink-0 rounded border border-zinc-700 px-1.5 py-0.5 text-[11px] text-zinc-300 hover:bg-zinc-800"
              >
                Show in folder
              </button>
            )}
          </div>
        )}
        {revealError && <p className="text-xs text-red-400">{revealError}</p>}
        {record.error && <p className="text-xs text-red-400">{record.error}</p>}
        {missing && (
          <div className="flex flex-wrap items-center gap-3 pt-1 text-xs">
            <a
              href={`https://open.spotify.com/track/${record.spotify_id}`}
              target="_blank"
              rel="noreferrer"
              className="text-green-400 underline-offset-2 hover:underline"
            >
              Open on Spotify
            </a>
            <button
              type="button"
              disabled={attachDisabled || uploading}
              onClick={() => inputRef.current?.click()}
              aria-label={`Attach a file for ${record.title}`}
              title={attachDisabled ? 'Wait until the job has finished' : undefined}
              className="rounded border border-zinc-700 px-2 py-1 hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Attach file
            </button>
            <input
              ref={inputRef}
              type="file"
              accept={ACCEPT}
              onChange={(e) => void onFile(e)}
              className="hidden"
              aria-label={`Audio file for ${record.title}`}
              tabIndex={-1}
            />
          </div>
        )}
        {uploading && (
          <div
            role="progressbar"
            aria-label={`Uploading file for ${record.title}`}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(progress * 100)}
            className="h-1.5 w-full max-w-xs overflow-hidden rounded bg-zinc-800"
          >
            <div className="h-full bg-sky-500 transition-[width]" style={{ width: `${progress * 100}%` }} />
          </div>
        )}
        {error && (
          <p role="alert" className="text-xs text-red-400">
            {error}
          </p>
        )}
      </div>
    </li>
  )
}
