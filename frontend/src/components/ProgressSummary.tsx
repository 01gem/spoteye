import type { ProgressMap, ProgressPhase } from '../types'

const ORDER: readonly ProgressPhase[] = ['matching', 'downloading', 'converting', 'tagging', 'waiting']

/** "2 downloading · 1 converting · 5 waiting", counted from the live progress map. */
export default function ProgressSummary({ progress }: { progress: ProgressMap }) {
  const counts = new Map<ProgressPhase, number>()
  for (const { phase } of Object.values(progress)) counts.set(phase, (counts.get(phase) ?? 0) + 1)
  const parts = ORDER.filter((phase) => counts.has(phase)).map((phase) => `${counts.get(phase)} ${phase}`)
  if (parts.length === 0) return null
  return <span className="text-sky-300 tabular-nums">{parts.join(' · ')}</span>
}
