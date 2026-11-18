import { useState } from 'react'
import { errorMessage, revealFile } from '../api'
import { trackErrorText } from '../messages'
import { KEPT_STATUSES, MISSING_STATUSES } from '../types'
import type { TrackRecord } from '../types'
import AttachButton from './AttachButton'
import MatchPicker from './MatchPicker'
import StatusPill from './StatusPill'

interface Props {
  jobId: number
  record: TrackRecord
  /** Job is queued or running: attach and choose would answer 409. */
  attachDisabled: boolean
  onUpdated: (record: TrackRecord) => void
}

const BUSY_TITLE = 'Wait until the job has finished'

export default function TrackRow({ jobId, record, attachDisabled, onUpdated }: Props) {
  const [revealError, setRevealError] = useState<string | null>(null)
  const [picking, setPicking] = useState(false)
  const revealable = KEPT_STATUSES.includes(record.status) && record.file_name !== null
  const missing = MISSING_STATUSES.includes(record.status)
  const pickable =
    record.status === 'review_skipped' || record.status === 'not_found' || record.status === 'failed'
  const pickerId = `pick-${record.id}`

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
        {record.error && <p className="text-xs text-red-400">{trackErrorText(record.error)}</p>}
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
            {pickable && (
              <button
                type="button"
                disabled={attachDisabled}
                onClick={() => setPicking((open) => !open)}
                aria-expanded={picking}
                aria-controls={picking ? pickerId : undefined}
                aria-label={`Pick a YouTube Music match for ${record.title}`}
                title={attachDisabled ? BUSY_TITLE : undefined}
                className={`rounded border px-2 py-1 disabled:cursor-not-allowed disabled:opacity-50 ${
                  picking ? 'border-sky-500/60 bg-sky-500/10' : 'border-zinc-700 hover:bg-zinc-800'
                }`}
              >
                Pick match
              </button>
            )}
            <AttachButton jobId={jobId} record={record} disabled={attachDisabled} onUpdated={onUpdated} />
          </div>
        )}
        {picking && pickable && (
          <div id={pickerId}>
            <MatchPicker jobId={jobId} record={record} onChosen={() => setPicking(false)} />
          </div>
        )}
      </div>
    </li>
  )
}
