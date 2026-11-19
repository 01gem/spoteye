import type { ProgressEvent, ProgressPhase } from '../types'

const LABELS: Record<ProgressPhase, string> = {
  matching: 'Matching…',
  waiting: 'Waiting for a download slot',
  downloading: 'Downloading…',
  converting: 'Converting…',
  tagging: 'Tagging…',
}
const KB = 1024

/** 1 decimal: KB below 1000 KB, MB from there (1023 KB reads "1.0 MB"). */
function formatBytes(bytes: number): string {
  const kb = bytes / KB
  return kb >= 999.95 ? `${(kb / KB).toFixed(1)} MB` : `${kb.toFixed(1)} KB` // never "1000.0 KB"
}

/** Same KB/MB rule as formatBytes. */
function formatSpeed(bytesPerSecond: number): string {
  return `${formatBytes(bytesPerSecond)}/s`
}

/** m:ss */
function formatEta(seconds: number): string {
  const s = Math.max(0, Math.round(seconds))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

/** "2.1 of 4.4 MB" (unit once when both share it). */
function formatAmount(done: number, total: number): string {
  const [a, b] = [formatBytes(done), formatBytes(total)]
  return a.slice(-2) === b.slice(-2) ? `${a.slice(0, -3)} of ${b}` : `${a} of ${b}`
}

/** "47% · 2.1 of 4.4 MB · 1.3 MB/s · 0:02 left", unknown parts left out. */
function details(progress: ProgressEvent, percent: number): string {
  const { downloaded_bytes: done, total_bytes: total, speed, eta } = progress
  const parts = [`${Math.floor(percent)}%`]
  if (done !== null) parts.push(total !== null ? formatAmount(done, total) : formatBytes(done))
  if (speed !== null) parts.push(formatSpeed(speed))
  if (eta !== null) parts.push(`${formatEta(eta)} left`)
  return parts.join(' · ')
}

const BAR = 'h-1 overflow-hidden rounded-full bg-zinc-800'
const TEXT = 'text-[11px] text-zinc-500 tabular-nums'

export default function TrackProgress({ progress }: { progress: ProgressEvent }) {
  const { phase, percent } = progress
  const label = LABELS[phase]
  if (phase === 'matching' || phase === 'waiting') return <p className={TEXT}>{label}</p>
  if (phase === 'downloading' && percent !== null) {
    return (
      <div className="max-w-sm space-y-1">
        <div
          role="progressbar"
          aria-label="Download progress"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.floor(percent)}
          className={BAR}
        >
          <div className="h-full bg-sky-500 transition-[width] duration-300" style={{ width: `${percent}%` }} />
        </div>
        <p className={TEXT}>{details(progress, percent)}</p>
      </div>
    )
  }
  return (
    <div className="max-w-sm space-y-1">
      <div role="progressbar" aria-label="Track progress" aria-valuetext={label} className={BAR}>
        <div className="h-full w-1/3 bg-sky-500/70 motion-safe:animate-indeterminate motion-reduce:w-full motion-reduce:opacity-40" />
      </div>
      <p className={TEXT}>{label}</p>
    </div>
  )
}
