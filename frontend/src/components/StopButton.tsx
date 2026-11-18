import { useState } from 'react'
import { errorMessage, stopJob } from '../api'
import { useArmed } from '../hooks/useArmed'

/** Two-click Stop for a queued or running job (render it only while the job is busy). */
export default function StopButton({ jobId }: { jobId: number }) {
  const [armed, arm] = useArmed<true>()
  const [stopping, setStopping] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function onClick() {
    if (armed === null) {
      setError(null)
      arm(true)
      return
    }
    arm(null)
    setStopping(true)
    try {
      await stopJob(jobId)
    } catch (e: unknown) {
      setError(errorMessage(e))
      setStopping(false)
    }
  }

  if (stopping) {
    return (
      <span role="status" className="ml-auto text-sm text-orange-300">
        Stopping… (tracks already downloading will finish)
      </span>
    )
  }

  return (
    <span className="ml-auto flex items-center gap-2">
      {error && (
        <span role="alert" className="text-sm text-red-400">
          {error}
        </span>
      )}
      <button
        type="button"
        onClick={() => void onClick()}
        aria-label={armed ? 'Confirm stopping this job' : 'Stop this job'}
        className={`rounded-md px-3 py-1.5 text-sm font-medium ${
          armed
            ? 'bg-red-600 text-white hover:bg-red-500'
            : 'border border-zinc-700 text-zinc-200 hover:bg-zinc-800'
        }`}
      >
        {armed ? 'Confirm stop' : 'Stop'}
      </button>
    </span>
  )
}
