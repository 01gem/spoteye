import { useState } from 'react'
import { errorMessage } from '../api'
import { updateYtDlp } from '../settingsApi'
import type { Health } from '../types'

/** "yt-dlp <version>" with an Update button for the bundled program (packaged app only). */
export default function YtDlpSection({ health, onUpdated }: { health: Health; onUpdated: () => void }) {
  const [busy, setBusy] = useState(false)
  const [output, setOutput] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function update() {
    setBusy(true)
    setError(null)
    setOutput(null)
    try {
      setOutput((await updateYtDlp()).output || '(no output)')
      onUpdated()
    } catch (e: unknown) {
      setError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="space-y-2">
      <h3 className="text-sm font-semibold text-zinc-200">yt-dlp {health.yt_dlp_version}</h3>
      {health.yt_dlp_mode === 'binary' ? (
        <>
          <button
            type="button"
            onClick={() => void update()}
            disabled={busy}
            className="rounded-md border border-zinc-700 px-3 py-1.5 text-sm text-zinc-200 hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy ? 'Updating…' : 'Update yt-dlp'}
          </button>
          {error && (
            <p role="alert" className="text-sm text-red-400">
              {error}
            </p>
          )}
          {output !== null && (
            <pre className="max-h-48 overflow-auto rounded-md bg-black/40 p-2 text-xs whitespace-pre-wrap text-zinc-300">
              {output}
            </pre>
          )}
        </>
      ) : (
        <p className="text-sm text-zinc-400">
          From source: <code className="font-mono">pip install -U yt-dlp</code>
        </p>
      )}
    </section>
  )
}
