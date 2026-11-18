import { useRef, useState } from 'react'
import type { ChangeEvent } from 'react'
import { attachFile, errorMessage } from '../api'
import type { TrackRecord } from '../types'

const ACCEPT = '.mp3,.m4a,.opus,.flac,.ogg'

interface Props {
  jobId: number
  record: TrackRecord
  /** Job is queued or running: the API would answer 409. */
  disabled: boolean
  onUpdated: (record: TrackRecord) => void
}

/** "Attach file" for a missing track: upload with progress, then report the updated record. */
export default function AttachButton({ jobId, record, disabled, onUpdated }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [progress, setProgress] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
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

  return (
    <>
      <button
        type="button"
        disabled={disabled || uploading}
        onClick={() => inputRef.current?.click()}
        aria-label={`Attach a file for ${record.title}`}
        title={disabled ? 'Wait until the job has finished' : undefined}
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
      {uploading && (
        <div
          role="progressbar"
          aria-label={`Uploading file for ${record.title}`}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(progress * 100)}
          className="h-1.5 w-full max-w-xs basis-full overflow-hidden rounded bg-zinc-800"
        >
          <div className="h-full bg-sky-500 transition-[width]" style={{ width: `${progress * 100}%` }} />
        </div>
      )}
      {error && (
        <p role="alert" className="basis-full text-xs text-red-400">
          {error}
        </p>
      )}
    </>
  )
}
