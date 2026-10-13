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
 *    project, while the Vercel project additionally hosts the API under `/api`.
 *    Leaving the canonical there told every crawler to consolidate onto the
 *    mirror rather than the primary frontend, which is the same class of
 *    disagreement entry 1 describes.
 *
 * 3. `https://visionary-cactus-600b38.netlify.app` - the default this replaces.
 *    That was the Netlify project's default subdomain, and it is now dead: the
 *    host returns HTTP 404 and serves no document at all. It survived here only
 *    because it was written when the project was named that, and the site has
 *    since been published at `https://schollarzone.netlify.app`. The default
 *    and every artefact downstream of it named a host that does not resolve,
 *    so a crawler following a canonical was sent to a 404.
 *
 * The default is now the primary public frontend's published hostname. Unlike
 * entry 3, this one is the host that actually serves the site: verified live
 * as the domain the deployment answers on, and chosen over a per-deployment
 * hostname because a Netlify subdomain is renamed with the project. The
 * frontend is built with Vite base `/` and the Netlify SPA rewrite already
 * resolves that host at the domain root.
 */
export const CANONICAL_ORIGIN = (
  import.meta.env.VITE_CANONICAL_ORIGIN || 'https://schollarzone.netlify.app'
).replace(/\/$/, '')