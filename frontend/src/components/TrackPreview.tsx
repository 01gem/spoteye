import type { Resolved } from '../types'

/** 3723000 -> "1:02:03", 185000 -> "3:05" (hours only when needed unless forceHours). */
function formatDuration(ms: number, forceHours = false): string {
  const total = Math.round(ms / 1000)
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = String(total % 60).padStart(2, '0')
  return h > 0 || forceHours ? `${h}:${String(m).padStart(2, '0')}:${s}` : `${m}:${s}`
}

export default function TrackPreview({ resolved }: { resolved: Resolved }) {
  const totalMs = resolved.tracks.reduce((sum, t) => sum + t.duration_ms, 0)
  const count = resolved.tracks.length

  return (
    <section
      aria-label="Preview"
      className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4"
    >
      <h2 className="truncate text-base font-semibold">{resolved.name}</h2>
      <p className="mb-3 text-sm text-zinc-400">
        {count} {count === 1 ? 'track' : 'tracks'} · {formatDuration(totalMs, true)}
      </p>
      <ol className="max-h-80 space-y-1 overflow-y-auto pr-1">
        {resolved.tracks.map((t) => (
          <li key={`${t.position}-${t.spotify_id}`} className="flex items-center gap-3 text-sm">
            <span className="w-6 shrink-0 text-right text-zinc-500 tabular-nums">{t.position}</span>
            {t.cover_url ? (
              <img
                src={t.cover_url}
                alt=""
                width={40}
                height={40}
                loading="lazy"
                className="h-10 w-10 shrink-0 rounded object-cover"
              />
            ) : (
              <div className="h-10 w-10 shrink-0 rounded bg-zinc-800" aria-hidden="true" />
            )}
            <div className="min-w-0 flex-1">
              <p className="truncate">{t.title}</p>
              <p className="truncate text-xs text-zinc-400">{t.artists.join(', ')}</p>
            </div>
            <span className="shrink-0 text-xs text-zinc-500 tabular-nums">
              {formatDuration(t.duration_ms)}
            </span>
          </li>
        ))}
      </ol>
    </section>
  )
}
