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
 * The default was `https://gopal735.github.io/ScholarZone`. That host is the
 * stale legacy deployment: its branch was last built 2026-09-08, it serves no
 * SPA fallback (`/ScholarZone/scholarships` returns HTTP 404 there), and it is
 * not the identity-proven production project. With the default pointing at it,
 * every canonical link, Open Graph URL and BreadcrumbList item the production
 * site emits named a host that is not the production site, so a crawler was
 * instructed to consolidate onto a legacy origin and the two hosts disagreed.
 *
 * The default is now the canonical project's stable production alias. It is
 * chosen over the per-deployment hostname deliberately: the alias is held by the
 * deployment and survives every future build, while a deployment URL does not.
 * This is the project the GitHub App deploys from master, and it is the host the
 * app's own Vite base (`/`) and root vercel.json multi-service routing assume.
 */
export const CANONICAL_ORIGIN = (
  import.meta.env.VITE_CANONICAL_ORIGIN || 'https://scholarzone-fwzj.vercel.app'
).replace(/\/$/, '')