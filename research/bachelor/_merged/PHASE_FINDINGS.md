# PHASE FINDINGS — closed status, MAECI/133, logo re-audit

Generated 2026-10-03. Nothing in `backend/config/` was read-modified or written.
No DB write, no commit, no push.

---

## 1. Why `do_add()` refuses closed records, and what the right route is

### The guard

`backend/app/jobs/scholarzone_maintenance.py` (`do_add()`):

```python
if status not in ("open", "upcoming"):
    rejected.append({"name": name, "reason": f"status={status or 'missing'}"})
    continue
```

The docstring states the intent: *"the status must be open or upcoming, so a closed
cycle researched late cannot be published as live."*

### That intent is correct. The guard should not be relaxed.

The reason is structural, not stylistic:

- `Scholarship.status` is `String(20)`, default `"open"`, indexed. It answers
  **"is this round open right now"** (`models.py:31-34`).
- `public_visibility_conditions()` gates the directory and the homepage counts.
  The router counts `status == "open"`, `"closing-soon"` and `"upcoming"`
  (`routers/scholarships.py:78-84`). A `closed` row is in `total` but in none of
  those three buckets.
- The auto-close stage already exists and already writes `closed`:
  `scholarzone_maintenance.py:989-1006` archives any row whose
  `deadline_date < today`, sets `is_archived=True`, and sets `status="closed"`
  with the comment *"Status is derived from the same date, so leaving it open
  would make a filter on status contradict the archive."*

So `closed` is a **real, supported, pipeline-produced state**. It is not a
validation artefact and not a data error. Relaxing the guard would let a stale
cycle into a public listing as live, which is precisely the failure the stage
was written to prevent.

### Decision: option C is false, option B is true, option A is wrong

These three awards are **not** "excluded because the pipeline is broken". They
are excluded because they are genuinely closed, and the correct handling is a
**historical/closed route that does not exist yet**.

| award | verified cycle state | factual status |
|---|---|---|
| MAECI IRE (`esteri.it`) | 2026-27 call closed 26 Mar 2026, 14:00 Italian time | `closed` |
| Heidelberg tuition-fee exemption | standing scheme, deadlines 15 Jan / 15 Jul; next window 15 Jan 2027 | `closed` |
| Monash K.C. Kuok | 2026 award closed 20 Jul 2026, "cannot be deferred" | `closed` |

All three are **recurring annual schemes**. None has ended. That distinction
matters: `closed` here means "this cycle has passed", not "this programme is
discontinued". A recurring scheme should re-enter the catalogue when its next
cycle opens — and the pipeline already anticipates that, because
`do_add`'s sibling stage reopens rows whose official facts report
`OPEN`/`UPCOMING` (`scholarzone_maintenance.py:2253-2256`).

### The correct route (recommended, not implemented)

These three should be parked in a **recurring-closed holding set**, not in
`new_scholarships.json`, and promoted to `open`/`upcoming` by the existing
reopen stage once the next cycle is published. That preserves factual status,
keeps them off public listings, and lets them return automatically.

**No code change was made.** Implementing a new route means editing
`do_add()` or adding a stage, which is a production change and outside this
phase's authority. Until that route exists, the honest state is:
**3 records researched, verified, and deliberately held out of insertion.**

### What this means for the counts

They are not "failed records". They are **complete records on deferred
insertion**. Counting them as BLOCKED understates the work done; counting them
as INSERT would publish a closed cycle. They get their own category.

---

## 2. MAECI vs id 133 — NOT a duplicate

### The claim being tested

My earlier note said b01 might duplicate LIVE id 133, because both sit on
registrable domain `esteri.it` and both are MAECI programmes.

### Evidence

`EXISTING_AWARDS.json` id 133:

```json
{ "id": 133,
  "name": "Invest Your Talent in Italy (IYT)",
  "degrees": ["Master's", "Postgraduate"],
  "status": "CLOSED",
  "hosts": ["investyourtalentapplication.esteri.it", "investyourtalent.esteri.it"] }
```

My b01 record:

```
name : Borse di studio offerte dal Governo italiano a studenti stranieri
        e italiani residenti all'estero (IRE)
url  : https://www.esteri.it/it/servizi-opportunita/opportunita/borse-di-studio/
        per-cittadini-stranieri/borsestudio_stranieri/
```

Fetched from that official page:

> "Il Ministero degli Affari Esteri e della Cooperazione Internazionale (MAECI)
> offre borse di studio in favore di **studenti stranieri e Italiani Residenti
> all'Estero (IRE)** per l'anno accademico 2026-2027 … La borsa di studio copre
> soltanto la frequenza di corsi sul territorio italiano. Il bando e la lista dei
> Paesi/altri territori beneficiari sono disponibili alla seguente pagina:
> https://studyinitaly.esteri.it/ListaBandi. Le candidature online devono
> pervenire tassativamente entro le ore 14.00 (ora italiana) del 26 marzo 2026."

### Verdict: distinct programmes

| | id 133 IYT | my b01 IRE |
|---|---|---|
| name | Invest Your Talent in Italy (IYT) | Borse di studio … residenti all'estero (IRE) |
| hosts | `investyourtalent.esteri.it`, `investyourtalentapplication.esteri.it` | `www.esteri.it` (MAECI borse di studio section) |
| legal basis | MAECI / ICE / Uni-Italia programme | **Legge 288/55** (cited on the page) |
| applicant portal | own IYT portal | **Study in Italy portal only** |
| eligibility | graduates / IYT track | foreign students **and Italians resident abroad** |
| degree level in DB | Master's, Postgraduate | not established |

They share only the sponsoring ministry and the `esteri.it` domain. Different
programme, different portal, different legal basis, different beneficiary
population. **Not a duplicate.**

### The real finding is worse, and it is not mine

The index contains a **third** row:

```json
{ "name": "Invest Your Talent in Italy (IYT) — MAECI / ICE / Uni-Italia scholarship programme",
  "state": "PENDING_INSERT",
  "hosts": ["investyourtalentapplication.esteri.it", "investyourtalent.esteri.it"] }
```

That row is already in committed `backend/config/new_scholarships.json` and it
**does** duplicate LIVE id 133 — same programme, same two hosts, near-identical
name. That is a pre-existing data defect in the catalogue, not something this
research introduced.

### Two actions, both outside this phase's authority

1. b01's rejection from the pool was a **false positive** caused by the
   domain-level filter (fixed below). It is a legitimate target.
2. The pre-existing IYT `PENDING_INSERT` duplicate should be dropped or
   downgraded to a REFRESH against id 133. **Requires editing
   `backend/config/new_scholarships.json` — not done.**

---

## 3. Logo re-audit — 14 rule-6 errors

Re-audited from the stored static evidence. No asset was substituted, nothing
was guessed, no production file was touched.

The rule-6 test measures the share of near-white SVG fills. That test **cannot
distinguish a white wordmark from a white background rectangle** behind a dark
wordmark, so the 14 findings split three ways:

### Reject now — 5 (would render as nothing on a light card)

| host | evidence |
|---|---|
| `uct.ac.za` | 96/97 fills near-white (99%) |
| `admissions.msu.edu` | 101/126 near-white (80%), served from `edge.sitecorecloud.io` |
| `ku.dk` | 1/2 near-white (50%), asset `ucph-logo-**da**.svg` |
| `studies.ku.dk` | 1/2 near-white (50%), asset `ucph-logo-**en**.svg` |
| `daad.de` | 2/4 near-white (50%), asset `logo-**light**.1I6xeyd5.svg` |

Action: `logo_override.url → null`. A missing logo is preferable to an
invisible one.

### Hold for a pixel check — 6

`cvut.cz`, `utoronto.ca`, `jku.at`, `liu.se`, `education.ki.se`,
`jeffersonscholars.org` — each is a **single 100% near-white fill**, which is
what a background rectangle looks like *and* what a solid white mark looks
like. Static analysis cannot separate those. A rasterised pixel check is
required before changing anything. **Not changed.**

### Likely false positives — 3

`dzs.cz` (`logo_msmt_**cerne**_rgb.svg` — "cerne" is Czech for *black*),
`flinders.edu.au` (`flinders-60th-**navy**-header.svg`),
`www2.daad.de` (`logo-small-**dark**.BjXioAOO.svg`).

An asset named "black" or "navy" whose fills read 64-75% near-white is almost
certainly a background rect being counted as a fill. These original findings
should be withdrawn once confirmed. **Not changed.**

### Net effect

- 14 findings reviewed, 5 rejected, 6 held, 3 flagged as probably wrong.
- **0 assets substituted. 0 guessed. 0 production edits.**
- Also noted: `utoronto.ca` and `future.utoronto.ca` would key two entries on
  different hosts for the same university logo.

Written to `_merged/white_logo_recheck.json`.

---

## 4. Index defect found and fixed — citation leakage

While verifying MAECI I found the duplicate index was **identifying awards by
their citations**.

`programme_details.json` `official.official_source_urls` is not a list of an
award's own pages. 312 of 368 records carry more than one entry, and 122 include
third-party URLs that merely appear in the record's prose. The index used that
array as identity, so:

| host | rows before | after |
|---|---|---|
| `anr.fr` | 126 | 4 |
| `www.sutd.edu.sg` | 127 | 2 |
| `bs.china-embassy.gov.cn` | 121 | 1 |

That produced **576 bogus "duplicate" pairs** in a cross-source check and one
wrong pool rejection (`nawa.gov.pl`). Worse, a host that broad would have caused
any future SUTD or ANR work to be rejected as a duplicate.

Fixed in `build_exclusion_index.js`: identity now comes only from the singular
fields (`official_source_url`, `application_link`, `catalogue_url`,
`official_updates_url`); the wide array is retained as `citation_urls` and is
never read by the duplicate filter.

Also added `shared_hosts` — hosts carrying 6+ unrelated awards (`daad.de` ×10,
`nawa.gov.pl` ×9, `kaist.ac.kr` ×6, `jsps.go.jp` ×6 …). `build_assignments.js`
now refuses to read breadth as identity and falls back to the name check, so
genuine duplicates are still caught by name rather than by website.

**Pool after the fix: 134 accepted / 27 rejected** (was 131/30). Europe 45,
US 33, Canada 19, Australia 15, Singapore 4, Malaysia 18.

All 23 records re-validated against the corrected index: still 23 complete,
0 errors, 20 INSERT + 3 REFRESH, 92 citations, 18 logos. Nothing regressed.

---

## 5. Slot drift — the "60-slot batch" framing was wrong

File-name slot prefixes no longer correspond to `ASSIGNMENTS.json` slots,
because earlier slots were reassigned when the pool was rebuilt. Comparing by
**host** instead of slot:

- 12 of the 23 completed records match a current pool row.
- 11 (`21`, `25`, `36`, `42`, `49`, `57`, `b01`, `b116`, `b70`, `b132`, `b133`… )
  have **no pool row at all** — they were produced from an earlier pool version.

So "37 remaining of the current 60" was computed against slot numbers that do
not describe these files. The authoritative remaining count is computed from
`_merged/remaining_targets.json`, keyed by host.