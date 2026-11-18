import { useEffect, useState } from 'react'
import { errorMessage, listJobs } from '../api'
import type { JobSummary } from '../types'
import StatusPill from './StatusPill'

const REFRESH_MS = 10_000

interface Props {
  selectedId: number | null
  onSelect: (jobId: number) => void
  /** Changing this reloads the list (e.g. when the selected job's status changes). */
  refreshKey: number
}

export default function JobHistory({ selectedId, onSelect, refreshKey }: Props) {
  const [jobs, setJobs] = useState<JobSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const load = () => {
      listJobs()
        .then((list) => {
          if (cancelled) return
          setJobs(list)
          setError(null)
        })
        .catch((e: unknown) => !cancelled && setError(errorMessage(e)))
    }
    load()
    const timer = window.setInterval(load, REFRESH_MS)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [refreshKey])

  return (
    <section aria-labelledby="history-heading" className="space-y-2">
      <h2 id="history-heading" className="text-sm font-semibold tracking-wide text-zinc-400 uppercase">
        History
      </h2>
      {error && (
        <p role="alert" className="text-sm text-red-400">
          {error}
        </p>
      )}
      {jobs?.length === 0 && <p className="text-sm text-zinc-500">No jobs yet.</p>}
      <ul className="space-y-1">
        {jobs?.map((job) => {
          const selected = job.id === selectedId
          return (
            <li key={job.id}>
              <button
                type="button"
                onClick={() => onSelect(job.id)}
                aria-current={selected ? 'true' : undefined}
                className={`flex w-full items-center gap-3 rounded-md border px-3 py-2 text-left text-sm ${
                  selected
                    ? 'border-sky-500/60 bg-sky-500/10'
                    : 'border-zinc-800 bg-zinc-900/60 hover:bg-zinc-800/80'
                }`}
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{job.name}</p>
                  <p className="text-xs text-zinc-500">
                    {new Date(job.created_at).toLocaleString()} ·{' '}
                    <span className="tabular-nums">
                      {job.done}/{job.total}
                    </span>
                  </p>
                </div>
                <StatusPill status={job.status} />
              </button>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
