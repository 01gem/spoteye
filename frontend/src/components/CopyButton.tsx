import { useState } from 'react'
import { errorMessage } from '../api'

const COPIED_MS = 1500

/** Copies `text` to the clipboard; `label` names what is copied for screen readers. */
export default function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function copy() {
    try {
      await navigator.clipboard.writeText(text)
      setError(null)
      setCopied(true)
      setTimeout(() => setCopied(false), COPIED_MS)
    } catch (e: unknown) {
      setError(`Could not copy: ${errorMessage(e)}`)
    }
  }

  return (
    <span className="inline-flex items-center gap-2">
      <button
        type="button"
        onClick={() => void copy()}
        aria-label={`Copy ${label}`}
        className="rounded-md border border-zinc-700 px-2 py-1 text-xs text-zinc-200 hover:bg-zinc-800"
      >
        {copied ? 'Copied' : 'Copy'}
      </button>
      {error && (
        <span role="alert" className="text-xs text-red-400">
          {error}
        </span>
      )}
    </span>
  )
}
