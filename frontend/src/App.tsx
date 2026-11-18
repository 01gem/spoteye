import { useCallback, useState } from 'react'
import HealthBanner from './components/HealthBanner'
import JobHistory from './components/JobHistory'
import JobView from './components/JobView'
import LinkForm from './components/LinkForm'
import TrackPreview from './components/TrackPreview'
import type { Resolved } from './types'

export default function App() {
  const [preview, setPreview] = useState<Resolved | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [historyKey, setHistoryKey] = useState(0)

  const refreshHistory = useCallback(() => setHistoryKey((k) => k + 1), [])
  const onCreated = useCallback(
    (jobId: number) => {
      setSelectedId(jobId)
      refreshHistory()
    },
    [refreshHistory],
  )

  return (
    <div className="mx-auto max-w-7xl space-y-6 px-4 py-6">
      <header className="space-y-3">
        <h1 className="text-2xl font-bold tracking-tight">
          Spot<span className="text-green-500">eye</span>
        </h1>
        <HealthBanner />
      </header>
      <main className="grid gap-6 lg:grid-cols-[minmax(0,26rem)_minmax(0,1fr)]">
        <div className="space-y-6">
          <LinkForm onPreview={setPreview} onCreated={onCreated} />
          {preview && <TrackPreview resolved={preview} />}
          <JobHistory selectedId={selectedId} onSelect={setSelectedId} refreshKey={historyKey} />
        </div>
        <div className="min-w-0">
          {selectedId === null ? (
            <p className="rounded-lg border border-dashed border-zinc-800 p-10 text-center text-sm text-zinc-500">
              Paste a link and press Download, or pick a job from the history.
            </p>
          ) : (
            <JobView key={selectedId} jobId={selectedId} onStatusChange={refreshHistory} />
          )}
        </div>
      </main>
    </div>
  )
}
