const VIDEO_ID = /^[A-Za-z0-9_-]{11}$/
const YOUTUBE_HOSTS = new Set(['youtube.com', 'music.youtube.com', 'm.youtube.com'])

/**
 * The 11-character video id from a YouTube / YouTube Music link, or null.
 * Accepts watch?v=ID (youtube.com, music.youtube.com, m.youtube.com), youtu.be/ID,
 * youtube.com/shorts/ID, and a bare id.
 */
export function videoIdFromLink(text: string): string | null {
  const input = text.trim()
  if (VIDEO_ID.test(input)) return input
  let url: URL
  try {
    url = new URL(/^https?:\/\//i.test(input) ? input : `https://${input}`)
  } catch {
    return null
  }
  const host = url.hostname.toLowerCase().replace(/^www\./, '')
  let id: string | null = null
  if (host === 'youtu.be') {
    id = url.pathname.split('/')[1] ?? null
  } else if (YOUTUBE_HOSTS.has(host)) {
    const shorts = /^\/shorts\/([^/]+)/.exec(url.pathname)
    id = url.pathname === '/watch' ? url.searchParams.get('v') : (shorts?.[1] ?? null)
  }
  return id !== null && VIDEO_ID.test(id) ? id : null
}
