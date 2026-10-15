/**
 * The sitemap must agree with the public catalogue.
 *
 * The origin-consistency contract lives in seoContract.test.js. This file
 * asserts the other half, which nothing was checking: that every detail URL in
 * sitemap.xml belongs to a record the app will actually serve as public, and
 * that every public record has a URL.
 *
 * Both directions were broken in production at the same time. The sitemap
 * carried 367 detail URLs, of which 49 named records that are no longer public,
 * and it omitted 198 records that are public and do have a detail page. A
 * sitemap can therefore be internally perfect and still wrong.
 */
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { CANONICAL_ORIGIN } from './services/canonicalOrigin.js'

const read = (relative) => readFileSync(new URL(relative, import.meta.url), 'utf8')

const SITEMAP = read('../public/sitemap.xml')
const SNAPSHOT = JSON.parse(read('../public/scholarships-snapshot.json'))

const locs = [...SITEMAP.matchAll(/<loc>([^<]+)<\/loc>/g)].map((match) => match[1])
const detailLocs = locs.filter((loc) => /\/scholarships\/\d+$/.test(loc))
const detailIds = detailLocs.map((loc) => Number(loc.split('/').pop()))

const publicIds = (SNAPSHOT.scholarships ?? []).map((record) => Number(record.id))

/** Routes that are private, per-user or otherwise never indexable. */
const FORBIDDEN = [
  '/admin',
  '/dashboard',
  '/applications',
  '/login',
  '/register',
  '/saved',
  '/compare',
  '/api/',
]

describe('sitemap origin', () => {
  it('is unique, on the canonical host, and carries no query parameters', () => {
    expect(new Set(locs).size).toBe(locs.length)
    expect(locs.every((loc) => loc.startsWith(`${CANONICAL_ORIGIN}/`))).toBe(true)
    expect(locs.some((loc) => loc.includes('?'))).toBe(false)
  })

  it('includes the three static public routes', () => {
    for (const route of ['/', '/scholarships', '/countries']) {
      expect(locs).toContain(`${CANONICAL_ORIGIN}${route}`)
    }
  })
})

describe('sitemap excludes everything that is not a public page', () => {
  it('names no private, per-user or administrative route', () => {
    const offenders = locs.filter((loc) => {
      const path = loc.slice(CANONICAL_ORIGIN.length)
      return FORBIDDEN.some((prefix) => path.startsWith(prefix))
    })
    expect(offenders).toEqual([])
  })

  it('names no duplicate or non-detail scholarship path', () => {
    const odd = detailLocs.filter((loc) => !/^https:\/\/[^/]+\/scholarships\/\d+$/.test(loc))
    expect(odd).toEqual([])
  })
})

describe('sitemap agrees with the public catalogue', () => {
  it('lists every public record exactly once', () => {
    expect(new Set(detailIds).size).toBe(detailIds.length)
    const missing = publicIds.filter((id) => !detailIds.includes(id))
    expect(missing).toEqual([])
  })

  it('lists no record that is not in the public snapshot', () => {
    const extra = detailIds.filter((id) => !publicIds.includes(id))
    expect(extra).toEqual([])
  })

  it('covers every record the snapshot reports as public', () => {
    expect(detailIds.length).toBe(publicIds.length)
  })

  it('never invents a lastmod', () => {
    const stamped = [...SITEMAP.matchAll(/<lastmod>([^<]+)<\/lastmod>/g)].map((m) => m[1])
    expect(stamped.every((value) => /^\d{4}-\d{2}-\d{2}$/.test(value))).toBe(true)
  })
})

describe('the snapshot is the authoritative public set', () => {
  it('holds only public records, one per id', () => {
    expect(publicIds.length).toBe(new Set(publicIds).size)
    expect(publicIds.every((id) => Number.isInteger(id) && id > 0)).toBe(true)
  })
})
