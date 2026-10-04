# BUILD PROVENANCE — PR FINAL

| | |
| --- | --- |
| PR | **https://github.com/gopal735/ScholarZone/pull/5** — OPEN, not merged |
| Branch | `release/build-provenance-only` |
| Head | `f9b4778` |
| Base | `origin/master` `ddcd9c3662f4d3257d4f92e335fa7422e99ebdeb` |
| merge-base(master, head) | `ddcd9c3` — equals the master tip |
| Scope | **10 files, +1265 / −61** |
| Nature | infrastructure only — **no product behaviour change** |
| Frontend | **untouched** |
| Database / Neon / scholarship data | **untouched** |

Labels: **PROVEN**, **VALIDATED**, **UNKNOWN**, **BLOCKED**.

---

## 1. What was extracted, and what was deliberately left behind

Source: `origin/rc/revision-provenance`, which sits on **3 commits** above its own
base `3ee434c`:

| Commit | Subject | Taken? |
| --- | --- | --- |
| `00bc39d` | fix: scope mentor chip dedup to one record | **NO — Mentor** |
| `255ca97` | fix: identify the deployed build from an embedded artefact, not the runtime env | **YES** |
| `d050d30` | build: run provenance generation from install as well as build | **YES** |

**PROVEN.** The whole branch was **not** merged or cherry-picked. A naive
`git diff master..branch` appeared to show Mentor contamination, but that was an
artefact: the branch is based on `3ee434c`, so already-landed master work shows as
reversed. The correct measure is the branch's own commits, and the Mentor commit
is excluded.

**PROVEN.** Before porting, I verified that **every** modified file was unchanged
on master since `3ee434c` (0 commits touched `main.py`, `vercel.json`,
`deploy.yml`, `test_final_hardening.py`, `test_vercel_migration.py`). Taking them
verbatim therefore could not revert newer work.

## 2. Files in this PR

| File | Change |
| --- | --- |
| `backend/app/build_provenance.py` | **new** — build-time embed + runtime read, 40-hex validation, fail-closed |
| `backend/scripts/embed_build_revision.py` | **new** — build-time entry point; exit status is the build's exit status |
| `backend/scripts/release_identity_gate.py` | **new** — deployment↔artefact identity gate |
| `backend/app/main.py` | `build_revision()` reads the artefact only; `/health` 503 on a corrupt artefact; startup logs instead of refusing to boot |
| `vercel.json` | **root** — backend service gains `buildCommand` + `installCommand` |
| `.github/workflows/deploy.yml` | gate compares full `${github.sha}`; `{7,40}` → `{40}`; `EXPECTED_SHORT` removed |
| `backend/tests/test_build_provenance.py` | **new** — provenance regression suite |
| `backend/tests/test_release_identity_gate.py` | **new** — 21 gate tests, mostly negative |
| `backend/tests/test_final_hardening.py` | updated |
| `backend/tests/test_vercel_migration.py` | updated |

## 3. Provenance chain, end to end

**BUILD.** `VERCEL_GIT_COMMIT_SHA` → validated as **exactly 40 lowercase hex** →
written to `backend/app/build_revision.txt`, which lives *inside* the package and
therefore ships with the artefact. A platform build with no usable SHA raises, and
the build fails.

**RUNTIME.** `build_revision()` calls `read_embedded_revision()` and nothing else.
No environment variable, no request header, no query parameter, no branch name,
no deployment URL. **VALIDATED** by test: with `VERCEL_GIT_COMMIT_SHA` and
`SCHOLARZONE_BUILD_REVISION` both set to a *different* commit at runtime, the
reported revision is still the embedded one.

**FAIL CLOSED.** Missing artefact **in production** → `/health` returns **503**
with `Build identity unavailable`, resolved separately from the database check so
a packaging fault is never misdiagnosed as a database outage. Corrupt artefact →
always raises. Missing artefact **off-platform** → `dev`, so tests still run.

## 4. Health contract

| Case | Result | Label |
| --- | --- | --- |
| 40-char SHA embedded | returned verbatim, full length | **PROVEN** |
| 12-char value in artefact | refused; `/health` 503 | **PROVEN** |
| Malformed value in artefact | refused | **PROVEN** |
| Missing artefact, production | `/health` 503 | **PROVEN** |
| `VERCEL_GIT_COMMIT_SHA` set at runtime | ignored | **PROVEN** |
| `SCHOLARZONE_BUILD_REVISION` set at runtime | ignored (support removed) | **PROVEN** |
| Startup with bad artefact | logs the fault, **still boots** | **PROVEN** |

**Deliberate decision:** a *missing* artefact is tolerated off-platform and a
*corrupt* one is not. Failing to boot on a packaging fault would convert a
diagnosable problem into a full outage; degrading a corrupt artefact to `dev`
would let a broken deployment answer `ok` on the one endpoint whose job is to
notice.

## 5. Deploy gate — strengthened, not weakened

| | Before | After |
| --- | --- | --- |
| Comparison | `CURRENT = EXPECTED_SHORT` (12 chars) | `CURRENT = EXPECTED_REVISION` (`${{ github.sha }}`) |
| Accepted shape | `^[0-9a-f]{7,40}$` | `^[0-9a-f]{40}$` |
| Prefix acceptance | yes | **no** |

**PROVEN.** `EXPECTED_SHORT` is gone; the gate now demands the full SHA on both
sides. No relaxation was introduced.

## 6. Release identity gate

`backend/scripts/release_identity_gate.py` binds **deployment id**, **deployment
URL**, **`gitSource.ref`**, **`gitSource.sha`** and the **runtime health SHA**,
requiring exact equality on two full 40-character SHAs.

It rejects, each with a dedicated negative test:

| Rejection | Label |
| --- | --- |
| an alias standing in for a deployment | **PROVEN** |
| a production response when a **preview** was requested | **PROVEN** |
| a prefix SHA, in the reported revision or the platform record | **PROVEN** |
| the wrong deployment id | **PROVEN** |
| a deployment of a different expected commit | **PROVEN** |
| an expected SHA that is itself a prefix | **PROVEN** |
| a payload with no URL, no git source, or a non-object shape | **PROVEN** |

**Design note.** Health is read from the deployment the **platform** named, not
from the URL the caller supplied, so a substituted alias cannot influence the
result. The verification half is a **pure function** over two fetched payloads
with no network call inside it — which is what allows the rejections to be
asserted directly rather than inferred from a live deployment.

**One implementation change I made deliberately.** My first version
`.strip().lower()`-normalised the reported revision, so an uppercase or
whitespace-padded value was silently accepted. Two of my own tests caught it. A
gate that normalises what the artefact claimed is weaker than one that demands
the exact form, so the normalisation was removed. The gate is now **stricter**
than the version I first wrote.

## 7. Test evidence

| Suite | Result |
| --- | --- |
| `test_build_provenance.py` + `test_release_identity_gate.py` | **66 passed** |
| Full backend — untouched master `ddcd9c3` | 4988 passed / 8 failed / 11 skipped / 13 warnings / 1 error |
| Full backend — this branch | **5055 passed** / 8 failed / 11 skipped / 13 warnings / 1 error |
| Delta | **+67 passed. Zero new deterministic failures.** |

**PROVEN.** The 8 failures are the known pre-existing set, all in
`test_neon_migration.py`; the 1 error is
`scripts/artifact_smoke_test.py::test_endpoint`. **No test was weakened,
skipped, or xfailed.**

**PROVEN — test isolation.** The real `backend/app/build_revision.txt` is
**never** written by the suite: tests redirect `provenance.ARTIFACT` to
`tmp_path` via `monkeypatch.setattr`. Verified by confirming the file is still
absent from the source package after a full run — the failure mode PHASE 11 warns
about, checked rather than assumed.

## 8. Build hook — what is and is not proven

**PROVEN (structural).** `vercel.json`'s backend service declares
`buildCommand: python scripts/embed_build_revision.py`, and
`test_build_provenance.py` asserts that wiring
(`assert "embed_build_revision.py" in backend.get("buildCommand", "")`).
`installCommand` also runs it, so the identity is embedded even on a path that
skips the build step.

**PROVEN (this matters).** Both Vercel projects declare **Root Directory `.`**,
so Vercel consumes the **repository-root** `vercel.json`. A `backend/vercel.json`
also exists in the repo as a supplementary backend-scoped file, but it is not the
file the root-deployed project reads. **This PR modifies the root file.**

**BLOCKED — real execution.** Whether the command actually executes under this
project's deployment path cannot be shown without a real deployment, and
deployments are rate-limited. Current live evidence of the *pre-fix* state: project
`Build Command` is `None` and the deployment `Builds` block shows the root build at
`[0ms]`. That evidence is why this PR exists; confirming the fix requires a
deployment.

## 9. Relationship to the other open provenance PRs

**PROVEN — three PRs now overlap.** This was found while opening this one and is
material to whoever merges.

| PR | Branch | Files | Notes |
| --- | --- | --- | --- |
| **#3** | `release/final-mentor-production-reconciliation` | 14 | provenance **plus Mentor `evidence.py`**, plus **frontend** `anonymousProbe.js` + test, plus `.gitignore` |
| **#4** | `release/build-provenance-identity` | 7 | provenance only, but does **not** touch the **root** `vercel.json` |
| **#5 (this)** | `release/build-provenance-only` | 10 | provenance only; root `vercel.json`; adds the identity gate and its tests |

**VALIDATED by configuration inspection.** #3 and #4 modify `backend/vercel.json`
rather than the repository-root `vercel.json`. Because both projects deploy with
Root Directory `.`, the root file is the one Vercel reads, so on their current
contents **the build hook would not be wired** — the exact failure this work
exists to fix. Confirming that requires a deployment (**BLOCKED**), so this is
labelled VALIDATED rather than PROVEN.

**Recommendation:** merge one provenance PR, not three. This one is the only one
that (a) touches the authoritative `vercel.json`, (b) contains no Mentor or
frontend changes, and (c) ships a tested deployment identity gate. PRs #3 and #4
should be closed in favour of it rather than merged alongside.

## 10. Remaining risk

- **BLOCKED.** Real build execution is unproven until a deployment runs.
- **VALIDATED.** If the build hook does *not* execute, the consequence is a
  **loud** failure, not a silent one: `/health` returns 503 and `deploy.yml`
  fails. The failure mode is downtime with a clear cause, which is the correct
  trade against publishing a deployment that cannot name its own commit.
- **UNKNOWN.** Whether Vercel's Services preset honours a per-service
  `buildCommand` at all in this configuration. The previous deployment's `[0ms]`
  root build is consistent with the build step never having been configured;
  whether configuring it is sufficient is what the first deployment will answer.