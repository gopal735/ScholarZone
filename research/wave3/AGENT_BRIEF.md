# WAVE 3 BRIEF — official-logo hunt

Every scholarship record must carry the **official logo of the awarding body**.
The waves before you fixed the data and found most logos; what remains is the
long tail: records whose host had no audited override yet.

Your shard list is given in your prompt. Each shard file names one **host** and
the records on it. **One researched logo serves every record on that host**, so
research the host once and report it once — do not repeat the same work per
record.

Today is **2026-10-04**.

---

## 1. Rules (absolute)

1. **The asset must be served by the awarding body's own domain** — the shard's
   host, a subdomain of it, or a parent of it. A CDN that merely mirrors the
   file is **not** acceptable.
2. **The logo must belong to the body that awards the scholarship.** A university's
   mark on a ministry-awarded scholarship is a provenance error.
3. **No white-on-transparent wordmark.** It is invisible on a light card. Check
   SVG `fill` attributes, or render a PNG on white. If the only variant is white,
   hunt for a dark/coloured one; if none exists, report `null`.
4. **Probe the URL before reporting it.** Fetch the asset. A `webfetch` that
   returns *"Image fetched successfully"* (png/jpg/svg/webp) or *"Unsupported
   image format"* (ico) confirms **HTTP 200 + an image content type**. HTML in
   place of image bytes is a WAF interstitial or an error page — reject it.
5. **Never invent, guess or construct a URL.** An unprobed URL is a failure.
6. **Never use a third party**: aggregators, blogs, Wikipedia/Wikimedia, news,
   stock sites, imgur, pinterest, a screenshot, or a social-media CDN.
7. `null` is a **correct and acceptable** result. Say in `notes` exactly what you
   tried and why nothing acceptable exists. An honest null is worth more than a
   plausible wrong logo.
8. Never modify any repo file except your own output file.

## 2. Where to look, in order

1. Page markup: webfetch the awarding body's homepage and one programme page.
   Look for `<img>` whose `src` contains `logo`, `wordmark`, `brand`, `mark`;
   `og:image`; `<meta name="msapplication-TileImage">`; JSON-LD `logo`.
2. Common paths: `/favicon.ico`, `/apple-touch-icon.png`,
   `/apple-touch-icon-precomposed.png`, `/assets/logo.svg`, `/images/logo.png`,
   `/static/logo.svg`, `/sites/default/files/logo.svg`, `/wp-content/themes/*/logo.svg`,
   `/brand/logo.svg`, `/sites/default/files/logo.png`.
3. An official brand / press / media / "about us" page on the same domain.
4. If webfetch is blocked by a WAF (403, or an HTML interstitial), open the page
   with the Playwright tools and read the markup there. That is allowed and is
   how several stubborn sites were handled.

Prefer a full-colour wordmark or crest over a bare favicon when both exist.

## 3. Output

Write **one** file: `research/wave3/out/<your shard>.json`. Create the `out`
directory if needed. Write it as soon as you have finished a host, and rewrite
it after every host, so a timeout never loses more than one host.

```json
{
  "agent_id": "w3_01",
  "shard": "w3-01",
  "host": "massey.ac.nz",
  "today": "2026-10-04",
  "logo_override": {
    "url": "https://massey.ac.nz/.../logo.svg",
    "page_url": "https://massey.ac.nz/",
    "official_host": true,
    "alt_text": "Massey University",
    "validation_result": "verified",
    "validation_detail": "svg 11931+B, dark wordmark on white",
    "image_kind": "official_logo",
    "image_format": "svg",
    "verified_at": "2026-10-04T00:00:00+00:00",
    "host_evidence": "same_registrable_domain",
    "_award": "<the award name this logo belongs to>"
  },
  "target_ids": [615, 658, 659],
  "notes": "how you found it, what you probed, what you rejected and why"
}
```

- `logo_override` is `null` when nothing acceptable exists. Keep `notes` then.
- `image_kind`: `official_logo`, `official_government` (a ministry or state body)
  or `official_university`.
- `image_format`: `svg`, `png`, `jpg`, `webp` or `ico`.
- `host_evidence`: `same_registrable_domain`, or `official_social_asset` only when
  the bytes really are the body's own mark.

For a multi-host assignment, write one file per shard, named after the shard.

## 4. Report back

Two or three lines: how many hosts got a logo, how many are `null`, and for the
nulls the reason in one clause each.