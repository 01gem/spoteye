import { useState } from 'react'
import { errorMessage, openFolder } from '../api'

interface Props {
  jobId: number
  partial: boolean
  kept: number
  total: number
  outDir: string
  onDismiss: () => void
}

/** Shown once when a job this tab watched goes from queued/running to done or partial. */
export default function FinishedBanner({ jobId, partial, kept, total, outDir, onDismiss }: Props) {
  const [error, setError] = useState<string | null>(null)
  const missing = total - kept
  const tone = partial
    ? 'border-amber-500/40 bg-amber-500/10 text-amber-100'
    : 'border-green-500/40 bg-green-500/10 text-green-100'

  async function open() {
    setError(null)
    try {
      await openFolder(jobId)
    } catch (e: unknown) {
      setError(errorMessage(e))
    }
  }

  return (
    <div role="status" className={`flex items-start gap-3 rounded-lg border p-3 text-sm ${tone}`}>
      <div className="min-w-0 flex-1 space-y-1">
        <p>
          Finished: {kept} of {total} tracks saved to{' '}
          <span className="font-mono break-all">{outDir}</span>
        </p>
        {partial && (
          <p>
            {missing} missing; see <span className="font-mono">_missing.txt</span> in that folder, or use
            Attach file below.
          </p>
        )}
        {error && <p className="text-red-400">{error}</p>}
      </div>
      <button
        type="button"
        onClick={() => void open()}
        aria-label="Open folder in File Explorer"
        className="shrink-0 rounded-md border border-current/40 px-2 py-1 text-xs hover:bg-black/20"
      >
        Open folder
      </button>
      <button
        type="button"
        onClick={onDismiss}
        aria-label="Dismiss finished message"
        className="shrink-0 rounded px-1.5 text-base leading-none hover:bg-black/20"
      >
        ×
      </button>
    </div>
  )
}
