import { useEffect, useState } from 'react'
import { errorMessage, resumeJob } from '../api'
import { useJobEvents } from '../hooks/useJobEvents'
import { useJustFinished } from '../hooks/useJustFinished'
import { BUSY_STATUSES, KEPT_STATUSES, RESUMABLE_STATUSES } from '../types'
import type { JobStatus, RecordStatus, TrackRecord } from '../types'
import FinishedBanner from './FinishedBanner'
import ProgressSummary from './ProgressSummary'
import SaveLocation from './SaveLocation'
import StatusPill from './StatusPill'
import StopButton from './StopButton'
import TrackRow from './TrackRow'

interface Props {
  jobId: number
  onStatusChange: (status: JobStatus) => void
}

function countOf(records: TrackRecord[], ...statuses: RecordStatus[]): number {
  return records.filter((r) => statuses.includes(r.status)).length
}

export default function JobView({ jobId, onStatusChange }: Props) {
  const { job, records, progress, connected, updateRecord } = useJobEvents(jobId)
  const [resuming, setResuming] = useState(false)
  const [resumeError, setResumeError] = useState<string | null>(null)
  const status = job?.status
  const [finished, dismissFinished] = useJustFinished(status, job?.name)

  useEffect(() => {
    if (status) onStatusChange(status)
  }, [status, onStatusChange])

  if (!job) {
    return <p className="p-6 text-sm text-zinc-500">Loading job {jobId}…</p>
  }

  const kept = records.filter((r) => KEPT_STATUSES.includes(r.status)).length
  const percent = records.length ? Math.round((kept / records.length) * 100) : 0
  const busy = BUSY_STATUSES.includes(job.status)
  const counts: [string, number][] = [
    ['done', countOf(records, 'done')],
    ['skipped', countOf(records, 'skipped')],
    ['manual', countOf(records, 'manual')],
    ['missing', countOf(records, 'not_found', 'review_skipped')],
    ['failed', countOf(records, 'failed')],
  ]

  async function resume() {
    setResuming(true)
    setResumeError(null)
    try {
      await resumeJob(jobId)
    } catch (e: unknown) {
      setResumeError(errorMessage(e))
    } finally {
      setResuming(false)
    }
  }

  return (
    <section aria-label={`Job ${job.name}`} className="space-y-4">
      <header className="space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="min-w-0 truncate text-lg font-semibold">{job.name}</h2>
          <StatusPill status={job.status} />
          <span className="text-xs text-zinc-500">preset {job.preset}</span>
          <span
            role="status"
            aria-label={connected ? 'Live updates connected' : 'Live updates disconnected'}
            title={connected ? 'Live updates connected' : 'Live updates disconnected'}
            className={`ml-auto h-2.5 w-2.5 rounded-full ${connected ? 'bg-green-500' : 'bg-zinc-600'}`}
          />
        </div>
        <SaveLocation path={job.out_dir} jobId={job.id} />
        {finished && (job.status === 'done' || job.status === 'partial') && (
          <FinishedBanner
            jobId={job.id}
            partial={job.status === 'partial'}
            kept={kept}
            total={records.length}
            outDir={job.out_dir}
            onDismiss={dismissFinished}
          />
        )}
        <div
          role="progressbar"
          aria-label="Tracks complete"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={percent}
          className="h-2 overflow-hidden rounded-full bg-zinc-800"
        >
          <div className="h-full bg-green-500 transition-[width]" style={{ width: `${percent}%` }} />
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-zinc-400">
          <span className="text-zinc-200 tabular-nums">
            {kept}/{records.length}
          </span>
          {counts.map(([label, n]) => (
            <span key={label} className="tabular-nums">
              {n} {label}
            </span>
          ))}
          {job.status === 'running' && <ProgressSummary progress={progress} />}
          {busy && <StopButton jobId={job.id} />}
          {RESUMABLE_STATUSES.includes(job.status) && (
            <button
              type="button"
              onClick={() => void resume()}
              disabled={resuming}
              className="ml-auto rounded-md bg-sky-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50"
            >
              {resuming ? 'Resuming…' : 'Resume'}
            </button>
          )}
        </div>
        {resumeError && (
          <p role="alert" className="text-sm text-red-400">
            {resumeError}
          </p>
        )}
      </header>
      {records.length === 0 ? (
        <p className="rounded-lg border border-dashed border-zinc-800 p-6 text-center text-sm text-zinc-500">
          This job has no tracks.
        </p>
      ) : (
        <ol className="rounded-lg border border-zinc-800 bg-zinc-900/60 px-3">
          {records.map((r) => (
            <TrackRow
              key={r.id}
              jobId={jobId}
              record={r}
              progress={progress[r.id]}
              attachDisabled={busy}
              onUpdated={updateRecord}
            />
          ))}
        </ol>
      )}
    </section>
  )
}
