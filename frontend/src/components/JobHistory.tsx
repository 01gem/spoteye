import { useEffect, useState } from 'react'
import { deleteJob, errorMessage, listJobs } from '../api'
import { useArmed } from '../hooks/useArmed'
import { BUSY_STATUSES } from '../types'
import type { JobSummary } from '../types'
import StatusPill from './StatusPill'

const REFRESH_MS = 10_000
const DELETE_TITLE = 'Removes it from history only; your files stay.'

interface Props {
  selectedId: number | null
  onSelect: (jobId: number) => void
  onDeleted: (jobId: number) => void
  /** Changing this reloads the list (e.g. when the selected job's status changes). */
  refreshKey: number
}

function TrashIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
      <path d="M8 2a1 1 0 0 0-1 1v1H4a1 1 0 0 0 0 2h.1l.8 10.1A2 2 0 0 0 6.9 18h6.2a2 2 0 0 0 2-1.9L15.9 6h.1a1 1 0 1 0 0-2h-3V3a1 1 0 0 0-1-1H8Zm1 2h2V4H9v0Z" />
    </svg>
  )
}

export default function JobHistory({ selectedId, onSelect, onDeleted, refreshKey }: Props) {
  const [jobs, setJobs] = useState<JobSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [armed, arm] = useArmed<number>()

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

  async function onDelete(job: JobSummary) {
    if (armed !== job.id) {
      arm(job.id)
      return
    }
    arm(null)
    try {
      await deleteJob(job.id)
      setJobs((list) => list?.filter((j) => j.id !== job.id) ?? null)
      setError(null)
      onDeleted(job.id)
    } catch (e: unknown) {
      setError(errorMessage(e))
    }
  }

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
          const confirming = armed === job.id
          return (
            <li key={job.id} className="flex items-stretch gap-1">
              <button
                type="button"
                onClick={() => onSelect(job.id)}
                aria-current={selected ? 'true' : undefined}
                className={`flex min-w-0 flex-1 items-center gap-3 rounded-md border px-3 py-2 text-left text-sm ${
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
              <button
                type="button"
                onClick={() => void onDelete(job)}
                disabled={BUSY_STATUSES.includes(job.status)}
                aria-label={
                  confirming
                    ? `Confirm: delete job ${job.name} from history`
                    : `Delete job ${job.name} from history`
                }
                title={DELETE_TITLE}
                className={`shrink-0 rounded-md border px-2 text-xs disabled:cursor-not-allowed disabled:opacity-40 ${
                  confirming
                    ? 'border-red-500 bg-red-600 font-medium text-white hover:bg-red-500'
                    : 'border-zinc-800 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200'
                }`}
              >
                {confirming ? 'Confirm' : <TrashIcon />}
              </button>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
