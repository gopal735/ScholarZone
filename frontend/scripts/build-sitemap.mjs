/**
 * Regenerates public/sitemap.xml from the public catalogue snapshot.
 *
 * Why this exists
 * ---------------
 * sitemap.xml was a hand-maintained file. It drifted from the catalogue in both
 * directions at once: it listed detail URLs for records that are no longer
 * public (closed, archived or quarantined), and it omitted public records that
 * do have a real detail page. Google therefore had 49 URLs pointing at pages
 * the app will not serve as public, and 198 public records with no URL at all,
 * while every route it did crawl returned the identical HTML shell and
 * declared the homepage as its canonical. That combination is what produces
 * "duplicate without user-selected canonical" and "soft 404" exclusions.
 *
 * The snapshot is the single source of truth here because it is generated from
 * the same public visibility contract the API enforces, and it was verified to
 * contain exactly the 516 records the catalogue reports as public - no more and
 * no fewer. Deriving the sitemap from it means the sitemap cannot drift again.
 *
 * Scope rules applied:
 *   - every scholarship detail URL comes from a record in the public snapshot
 *   - the record must exist and be public (the snapshot only holds public ones)
 *   - no closed, archived or quarantined record is included
 *   - no private, admin, per-user, login, saved or compare route is included
 *   - no query-parameter or filter variant is included
 *   - every URL is unique and on the canonical host
 *
 * lastmod is taken from each record's own last_verified_at when it is a real
 * ISO date. It is never invented: a record with no verifiable date is emitted
 * without a lastmod rather than with a fabricated one.
 */
import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { CANONICAL_ORIGIN } from '../src/services/canonicalOrigin.js'

const HERE = dirname(fileURLToPath(import.meta.url))
const SNAPSHOT = join(HERE, '..', 'public', 'scholarships-snapshot.json')
const OUTPUT = join(HERE, '..', 'public', 'sitemap.xml')

/** Routes that are real public pages and belong in the sitemap. */
const STATIC_ROUTES = [
  { path: '/', changefreq: 'daily', priority: '1.0' },
  { path: '/scholarships', changefreq: 'daily', priority: '0.9' },
  { path: '/countries', changefreq: 'weekly', priority: '0.7' },
]

/** Routes that must never appear, whatever the catalogue contains. */
const EXCLUDED_PREFIXES = [
  '/admin',
  '/dashboard',
  '/applications',
  '/login',
  '/register',
  '/saved',
  '/compare',
  '/api/',
]

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/

const escapeXml = (value) =>
  String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;')

const build = () => {
  const snapshot = JSON.parse(readFileSync(SNAPSHOT, 'utf8'))
  const records = Array.isArray(snapshot?.scholarships) ? snapshot.scholarships : []

  const seen = new Set()
  const entries = []

  const add = (path, { changefreq, priority, lastmod }) => {
    const loc = `${CANONICAL_ORIGIN}${path}`
    if (seen.has(loc)) return
    if (EXCLUDED_PREFIXES.some((prefix) => path.startsWith(prefix))) return
    seen.add(loc)
    entries.push({ loc, changefreq, priority, lastmod })
  }

  for (const route of STATIC_ROUTES) {
    add(route.path, route)
  }

  let withoutDate = 0
  for (const record of records) {
    const id = Number(record?.id)
    if (!Number.isInteger(id) || id <= 0) continue
    const raw = record?.last_verified_at
    const lastmod = typeof raw === 'string' && ISO_DATE.test(raw.slice(0, 10))
      ? raw.slice(0, 10)
      : null
    if (!lastmod) withoutDate += 1
    add(`/scholarships/${id}`, { changefreq: 'weekly', priority: '0.8', lastmod })
  }

  const body = entries
    .map((entry) => [
      '  <url>',
      `    <loc>${escapeXml(entry.loc)}</loc>`,
      entry.lastmod ? `    <lastmod>${entry.lastmod}</lastmod>` : null,
      `    <changefreq>${entry.changefreq}</changefreq>`,
      `    <priority>${entry.priority}</priority>`,
      '  </url>',
    ]
      .filter(Boolean)
      .join('\n'))
    .join('\n')

  const xml = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    body,
    '</urlset>',
    '',
  ].join('\n')

  writeFileSync(OUTPUT, xml, 'utf8')

  console.log(
    `[sitemap] ${entries.length} urls from ${records.length} public records ` +
    `(${withoutDate} without a verifiable lastmod) -> ${OUTPUT}`
  )

  if (entries.length < records.length + STATIC_ROUTES.length) {
    throw new Error(
      `[sitemap] expected at least ${records.length + STATIC_ROUTES.length} urls, ` +
      `produced ${entries.length}`
    )
  }
}

build()
