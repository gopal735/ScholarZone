/**
 * Sanity check: the middleware's head rewriting must work against the real
 * index.html the app ships, not against a hand-written sample.
 *
 * HEAD's index.html is the functional React entry (it carries #root and the
 * module script). The working tree currently holds a much larger static page
 * with no React entry at all, which is why deployment is blocked - but the
 * middleware has to be correct against the version that actually serves the
 * catalogue.
 *
 * This asserts the shape the middleware depends on, and rewrites a copy of
 * HEAD's document to prove the substitution produces route-specific SEO.
 */
import { execFileSync } from 'node:child_process'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const HERE = dirname(fileURLToPath(import.meta.url))
const FRONTEND_ROOT = join(HERE, '..')
const REPO_ROOT = join(FRONTEND_ROOT, '..')

const headHtml = execFileSync(
  globalThis.process?.env?.GIT_EXECUTABLE || 'git',
  ['-C', REPO_ROOT, 'show', 'HEAD:frontend/index.html'],
  { encoding: 'utf8', maxBuffer: 8 * 1024 * 1024 }
)

// Order-tolerant and multi-line tolerant: the document writes its tags across
// several lines with data-sz-seo between the attributes, so a strict
// `name="x" content="y"` pattern does not match the real file.
const findTag = (html, predicate) =>
  [...html.matchAll(/<meta\b[^>]*>/gi)].find((match) => predicate(match[0]))

const setMeta = (html, attr, value) => {
  const tag = findTag(html, (candidate) => candidate.includes(attr))
  if (!tag) throw new Error(`missing meta ${attr}`)
  const next = tag[0].replace(/content="[^"]*"/i, `content="${value}"`)
  return html.replace(tag[0], next)
}

const setLink = (html, rel, href) => {
  const pattern = new RegExp(`<link\\b[^>]*\\brel="${rel}"[^>]*>`, 'i')
  const tag = html.match(pattern)
  if (!tag) throw new Error(`missing link ${rel}`)
  return html.replace(tag[0], tag[0].replace(/href="[^"]*"/i, `href="${href}"`))
}

const setTitle = (html, title) => {
  if (!/<title>[^<]*<\/title>/i.test(html)) throw new Error('missing title')
  return html.replace(/<title>[^<]*<\/title>/i, `<title>${title}</title>`)
}

const ORIGIN = 'https://scholarzone-fwzj.vercel.app'
const URL_UNDER_TEST = `${ORIGIN}/scholarships/14`

describe('the served index.html has the tags the middleware rewrites', () => {
  it('is the functional React entry, not a static shell', () => {
    expect(headHtml).toContain('id="root"')
    expect(headHtml).toMatch(/<script type="module"/)
  })

  it('carries title, canonical, description, og:url and JSON-LD', () => {
    expect(headHtml).toMatch(/<title>[^<]+<\/title>/i)
    expect(headHtml).toMatch(/<link rel="canonical" href="[^"]+"/i)
    expect(headHtml).toMatch(/name="description"/i)
    expect(headHtml).toMatch(/property="og:url"/i)
    expect(headHtml).toMatch(/application\/ld\+json/i)
  })

  it('preserves the Google verification token', () => {
    const token = headHtml.match(/name="google-site-verification" content="([^"]+)"/)?.[1]
    expect(token).toBeTruthy()
  })
})

describe('rewriting the head for a detail route', () => {
  const rewritten = (() => {
    let html = headHtml
    html = setTitle(html, 'A Wilhelmsen Foundation Scholarship · ScholarZone')
    html = setMeta(html, 'name="description"', 'Record-specific description.')
    html = setLink(html, 'canonical', URL_UNDER_TEST)
    html = setMeta(html, 'property="og:url"', URL_UNDER_TEST)
    return html
  })()

  it('points the canonical at the record instead of the homepage', () => {
    expect(rewritten).toContain(`<link rel="canonical" href="${URL_UNDER_TEST}"`)
    expect(rewritten).not.toContain(`<link rel="canonical" href="${ORIGIN}/"`)
  })

  it('points og:url at the record', () => {
    expect(rewritten).toContain(`content="${URL_UNDER_TEST}"`)
  })

  it('leaves the React entry and the design untouched', () => {
    expect(rewritten).toContain('id="root"')
    expect(rewritten).toMatch(/<script type="module"/)
    const stylesBefore = (headHtml.match(/<style/g) || []).length
    const stylesAfter = (rewritten.match(/<style/g) || []).length
    expect(stylesAfter).toBe(stylesBefore)
  })

  it('still carries the Google verification token after rewriting', () => {
    expect(rewritten).toMatch(/name="google-site-verification" content="[^"]+"/)
  })
})
