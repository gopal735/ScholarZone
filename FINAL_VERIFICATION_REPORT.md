# SCHOLARZONE — FINAL OFFICIAL-SOURCE VERIFICATION REPORT

Generated 2026-10-03. Every number in this report was observed in this run, from
the deployed public API, the deployed official pages, or the repository working
tree. Nothing is carried over from an earlier report.

Status: **COMPLETE WITH UNVERIFIED RECORDS**

---

## 1. Objective

For every publicly listed scholarship, establish whether its current information
is supported by the awarding body's own official source, and make the public
"Verified official source" claim derive from that determination rather than from a
historical boolean.

The task's own definition of 100% was adopted: *every public record has a final,
honest, auditable verification state*. Not: every record marked verified.

## 2. Verification state model

No new state machine was invented. The repository already had an authoritative
`verification_status` column and the frontend already read it on cards. What it
did not have was a rule preventing the legacy boolean from overriding it, or
keeping the derived counts honest.

| Stored `verification_status` | Public state | Public wording |
|---|---|---|
| `active` | VERIFIED | Verified official source / Verified listing |
| `needs_review`, `uncertain`, `failed` | CONFIRM_WITH_PROVIDER | Confirm with provider |
| `quarantined`, or `is_archived` | NOT_PUBLIC | (not shown) |

The derivation lives in one place and is pinned by tests
(`backend/tests/test_final_verification_audit.py::public_state`). `is_verified`
is retained as a column, because the public quality gate reads it, but it is now
written from the authoritative state and never read to produce a badge.

## 3. Initial baseline

At the start of this audit, from the deployed API:

| Measure | Value |
|---|---|
| Public total | 394 |
| `verified_active` | 372 |
| Not currently verified | 22 |
| `is_verified` true | 394 / 394 |
| Records with a quoted evidence row | 220 |
| Verified records with **no** evidence row | 172 |

The 172 is the pre-existing gap this audit was built to expose: `is_verified` was
true on every single record, so it could never distinguish anything.

## 4. Final public universe

The universe changed **during** this audit, by an action this audit did not
perform.

| Point in time | Public total | Verified active | Not verified |
|---|---|---|---|
| Audit start | 394 | 372 | 22 |
| Audit end | 386 | 364 | 22 |

Reconciliation: 394 − 9 + 1 = 386.

* **9 archived** during the audit, each with a stated lifecycle reason in
  `archived_reason`, all of the form `deadline passed on <date>`: ids 40 (ARES),
  215 (KOICA), 274 and 275 (BI), 294 (Czech Government — Developing Countries),
  317 (Asian Future Leaders), 344 (Nokia Foundation Fellow), 388 (NWO Embassy
  Science Fellowship), 416 (NAWA TOP200).
* **1 added**: id 620, CLP Future Conservationist Awards 2027
  (`verification_status = active`).
* The **set of 22 unresolved records is unchanged**. Every per-record decision
  below applies to the record as it stands today. This was verified by set
  comparison, not assumed.

No production write was made by this audit.

## 5. Final verified count

| Measure | Value |
|---|---|
| Public total now | 386 |
| Verified active now | 364 (94.3%) |
| Not currently verified now | 22 (5.7%) |
| **Projected** after the staging manifest is applied | **381 of 385 public** (98.96%) |
| Projected not verified | 4 |
| Projected retired out of the public universe | 1 |

The projected figures are arithmetic on the manifest, not an observed production
state. Production still reads 364/386 because §18 forbids unapproved writes.

## 6. Final unresolved count

| Category | Count |
|---|---|
| Resolved to VERIFIED in this pass | 17 |
| Resolved to NOT_PUBLIC (retired) | 1 |
| **Remain CONFIRM_WITH_PROVIDER** | **4** |
| Total | 22 |

The four, with the reason each is still unresolved, are 79, 113, 134, 140 and are
itemised in §7.

## 7. The 22-record resolution table

Every row was checked against the awarding body's own pages. "Official page
reachable" means an HTTP 200 was observed and the page text was read.

| ID | Record | Stored source | Reachable? | Outcome | Final state |
|---|---|---|---|---|---|
| 28 | Chevening Scholarship | chevening.org (homepage) | yes | Homepage replaced by the programme hub; deadline "6 October 2026 at 11:00 UTC" and FCDO funding confirmed verbatim | **VERIFIED** |
| 79 | Edinburgh Global Research Scholarship | ed.ac.uk funding hub | yes | "Global Research" appears nowhere on the current hub; the award survives only as a cross-reference on the college-studentships page. Amount, award count, eligibility and "Early February 2026" deadline are unsupported by any current official page | **CONFIRM_WITH_PROVIDER** |
| 113 | UGC JRF & RA for Foreign Nationals | ugc.gov.in (homepage) | yes | Scheme page confirms the general JRF scheme but publishes **no foreign-national variant**, and contradicts the stored figures (JRF 37,000/month for 2 years, SRF 42,000, tenure 5 years, against the stored 12,000–14,000, 16,000, 4 years). The record's identity claim and its money are both unsupported | **CONFIRM_WITH_PROVIDER** |
| 134 | International Talents @Unibo | bandi.unibo.it opportunities | yes (200), stored deep link 404 | Only the a.y. 2025/26 call exists, closed 30 May 2025. bandi.unibo.it search returns 6 "International Talents" items, newest 2025/26; no 2026/27 call published | **CONFIRM_WITH_PROVIDER** |
| 140 | Talent 4 UniTo | en.unito.it scholarships | **no — HTTP 403** | Seven official URLs attempted across four hosts; every one refused. apply.unito.it answers but has no Talents entry. No field change is justifiable and no retirement is either | **CONFIRM_WITH_PROVIDER** |
| 148 | NTU International Outstanding Graduate Student Scholarship | oia.ntu.edu.tw current-students page | yes | The award is **not on the stored page at all**. Found on NTU's own ISSS page; stored description ("Faculty Exchange Program") and duration were scraped from an unrelated entry | **VERIFIED** |
| 159 | IMD MBA Scholarships | imd.org/degree/mba/financing | yes | Confirmed current: "48% of students received a scholarship from IMD", "The MBA5 Scholarship - CHF 50K", open through 2026 | **VERIFIED** |
| 179 | Radboud Scholarship Programme | ru.nl/…/radboud-university-scholarship-programme | yes | Stored URL serves the generic hub. Programme page is `…/radboud-scholarship-programme`: "will reduce your tuition fee to EUR 2,771.-", 26 awards for 2027/2028, deadlines 31 Jan and 14 Feb 2027. Stored deadline matches exactly | **VERIFIED** |
| 214 | Yonsei International Companion Scholarship | graduate.yonsei.ac.kr scholarship02.do | yes | Page is short but genuine; confirms "Yonsei International Companion Scholarship", KRW 2,000,000 / 3,000,000 per semester. Title corrected to the official English wording | **VERIFIED** |
| 216 | GIST Government-Sponsored Scholarship | gist.ac.kr sub05/05020601 | yes | Confirmed: "All international graduate students are granted GIST scholarship without any separate application process", tuition 3,607,000 KRW/semester. Pointed at the international funding page | **VERIFIED** |
| 232 | DAAD Postgraduate Studies in Fine Art, Design, Film | www2.daad.de scholarship database | yes | Confirms the programme, "A monthly payment of 992 euros", 10–24 months. The application deadline is client-rendered and was not retrievable through six official URL variants, so **no deadline is asserted** | **VERIFIED** |
| 239 | MEXT Young Leaders Program (YLP) | studyinjapan.go.jp about-scholarships | yes | The stored URL is the generic overview. MEXT's own YLP page confirms "The YLP is one of the Japanese Government (MEXT) Scholarship Programs" with 2027-2028 guidelines. YLP *is* one of the seven MEXT types | **VERIFIED** |
| 272 | Aarhus University Danish State Scholarship | masters.au.dk scholarships-and-grants | yes | Confirmed, page revised 08.07.2026: automatic consideration at admission, no separate application, 15 Jan / 15 Sep cut-offs, non-EU only | **VERIFIED** |
| 320 | CGS Youth of Excellence at Fudan 2026 | iso.fudan.edu.cn c17458a754429 | yes | Page resolves and its title confirms the scheme and host; still listed among Fudan ISO's current prospective-student notices. Body is an image poster, so no amount is asserted | **VERIFIED** |
| 324 | CGS — China Embassy, Nassau 2026/2027 | bs.china-embassy.gov.cn/eng/sgxw/… | 301 → homepage | Same notice published by the embassy under `/eng/sggg/`: 1 bilateral place (full, incl. travel) + 3 unilateral (full, no travel), online via campuschina.org, deadline 14 Feb 2026, Category A / Agency 0441 | **VERIFIED** |
| 337 | University of Oulu tuition waivers + Early Bird | oulu.fi tuition fees page | yes | Confirms the schemes for 2027-2028 and, importantly, their limits: "No scholarships are available for first-year students" and "does not offer scholarships that cover 100% of the tuition fee" | **VERIFIED** |
| 338 | UEF Tuition Waivers (30% or 50%) | uef.fi tuition-fees-waivers | yes | Page updated 3 Aug 2026. Title's "(30% or 50%)" is the 2026 scheme; 2027 is a 30% Early Bird plus progress-based 30%. "Applicants cannot apply for full (100%) tuition waivers" | **VERIFIED** |
| 339 | University of Turku tuition waivers + Early Bird | utu.fi scholarships-before-2025 | yes (archive page) | Current page is scholarships-and-tuition-fees. "It is not possible to get a scholarship to cover the tuition fee for the first year, but the University offers an Early Bird discount of 2,000 EUR". Corrects the stored internal note: first-year scholarships withdrawn, **50% Merit Scholarship retained** for year 2 | **VERIFIED** |
| 340 | Åbo Akademi tuition fee scholarships | abo.fi scholarship programme | yes | "Scholarships mentioned for students admitted earlier are not available for those admitted in 2026 or later." Current scheme is fixed euro reductions: €4,000 year 1, €4,000 year 2 | **VERIFIED** |
| 341 | Finland Scholarship (National Programme for Master's) | studyinfinland.fi | yes | The awarding body states the programme does not exist: "Scholarships and tuition fee waivers in Finland are offered by individual universities. **There are no governmental scholarship programmes available.**" (page updated 04.06.2026) | **RETIRED** |
| 478 | Phi Kappa Phi Fellowship 2026 | phikappaphi.org/grants-awards/fellowship | yes | Confirms "40 Fellowships of $8,500 each, six at $15,000 each, and two at $35,000 each", "Dec. 15, 2026: Application portal opens", "April 15, 2027: National deadline". pkpf.org returns **HTTP 522** on both hosts | **VERIFIED** |
| 485 | CMU Africa Mastercard Foundation Scholars | cmu.edu/africa | 301 → africa.engineering.cmu.edu | Programme page confirmed: established 2016, full tuition plus travel and basic living expenses, admission-first route. Cycle 1 Oct / 15 Dec / 15 Jan for fall 2027 | **VERIFIED** |

### The four that remain unresolved, and exactly why

* **79 — Edinburgh Global Research Scholarship.** Not inaccessible: the page loads.
  The awarding body no longer publishes the award's terms. The string "Global
  Research" occurs zero times on the current international postgraduate funding
  hub and on the multi-regional awards page. The award name survives only in a
  cross-reference: "International students applying for studentships must also
  apply for an Edinburgh Global Research Scholarship or be able to demonstrate the
  availability of funds to meet the full overseas tuition fee." That sentence
  supports no amount, no award count, no eligibility rule and no deadline.
  Discontinuation is equally unproven, so the record is neither verified nor
  retired — retiring on absence would be a guess in the opposite direction.
* **113 — UGC JRF for Foreign Nationals.** Reachable and current, but it
  contradicts the record rather than supporting it. No page on ugc.gov.in
  publishes a foreign-national variant of the scheme, and the stored benefit
  figures are contradicted by the published ones. The record's central identity
  claim and its money are both unconfirmed. Correcting the URL does not make the
  rest of the record true, and the correction mechanism cannot write the benefit
  lists, so confirming it would assert something the source does not say.
* **134 — International Talents @Unibo.** The programme is real and the level in
  the record is right. There is no current call. The awarding body's own search
  returns 6 "International Talents" items, the newest being a.y. 2025/26, which
  closed on 30 May 2025. The stored "open" status is not supportable, so the
  record stays unresolved rather than being marked verified against a two-year-old
  call.
* **140 — Talent 4 UniTo.** The source is genuinely inaccessible. Seven official
  URLs across four hosts (en.unito.it, www.unito.it, unito.it, the Italian paths,
  and the tuition-fees path) all returned HTTP 403 to plain scripted fetches, and
  the recorded URL also returns 403 to a browser-style fetch. Only
  apply.unito.it answers, and it has no Talents entry. A fetch failure is not
  evidence, so nothing about this record could be confirmed and nothing about it
  could be corrected. It was neither verified nor retired.

## 8. Source migrations and replacements

Twelve records pointed at a URL that is technically live but states nothing about
the scholarship, or has moved. In every case the replacement is on the same
awarding body's own domain, and the record was re-read on the replacement rather
than having its URL swapped.

| ID | Old | New |
|---|---|---|
| 28 | `chevening.org` (homepage) | `chevening.org/scholarships/` |
| 148 | `oia.ntu.edu.tw/…/scholarships-6v27` | `isss.ntu.edu.tw/finances/scholarships/` |
| 179 | `ru.nl/…/radboud-university-scholarship-programme` | `ru.nl/…/radboud-scholarship-programme` |
| 216 | `gist.ac.kr/en/html/sub05/05020601.html` | `gist.ac.kr/iadm/html/sub04/0401.html` |
| 239 | `studyinjapan.go.jp/…/about-scholarships` | `mext.go.jp/en/policy/education/highered/title02/detail02/sdetail02/sdetail02/1374094.htm` |
| 324 | `bs.china-embassy.gov.cn/eng/sgxw/…` | `bs.china-embassy.gov.cn/eng/sggg/…` |
| 324 | — (application link) | `campuschina.org`, named by the notice itself |
| 339 | `utu.fi/en/study-at-utu/scholarships-before-2025` | `utu.fi/en/study-at-utu/scholarships-and-tuition-fees` |
| 485 | `cmu.edu/africa` (301) | `africa.engineering.cmu.edu/impact/mastercard-foundation-scholars.html` |
| 79 | `ed.ac.uk/student-funding/postgraduate/international` | `registryservices.ed.ac.uk/…/college-studentships` |
| 134 | `bandi.unibo.it/s/diri/bando-international-talents-unibo` (404) | the full a.y. 2025/26 call permalink |
| 113 | `ugc.gov.in` (homepage) | `ugc.gov.in/Fellowship/stu_Fellowship1` |

Title corrections applied where the stored title did not match the awarding
body's own wording: 179 ("Radboud Scholarship Programme"), 214 (official form
"Yonsei International Companion Scholarship"), 338 (drops "(30% or 50%)"), 340 (no
percentage waivers exist from 2026), 478 (labels the open Dec 2026 – Apr 2027
cycle).

### Two domain findings worth recording

* **pkpf.org returns HTTP 522** on both the bare and `www` hosts.
  phikappaphi.org is the Society's current official domain and every working
  official host is on it. Recorded as inaccessible, never as evidence.
* **15 awarding-body domains were missing from the curated official-domain set**
  in `scholarship_evidence.py`, so `classify_source` labelled their own pages
  "third party": imd.org, mo.ibrahim.foundation, mandelarhodes.org,
  tonyelumelufoundation.org, inlaksfoundation.org, ruffordsmallgrants.org, fes.de,
  kas.de, anr.fr, inria.fr, icssr.org, fnr.lu, harno.ee, hss.de, vlaanderen.be.
  None is a government, a university or a government portal, so the existing
  patterns could not match them. Each was read directly in this pass before being
  declared. Without this the "official domain requirement" is not machine-checkable
  for 20 of the 220 confirmations.

## 9. Lifecycle corrections

| ID | Finding | Action |
|---|---|---|
| 341 | The national Finnish master's scholarship does not exist; the awarding body says so on two dated pages. Not merged, not replaced — doctoral funding is a different programme and Kela study aid is not a scholarship | **Retired** (`NEVER-EXISTED`, 46th entry in `retired_records.json`) |
| 478 | Title labelled a cycle that has closed; the open cycle closes 15 April 2027 | Title corrected |
| 320 | The 2026 Youth of Excellence cycle is closed and Fudan ISO has published no 2027 notice as at 2026-10-03 | Verified as a published cycle; lifecycle note recorded in the evidence |
| 324 | The 2026/2027 application window closed on 14 February 2026; the stored status says "upcoming" | Verified; lifecycle defect recorded — `status` is not a field the correction mechanism may write |
| 134 | Stored status "open" against a call that closed 30 May 2025 | Left unresolved rather than verified |
| 9 records | Archived mid-audit on a passed deadline, each with a dated reason | Not this audit's action; reconciled in §4 |

The Rhodes Scholarship is **in the catalogue, currently verified, and unchanged by
this audit**. Its official page was not part of the 22 and no evidence in this
pass contradicts it. The prior report's "Board reportedly suspended it" is not an
official source and was not acted on.

## 10. Deadline corrections

Fourteen records stored a value in a deadline field that is not an application
deadline. In every case the value was **removed**, with the stored text quoted in
the correction's reason, and **no replacement was invented**.

| ID | Stored `deadline_display` | What it actually was |
|---|---|---|
| 325 | `is` | One word; the tail of a split sentence |
| 336 | `for accepting their study place.` | An obligation on an admitted student |
| 337 | `and a link to the payment portal…` | Payment instructions |
| 338 | `(end of December), the university has no obligation to return the tuition fee.` | A refund clause |
| 339 | `can also be 31 December.` | Fee-calendar text |
| 340 | `…specified in their admissions letter…` | An acceptance deadline |
| 342 | `for the discounted payment will be stated in…` | When a discount is quoted |
| 355 | `for submitting your online application). Obtaining certain documents…` | A mid-sentence fragment |
| 358 | *(an 11-sentence paragraph about editing course priorities)* | Help text, carrying a precision of `application_dead` |
| 392 | `It is not possible to` | A four-word fragment |
| 455 | `to pay tuition fees is 10 May.` | A tuition-payment deadline |
| 456 | `for studies is 15 January and the deadline for the application fee…` | Two deadlines in one field |
| 498 | `Alerts.` | A page heading |
| 520 | `for submission of internally moderated exam papers` | An internal departmental deadline |

`deadline_display` was cleared on all 14. `deadline_precision` was cleared on the
9 where the record also carried no date, and resolves through the shared deadline
semantics to `"unknown"` — the honest answer for a value that was never a date.

**Why this is a per-record decision and not a rule.** Three of these fragments
name a month — "end of December", "31 December", "10 May" — so
`classify_deadline_text` classifies them as `month`. The classifier reads words,
not meaning, and cannot tell a refund deadline from an application deadline. A
regex over the column would have deleted correct dates as well as false ones.
That is the reason the removal is an explicit entry naming the exact stored value.

The pipeline now supports this through the existing correction mechanism: a
`clear_fields` key naming deadline columns, with `deadline_precision` routed
through `deadline_semantics.coerce_deadline_precision`. It writes null only for
the fields it is given, so an absent key can never clear anything by accident.

## 11. Funding corrections

The audit did **not** force any funding label. The specific case named in the
brief, EPFL Excellence, was checked: it was not among the 22 unresolved and
carries no contradiction this pass can evidence, so it was left alone rather than
"corrected" from memory.

What was established instead:

* **The rule is now a test.** `fully_funded` requires a stated amount *and*
  `tuition_coverage` from the source. A fixed stipend with neither is not full
  funding; unknown coverage is not full funding.
* **The Finnish cluster, where the old labels were actively wrong.** Åbo
  Akademi's title claimed "Fee Waivers" for a scheme the awarding body says is no
  longer offered to students admitted from 2026; UEF's claimed "30% or 50%" is
  the 2026 scheme, not 2027. Both titles were corrected from the pages.
* **Turku's stored internal note was wrong in the opposite direction.** It claimed
  the whole waiver system was abolished. The current page retains a 50% Merit
  Scholarship for the second study year. The note was not rewritten, because
  `verification_notes` is not a field the correction mechanism may write; the
  correction was recorded against the URL instead and the finding is in the
  manifest.

Funding-label coverage across the catalogue: 4 records carry no funding label at
all (all in the 520–523 range). Recorded, not invented.

## 12. Duplicate decisions

No record was deleted, and no record was retired as a duplicate.

* 8 official pages are cited by more than one confirmation — MEXT's scheme table
  covers every MEXT programme, the Chevening timeline covers several Chevening
  awards. A shared page is expected for sibling records, so
  `official_source_url` uniqueness is the wrong test.
* The right test is a shared page **and** a shared name. No two confirmations
  share both.
* The MAECI "Invest Your Talent in Italy" / id 133 question: **not applicable.**
  That record is not in the public universe and is not part of the current
  unresolved set, so nothing was decided about it.
* One genuine prior duplicate decision stands unchanged: the retirement file holds
  46 entries, 3 flagged `NEVER-EXISTED`.

## 13. Logo audit

| Measure | Value |
|---|---|
| Public records with `image_kind = official_logo` | 370 of 386 |
| Public records with no logo | 16 |
| Hosts quarantined for unusable marks (`white_variant_only`) | 4 (ox.ac.uk, foreign.fulbrightonline.org, niied.go.kr, unige.ch), covering 7 records |
| **Quarantined hosts still carrying an asset** | **0** |
| Assets served from outside the awarding body's registrable domain | 12 |
| …of which are the awarding body's own delivery CDN | 10 |
| **Genuine third-party brand substitutions** | **0** |

The white-on-transparent problem is **resolved and explicitly quarantined**: the
four hosts are on the record in `unresolved_logos.json` with a reason code and a
detail, and none of their records carries a logo any more.

The 12 off-domain assets were each checked rather than pattern-matched, because a
registrable-domain test alone would have produced a false accusation:

* 10 are the awarding body's own asset on its own delivery host — `static.uq.net.au`
  for UQ, `gstatic.com/images/branding/googleg` for Google, `rotary.webdamdb.com`
  for Rotary, `edge.sitecorecloud.io`, and so on.
* id 372 uses `universitaly.it` for an Italian foreign-ministry programme.
  universitaly.it is the Italian government's own study-abroad portal — the same
  ministry, so the asset is official.
* id 118 uses `static.npfs.co` for a KIIT programme. `npfs.co` is a third-party
  account host. The awarding body's own page (`international.kiit.ac.in`) was
  fetched and **references that asset**, so it is the university's own published
  mark delivered from a vendor host — not a substituted brand.

**Two findings reported rather than fixed, because they are not logo
correctness:**

* **164 public records use an SVG logo.** A cross-origin SVG served without a
  `Cross-Origin-Resource-Policy` header is refused by browsers. Observed live:
  record 140's `unito.it` logo raised
  `ERR_BLOCKED_BY_RESPONSE.NotSameOrigin`, and two of the 22 probed logos (140,
  148) failed to load at all. The catalogue's own gate filters Wikimedia SVGs by
  content type but not CORP.
* **30 records carry an `image_evaluation_status` verdict that predates their own
  logo**, and **326 records are marked `no_official_image` while displaying an
  `official_logo`.** Every `no_official_image` verdict is dated 2026-09-30
  06:23–14:49; every accepted logo is dated 2026-09-30 17:25 onwards. The logo is
  the newer fact and the verdict is stale. This is contradictory evidence, not a
  false logo, and the image stage owns that field.

## 14. Verification evidence quality

| Measure | Value |
|---|---|
| Confirmations in the audited file | 220 |
| Written by this pass | 17 |
| **Ending mid-sentence at the 400-character bound** | **197** |
| Confirmations whose cited source is not an official domain | **0** (after §8) |
| Verified records with a quoted evidence row | 209 |
| **Verified records with only a timestamp** | **172** |

Two defects, both fixed where they can be and reported where they cannot:

1. **Mid-sentence truncation.** The reverify stage stored
   `evidence[:400]`, cutting mid-word. A note that stops mid-sentence makes a
   weaker claim than the one that was made — 197 of them did. The note builder now
   trims at the last sentence boundary inside the limit and says that it trimmed
   (`(truncated)` / `(extract) … (truncated)`). This repairs future writes; the
   197 existing fragments were not re-read and are reported, not rewritten.
2. **172 verified records rest on a timestamp alone.** They carry
   `last_verified_at` (92 in 2026-10, 80 in 2026-09) and 61 carry a `verified_by`,
   but no quoted finding exists anywhere in the repository's audited data. They
   publish "Verified official source" on the strength of a date. This audit did
   not re-check them; re-checking 172 official pages is a separate pass. The
   manifest labels every row `quoted_from_official_source` or `timestamp_only` so
   the two can never be read as the same thing.

## 15. Public UI trust semantics

Verified in a real browser against the deployed API, with the built bundle served
locally.

| Surface | Before | After | Evidence |
|---|---|---|---|
| Directory card badge | Element present but `display: none` in the grid | Visible on every card | `Ledger.css` hid `.scholarship-card__signals` on the grounds that the citation line "says the same thing". It does not — the citation line reports whether an **image** was captured, so a verified record with no logo said nothing about its verification, and an unresolved record never said "Confirm with provider" at all |
| Detail-page pill | `scholarship.verified ?? true` | `scholarship.verification_status === 'active'` | The boolean is true on all 386 records and **defaulted to true when absent**, so an unchecked record claimed "Verified listing" |
| Homepage statistics section | "Total opportunities 100" / "Verified active 100" | 386 / 47 / 122 / 364 | Two tiles read the paginated directory array — one page is 100 rows — directly beneath a trust bar reading 386 and 364. Two numbers for the same claim on one screen |
| Homepage verified count | `s.verified \|\| s.verification_status === 'active'` | `s.verification_status === 'active'` | The disjunct counted every record as verified |
| "Recommended" sort | `verified ?? true` | `verification_status === 'active'` | The comparison was always zero, so "recommended" meant no order at all |
| Directory meta description | "Every listing has a verified official source" | "Each listing states whether its details were re-checked against the awarding body's own page." | A blanket claim written into an indexed meta tag, asserting on four records exactly what each card withholds |

### Observed renderings

* **Unresolved record (id 140, `needs_review`, `is_verified = true`)** —
  card badge: **"Confirm with provider"**, visible; citation: "Not yet
  re-checked against the official page". Detail page pill: **"Confirm with
  provider"**. This is the §5 regression demonstrated end to end: the stale boolean
  no longer produces a badge.
* **Verified records** — card badge "Verified official source" plus
  "Verified Oct 3, 2026", matching `last_verified_at`.
* **Homepage** — trust bar and statistics section agree exactly:
  `386 / 47 / 364 / 122` in both.
* **Countries** — 47, from the API. No hand-written list.

### Other UI checks

* Responsive at 390×844: **no horizontal overflow** (`scrollWidth` 375 ≤
  viewport). Trust figures legible and correct at mobile width.
* Deep links: **116 of 386 detail pages return HTTP 500.** See §25.
* Console: the only errors observed were the blocked cross-origin SVG (§13) and
  the 500 detail responses. No new console errors or warnings from this audit.

## 16. Count reconciliation

```
Live now                     386 public
  = 364 verified active
  +  22 not verified

After the staging manifest   385 public
  = 381 verified
  +    4 confirm with provider
  +    1 retired out of the universe (386 − 1)

Manifest rows                386   (one per public record, no duplicates)
Actions    NO_CHANGE 364 · REFRESH 17 · UNVERIFIED 4 · RETIRED 1
States     VERIFIED 381 · CONFIRM_WITH_PROVIDER 4 · NOT_PUBLIC 1
```

Every component that publishes a trust figure now reads the same authoritative
count:

| Component | Source |
|---|---|
| `catalogue_counts["verification_status_active"]` | one SQL count |
| `catalogue_summary()["verified_active"]` | the same count |
| `/api/scholarships/stats` → `verified_active` | the same count |
| `HomeHero`, `HomeStats`, `ScholarZoneHero` | `stats.verified_active` |
| `HomePage` trust bar and statistics section | `stats.total` / `stats.verified_active` |
| `ScholarshipCard` badge | `verification_status` |
| `ScholarshipDetailsPage` pill | `verification_status` |
| `ScholarshipList` recommended sort | `verification_status` |

The directory has **no verification filter**, so there was none to reconcile.
`AdminPage` filters on `verification_status` and defaults an absent value to
`active`; that is an internal review tool, not a public trust surface.

## 17. Staging manifest

`verification/staging_manifest.json` — 386 rows, one per public record, each with
`id`, `name`, `action`, `public_verification_state`, `evidence_status`,
`field_changes`, `official_source`, `evidence`, `reason`,
`in_corrections_file`, `in_confirmations_file`, `in_retired_file`, `verified_at`.

Actions used: `INSERT` 0 · `REFRESH` 17 · `NO_CHANGE` 364 · `DUPLICATE` 0 ·
`RETIRED` 1 · `UNVERIFIED` 4 · `BLOCKED` 0.

No record is both VERIFIED and UNVERIFIED; a test asserts it.

Applied through the three existing mechanisms, no new stage:

| File | Before | After | Change |
|---|---|---|---|
| `record_corrections.json` | 151 | 177 | 16 value corrections + 14 deadline removals (10 of the 14 outside the 22) |
| `verification_confirmations.json` | 203 | 220 | 17 current checks with quoted evidence |
| `retired_records.json` | 45 | 46 | 1 `NEVER-EXISTED` |

`verification/apply_decisions.py` regenerates all three and the manifest
deterministically; running it twice produces byte-identical files.

## 18. Verification tests

`backend/tests/test_final_verification_audit.py` — **102 tests, all passing.**
Categories: source authority (official vs directory), source outcomes (404, 403,
522, redirect, moved URL), current verification state, verified-count
reconciliation on a real in-memory database, deadline semantics, funding
semantics, duplicate decisions, lifecycle, logo provenance, public trust
semantics in the frontend source, detail-endpoint reachability, final inventory,
and evidence provenance.

Existing suites extended:

* `test_record_corrections.py` — three new cases: `clear_fields` may name only
  deadline columns, an unknown `clear_fields` key is refused, and no entry may
  both clear and rewrite a field.
* `test_visibility_count_consistency.py` — this suite forced the production
  visibility gates on process-wide and never restored them, so every suite that
  ran afterwards saw a catalogue of zero. Six failures in `test_counting_api.py`
  with a minimum repro of
  `pytest tests/test_visibility_count_consistency.py tests/test_counting_api.py`.
  Fixed by restoring the environment and clearing the settings cache on teardown.

Freshly run, not carried over:

```
verification-specific suites
  tests/test_final_verification_audit.py
  tests/test_record_corrections.py
  tests/test_retired_records.py
  tests/test_source_classification.py
  tests/test_visibility_count_consistency.py
  tests/test_counting_api.py
  → 202 passed

all of backend/tests
  → 4332 passed, 2 skipped, 13 warnings in 152.16s
```

## 19. UI / browser verification

Browser: Chromium via Playwright, 1280×1024 and 390×844, against the deployed API
proxied onto the page's own origin so the bundle behaves as it does in
production.

* Homepage trust bar and statistics section agree: 386 / 47 / 364 / 122.
* Card badge visible on 12 of 12 cards sampled; unresolved record renders
  "Confirm with provider".
* Detail pill correct for both states.
* No horizontal overflow at 390px.
* Frontend builds clean (`vite build`, 520 modules, 241ms) and lints with
  0 errors (1 pre-existing `exhaustive-deps` warning in `HomePage.jsx`).

## 20. Repository-wide test status

**4332 passed, 2 skipped, 0 failed, 13 warnings.** The historical "3520 passed"
figure was not reused.

The suite has order-dependent behaviour in at least one place: `pytest-randomly`
is installed and the full run is not reproducible file-for-file. The pollution
found in §18 was fixed. Any future failure should be re-run in isolation before
being attributed to code.

## 21. Known Match 2.0 unrelated failures

**The reported 58 Match 2.0 failures did not reproduce.** The full suite passes
with zero failures, including `tests/test_matching_v2.py`,
`tests/test_matching_api.py`, `tests/test_matching_engine.py`,
`tests/test_matching_taxonomy.py` and the `TestMatchRegression` cases in
`tests/test_counting_api.py`.

No Match 2.0 file was read, modified or fixed by this audit. Those test files and
their supporting modules are untracked in the working tree and appear in
`git status` as `??` — they are present and they pass.

Match 2.0 therefore does not block the verification task, and this report does not
claim the repository is green *despite* it: it is green, and the 58 failures were
not observed at any point in this run.

## 22. Protected-file audit

| File | Status |
|---|---|
| `backend/app/services/deadline_semantics.py` | untouched |
| `backend/app/services/scholarship_enrichment.py` | untouched |
| `backend/app/services/image_validator.py` | untouched |
| `backend/app/services/scholarship_image_verifier.py` | untouched |
| `backend/app/services/official_page_discovery.py` | untouched |
| `backend/app/models.py` | untouched |
| `backend/app/database.py` | untouched |
| `backend/seed.py` | untouched |
| `backend/research_output/*.json` | untouched |
| `POST /api/scholarships/match`, `MatchProfileRequest` | untouched |
| Match frontend (`components/match/`, `pages/MatchPage.jsx`, match hooks/services) | untouched |

### Files this audit changed

| File | Change |
|---|---|
| `backend/app/jobs/scholarzone_maintenance.py` | `clear_fields` deadline removal in `do_correct`; sentence-boundary note builder; `row.verified` → `row.is_verified` |
| `backend/app/services/scholarship_evidence.py` | 15 official awarding-body domains added to the curated set |
| `backend/config/record_corrections.json` | +26 entries; `_rules` documents `clear_fields` |
| `backend/config/verification_confirmations.json` | +17 entries |
| `backend/config/retired_records.json` | +1 entry |
| `backend/tests/test_final_verification_audit.py` | **new**, 102 tests |
| `backend/tests/test_record_corrections.py` | allowlist + 3 new cases |
| `backend/tests/test_visibility_count_consistency.py` | environment restore on teardown |
| `frontend/src/Ledger.css` | removed the rule hiding the card badge |
| `frontend/src/components/ScholarshipList.jsx` | recommended sort reads the authoritative state |
| `frontend/src/pages/HomePage.jsx` | verified count and statistics tiles read the authoritative state |
| `frontend/src/pages/ScholarshipDetailsPage.jsx` | pill reads the authoritative state, no `?? true` |
| `frontend/src/pages/ScholarshipsPage.jsx` | blanket verification claim removed from the meta description |
| `verification/` | **new**, this audit's tooling and artefacts |

### Files modified in this working tree by another participant

`.gitignore`, `backend/app/main.py`, `backend/app/routers/scholarships.py`,
`backend/tests/test_final_hardening.py`,
`backend/tests/test_router_name_resolution.py`, `frontend/src/App.jsx`,
`frontend/src/components/Navigation.jsx`, and `backend/tests/test_counting_api.py`
(all untracked). These are not this audit's work and are listed for completeness
only. No schema change was made by this audit.

## 23. Database mutation status

**No production database write was performed.** No INSERT, UPDATE, DELETE or
bulk operation. Every read was through the public API or the read-only projection.

All changes are staged as data files plus a manifest, awaiting an owner-approved
run of the existing stages:

```
python -m app.jobs.scholarzone_maintenance correct
python -m app.jobs.scholarzone_maintenance retire
python -m app.jobs.scholarzone_maintenance reverify
```

## 24. Git status

Nothing staged, nothing committed, nothing pushed.

```
$ git ls-files -m
.gitignore
backend/app/jobs/scholarzone_maintenance.py
backend/app/main.py
backend/app/routers/scholarships.py
backend/app/services/scholarship_evidence.py
backend/config/record_corrections.json
backend/config/retired_records.json
backend/config/verification_confirmations.json
backend/tests/test_final_hardening.py
backend/tests/test_record_corrections.py
backend/tests/test_router_name_resolution.py
backend/tests/test_visibility_count_consistency.py
frontend/src/App.jsx
frontend/src/Ledger.css
frontend/src/components/Navigation.jsx
frontend/src/components/ScholarshipList.jsx
frontend/src/pages/HomePage.jsx
frontend/src/pages/ScholarshipDetailsPage.jsx
frontend/src/pages/ScholarshipsPage.jsx
```

19 modified files; 10 of them are this audit's, 8 are another participant's, and
`backend/tests/test_counting_api.py` is untracked. `git diff --check` reports no
whitespace errors (only CRLF line-ending notices). All pre-existing scratch and
research artefacts remain untouched.

## 25. Known limitations

Stated as limitations, not as conclusions.

1. **172 verified records rest on a timestamp with no quoted evidence.** They
   publish "Verified official source" on the strength of a date. Not re-checked in
   this pass. The manifest labels them `timestamp_only`.
2. **116 of 386 detail pages return HTTP 500.** Root cause identified exactly:
   `ScholarshipDetailResponse` declares `eligibility`, `benefits`, `coverage`,
   `requirements`, `documents`, `required_documents` and `application_method` as
   arrays, and 117 rows hold a bare JSON string in one or more of them.
   `ScholarshipResponse` declares no array fields, so the list endpoint renders
   them correctly — the record looks fine as a card and fails only on its own page.
   `verification/detail_shape_repairs.json` holds the exact repair for all 117
   (field, current value, repaired value, per record), every one validated against
   the response schema, with zero unexplained cases. Applying it is a data write
   and is deferred under §18. **10 of the 22 audited records are among them.**
3. **The deployed site is behind this working tree.** The live bundle still
   publishes "100 Total opportunities" and "100 Verified active", hides the card
   badge, reads `verified ?? true` on the detail page, and carries the blanket
   meta-description claim. All four are fixed here and not yet deployed.
4. **30 records carry an image-evaluation verdict that predates their own logo**,
   and 326 are marked `no_official_image` while displaying a logo. Reported, not
   rewritten — the image stage owns that field.
5. **164 public logos are cross-origin SVGs** and are refused by browsers unless
   the host sends a CORP header. One observed in practice (id 140).
6. **No current deadline could be established for id 232 (DAAD).** The date is
   rendered client-side and was not retrievable through six official URL variants.
   No date was inferred, so the stored deadline fields were left untouched and the
   record is verified on programme and award economics only.
7. **Four records publish a stale lifecycle `status`** (320, 324, 134 and others):
   a closed cycle marked `upcoming`, or `open` against a closed call. `status` is
   not a field the correction mechanism may write, so these are recorded rather
   than corrected.
8. **One prior claim in the brief was contradicted by the official source and no
   action was taken on it:** the brief said the Rhodes Scholarship was reportedly
   suspended. That is not an official source. The record is currently verified and
   unchanged.
9. **The public universe moved during the audit** (§4). Everything is reconciled
   against 386, but any owner applying the manifest should re-pull first.
10. **`frontend/dist` was rebuilt** from the working tree. It is git-ignored and
    was not a tracked artefact.

## 26. Final exact metrics

| Metric | Value |
|---|---|
| Public records at audit start | 394 |
| Public records at audit end | 386 |
| Verified active, live, now | 364 (94.30%) |
| Not currently verified, live, now | 22 (5.70%) |
| Resolved to verified in this pass | 17 |
| Resolved to retired | 1 |
| Remaining unverified after this pass | 4 |
| Projected public total after applying the manifest | 385 |
| Projected verified after applying the manifest | 381 (98.96%) |
| Records with a quoted official-source evidence row | 209 verified + 17 new confirmations |
| Records with a timestamp only | 172 |
| Value corrections staged | 16 |
| Deadline removals staged | 14 |
| Retirements staged | 1 |
| Official-source URLs migrated | 12 |
| Awarding-body domains added to the official set | 15 |
| Confirmations citing a non-official source | 0 |
| Logo hosts quarantined for unusable marks | 4 (7 records), 0 still carrying an asset |
| Genuine third-party logo substitutions | 0 |
| Detail endpoints returning HTTP 500 | 116 of 386 |
| Records with a validated, exact shape repair | 117 |
| Verification tests | 102 passed |
| Verification-adjacent suites | 202 passed |
| Full backend suite | 4332 passed, 2 skipped, 0 failed |
| Match 2.0 failures observed | 0 |
| Production database writes | 0 |
| Commits | 0 |
| Pushes | 0 |

---

## Status: COMPLETE WITH UNVERIFIED RECORDS

All 386 public records have a final, audited verification state, and 381 of 385
will be currently verified once the staged manifest is applied by an owner.

Four records remain `CONFIRM_WITH_PROVIDER`, and each remains unresolved for a
reason that is stated, sourced and specific:

* **79** — the awarding body no longer publishes the award's terms.
* **113** — the live page contradicts the record's identity claim and its funding.
* **134** — no current call exists to verify the record against.
* **140** — the awarding body refuses every request from seven official URLs.

None of them was marked verified. An inaccessible source is not a verified
source, and the absence of a page is not proof that a programme ended.
