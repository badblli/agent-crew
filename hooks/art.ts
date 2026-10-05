// Pure SVG builders for the desktop and mobile surfaces (no `$` here; the terminal keeps text bars).

export type Gauge = { name: string; color: string; outer: number | null; inner: number | null; caption: string; note: string }

const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
const tone = (p: number) => (p >= 90 ? '#ef4444' : p >= 75 ? '#f59e0b' : '#22c55e')

function arc(cx: number, cy: number, r: number, pct: number, color: string, width: number): string {
  const c = 2 * Math.PI * r
  const used = Math.max(0, Math.min(100, pct)) / 100
  return (
    `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="#8882" stroke-width="${width}"/>` +
    `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${color}" stroke-width="${width}" stroke-linecap="round"` +
    ` stroke-dasharray="${(c * used).toFixed(1)} ${c.toFixed(1)}" transform="rotate(-90 ${cx} ${cy})"/>`
  )
}

/** Three dials side by side: outer ring = short window, inner ring = weekly. */
export function quotaDials(gauges: Gauge[], legend: string): string {
  const w = 360
  const h = 190
  const step = w / gauges.length
  const parts = gauges.map((g, i) => {
    const cx = step * i + step / 2
    const cy = 78
    const main = g.outer ?? 0
    return (
      `<g>` +
      `<circle cx="${cx}" cy="${cy}" r="58" fill="${g.color}14" stroke="${g.color}55" stroke-width="1.5"/>` +
      (g.outer !== null ? arc(cx, cy, 48, g.outer, tone(g.outer), 9) : '') +
      (g.inner !== null ? arc(cx, cy, 34, g.inner, g.color, 6) : '') +
      `<text x="${cx}" y="${cy + 6}" text-anchor="middle" font-size="20" font-weight="700" fill="${g.outer !== null ? tone(main) : '#999'}">${g.outer !== null ? `${Math.round(main)}%` : '—'}</text>` +
      `<text x="${cx}" y="${cy + 22}" text-anchor="middle" font-size="9" fill="#999">${g.inner !== null ? `◦ ${Math.round(g.inner)}%` : ''}</text>` +
      `<text x="${cx}" y="152" text-anchor="middle" font-size="13" font-weight="700" fill="${g.color}">${esc(g.name)}</text>` +
      `<text x="${cx}" y="168" text-anchor="middle" font-size="10" fill="#999">${esc(g.caption)}</text>` +
      `<text x="${cx}" y="182" text-anchor="middle" font-size="10" fill="${g.note.startsWith('!') ? '#ef4444' : '#999'}">${esc(g.note.replace(/^!/, ''))}</text>` +
      `<title>${esc(`${g.name}: ${g.caption} ${g.note}`)}</title></g>`
    )
  })
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h + 16}" font-family="system-ui,sans-serif">` +
    parts.join('') +
    `<text x="${w / 2}" y="${h + 12}" text-anchor="middle" font-size="9" fill="#888">${esc(legend)}</text></svg>`
  )
}

/** Poké-ball step track: done = filled ball, current = glowing ball, upcoming = hollow. */
export function stepTrack(labels: string[], at: number, color: string, isFailed: boolean): string {
  const gap = 46
  const w = Math.max(1, labels.length) * gap
  const balls = labels.map((label, i) => {
    const x = i * gap + gap / 2
    const state = i < at ? 'done' : i === at ? 'now' : 'next'
    const top = state === 'next' ? 'none' : isFailed && state === 'now' ? '#ef4444' : color
    return (
      (i > 0 ? `<line x1="${x - gap + 9}" y1="14" x2="${x - 9}" y2="14" stroke="${i <= at ? color : '#8885'}" stroke-width="2"/>` : '') +
      (state === 'now' ? `<circle cx="${x}" cy="14" r="12" fill="${top}" opacity="0.25"><animate attributeName="r" values="10;13;10" dur="1.6s" repeatCount="indefinite"/></circle>` : '') +
      `<path d="M ${x - 8} 14 A 8 8 0 0 1 ${x + 8} 14 Z" fill="${top}" stroke="#888" stroke-width="1"/>` +
      `<path d="M ${x - 8} 14 A 8 8 0 0 0 ${x + 8} 14 Z" fill="${state === 'next' ? 'none' : '#f5f5f5'}" stroke="#888" stroke-width="1"/>` +
      `<line x1="${x - 8}" y1="14" x2="${x + 8}" y2="14" stroke="#555" stroke-width="1.2"/>` +
      `<circle cx="${x}" cy="14" r="2.6" fill="#fff" stroke="#555" stroke-width="1"/>` +
      `<text x="${x}" y="38" text-anchor="middle" font-size="8.5" fill="${state === 'now' ? color : '#999'}" font-weight="${state === 'now' ? 700 : 400}">${esc(label)}</text>`
    )
  })
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} 44" font-family="system-ui,sans-serif">${balls.join('')}</svg>`
}

/** Banner: project title over a band of team-colour stripes. */
export function banner(title: string, subtitle: string, colors: string[], accent: string): string {
  const w = 360
  const stripe = w / Math.max(1, colors.length)
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} 64" font-family="system-ui,sans-serif">` +
    `<defs><linearGradient id="g" x1="0" x2="1"><stop offset="0" stop-color="${accent}" stop-opacity="0.35"/><stop offset="1" stop-color="${accent}" stop-opacity="0.05"/></linearGradient></defs>` +
    `<rect x="0" y="0" width="${w}" height="56" rx="10" fill="url(#g)" stroke="${accent}66"/>` +
    colors.map((c, i) => `<rect x="${i * stripe}" y="58" width="${stripe - 2}" height="5" rx="2" fill="${c}"/>`).join('') +
    `<text x="14" y="26" font-size="17" font-weight="800" fill="${accent}">${esc(title)}</text>` +
    `<text x="14" y="45" font-size="11" fill="#999">${esc(subtitle)}</text></svg>`
  )
}
