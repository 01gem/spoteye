import type { JobStatus, RecordStatus } from '../types'

type Status = JobStatus | RecordStatus

const STYLES: Record<Status, string> = {
  pending: 'bg-gray-700/60 text-gray-200',
  queued: 'bg-gray-700/60 text-gray-200',
  running: 'bg-blue-500/20 text-blue-300 animate-pulse',
  done: 'bg-green-500/15 text-green-300',
  skipped: 'bg-zinc-800 text-zinc-400',
  manual: 'bg-violet-500/20 text-violet-300',
  review_skipped: 'bg-amber-500/15 text-amber-300',
  not_found: 'bg-red-500/15 text-red-300',
  failed: 'bg-red-500/15 text-red-300',
  partial: 'bg-amber-500/15 text-amber-300',
  stopped: 'bg-orange-500/15 text-orange-300',
}

export default function StatusPill({ status }: { status: Status }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap ${STYLES[status]}`}
    >
      {status.replace('_', ' ')}
    </span>
  )
}
