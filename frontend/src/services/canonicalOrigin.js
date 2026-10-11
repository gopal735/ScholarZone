/**
 * Canonical origin for SEO output.
 *
 * Canonical URLs, the sitemap host, robots.txt and JSON-LD must all agree, and
 * they must not be changed ahead of production validation. The current canonical
 * host is therefore the default here, so building today produces byte-identical
 * SEO output. Setting VITE_CANONICAL_ORIGIN in that project's environment
 * switches every consumer to a different host in one place rather than by
 * editing four pages.
 *
 * The defaults, in order:
 *
 * 1. `https://gopal735.github.io/ScholarZone` - the stale legacy deployment.
 *    Its branch was last built 2026-09-08, it serves no SPA fallback
 *    (`/ScholarZone/scholarships` returns HTTP 404 there), and it is not the
 *    identity-proven production project. With the default pointing at it,
 *    every canonical link, Open Graph URL and BreadcrumbList item the production
 *    site emits named a host that is not the production site, so a crawler was
 *    instructed to consolidate onto a legacy origin and the two hosts disagreed.
 *
 * 2. `https://scholarzone-fwzj.vercel.app` - the previous default. That project
 *    is still live and still serves the frontend, but it is a mirror: the
 *    frontend's automated production deploy from `master` runs on the Netlify
 *    project `visionary-cactus-600b38` (PR #32 fixed its Vite base path for
 *    exactly that reason), while the Vercel project additionally hosts the API
 *    under `/api`. Leaving the canonical there told every crawler to
 *    consolidate onto the mirror rather than the primary frontend, which is the
 *    same class of disagreement entry 1 describes.
 *
 * The default is now the primary public frontend's stable production host. It is
 * chosen over the per-deployment hostname deliberately: the alias is held by the
 * deployment and survives every future build, while a deployment URL does not.
 * The frontend is built with Vite base `/` and the Netlify SPA rewrite already
 * resolves that host at the domain root.
 */
export const CANONICAL_ORIGIN = (
  import.meta.env.VITE_CANONICAL_ORIGIN || 'https://visionary-cactus-600b38.netlify.app'
).replace(/\/$/, '')