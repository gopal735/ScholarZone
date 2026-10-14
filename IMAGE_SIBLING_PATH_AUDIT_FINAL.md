# IMAGE SIBLING PATH AUDIT — FINAL

**Read-only audit. No fix applied. No production touched. No dispatch, no stage run, no repair.**

Scope: `image_discovery_orchestrator._is_non_logo_stored`, reached through `--stage images --logo-only`
→ `do_images` → `ImageCoverageRunner(logo_only=True)` → `ImageDiscoveryOrchestrator.run()`.

---

## Headline: my Phase 7B risk claim about this path is **DISPROVEN**

In Phase 7B I told you this sibling path "can still destroy an accepted `program_image`" and recommended
fixing it next. **That was wrong**, and real execution is what disproved it. The destructive branch is
**unreachable**: it raises `AttributeError` before it can clear anything.

This is the second time in this project that a statically plausible claim collapsed under execution
(`do_add` "could not clear id 130" was the first). Both were found by running the real code.

---

## 1. Exact clear predicate — **PROVEN**

`image_discovery_orchestrator.py` line 229, module-level function:

```python
def _is_non_logo_stored(session, scholarship_id) -> bool:
    scholarship = session.get(Scholarship, scholarship_id)
    if scholarship is None or not scholarship.image_url:
        return False
    # An unset kind is treated as non-logo: ...
    return (scholarship.image_kind or "") not in LOGO_IDENTITY_KINDS
```

`ACCEPTED_IMAGE_KINDS` is **never consulted**. Proven by isolated test: for every accepted kind that is
not an identity mark — `program_image`, `official_banner` — the predicate returns `True`, i.e. "this
stored image is unwanted artwork". For `official_logo`, `official_government`, `official_university` it
returns `False`.

**So the predicate's intent is still wrong**, exactly as `9ff021b` found for `do_logos`.

## 2. But the branch never executes — **PROVEN**

| fact | evidence |
|---|---|
| `_is_non_logo_stored` exists only at module level | AST: `def _is_non_logo_stored (line 229) args=['session','scholarship_id']` |
| No class has a method of that name | AST: `methods on classes named *_non_logo_stored*: NONE` |
| The sole call site uses `self.` | line 658: `self._is_non_logo_stored(session, scholarship_id)` |
| Observed failure | `AttributeError: 'ImageDiscoveryOrchestrator' object has no attribute '_is_non_logo_stored'` |
| The failure is swallowed | line 674 `except Exception` → `status=ERROR`, `session.rollback()`, `return result` |

Reaching line 658 requires `not dry_run` **and** `status != NO_TRUSTWORTHY_IMAGE` **and** `logo_only`.
When those hold, the call raises, the transaction rolls back, and the run reports ERROR having written
nothing.

## 3. Reproduction results — 23/23 isolated tests pass

`backend/tests/test_sibling_logo_only_probe.py` (throwaway worktree, never committed). Only the network
is substituted — the page fetcher, page discovery and validator are stubbed; **the decision, the
destruction primitive and the write are the shipped code**.

| question asked | answer | classification |
|---|---|---|
| `program_image` → cleared by a real logo-only run? | **No.** Record byte-identical before/after | **PROVEN** |
| `official_banner` → cleared? | **No.** Unchanged | **PROVEN** |
| non-accepted artwork → cleared? | **No.** Unchanged (the crash precedes any write) | **PROVEN** |
| `official_logo` / `_government` / `_university` → preserved? | **Yes**, unchanged | **PROVEN** |
| `--dry-run` destroys nothing | Confirmed | **PROVEN** |
| `_is_non_logo_stored` judges `program_image` non-logo? | **Yes** | **PROVEN** |
| `_clear_stored_image` would destroy all 6 fields? | **Yes**, if reached | **PROVEN** |
| run outcome when the branch is reached | `status=ERROR`, `persisted=False`, `error` names `_is_non_logo_stored` | **PROVEN** |

## 4. Is this the same semantic defect class as `9ff021b`? — **PARTIALLY**

| | `9ff021b` (`do_logos`) | sibling (`images --logo-only`) |
|---|---|---|
| Membership test ignores `ACCEPTED_IMAGE_KINDS` | yes | **yes — same class** |
| Accepted image destroyed merely for not being a logo | yes | **intended yes, actually no** |
| Reachable in production | yes, proven on id 14 | **no — crashes first** |
| Consequence | image deleted, record left empty | **nothing written; run errors** |
| Blast radius | records the host has a logo override for | would be every discovered logo |

Same **predicate** defect. Different **reachability**: `do_logos` was live and destructive; this path is
dead code.

## 5. The real risk here is an arming trap, not a live defect — **PROVEN**

`_clear_stored_image` is unguarded and would null all six image fields. If someone "fixes" only the
`AttributeError` — changing `self._is_non_logo_stored(...)` to `_is_non_logo_stored(...)` — the
destructive branch becomes reachable **with the wrong predicate still in place**, and accepted
`program_image` / `official_banner` records would start being cleared on the next
`images --logo-only` run.

A test pins this: `test_the_intent_would_still_be_wrong_if_the_call_were_repaired` asserts the predicate
still lacks `ACCEPTED_IMAGE_KINDS` and that the call site still reads `self._is_non_logo_stored`. If
either changes, the test fails and forces a re-audit.

**Any repair must change the predicate and the call site together.**

## 6. Exposure — **PROVEN low**

`--logo-only` is a `workflow_dispatch` **input** in `verification-cron.yml`
(`${{ github.event.inputs.logo_only == 'true' && '--logo-only' || '' }}`), not a cron argument. The
schedule `7 */12 * * *` never passes it. So the path requires a deliberate manual dispatch, and today it
would only produce errors.

## 7. Classifications

**PROVEN**
- The predicate ignores `ACCEPTED_IMAGE_KINDS` and classifies `program_image` / `official_banner` as unwanted.
- No method named `_is_non_logo_stored` exists; the only call site uses `self.`.
- A real `logo_only` run reaching that line raises `AttributeError`, rolls back, and writes nothing.
- No stored image — accepted or not — is modified by `--stage images --logo-only` today.
- `_clear_stored_image` would destroy all six fields if reached.
- The `except Exception` converts the crash into `status=ERROR`, so the failure is recorded but not raised.

**DISPROVEN**
- My Phase 7B claim that this path "can still destroy an accepted `program_image`" / "`official_banner`".
- The assumption that the sibling behaves like `do_logos` in production impact.

**PLAUSIBLE BUT UNPROVEN**
- That the path has never been dispatched. No `images --logo-only` run appears in the recent run history
  I inspected, and no `maintenance.*` audit label corresponds to it, but I cannot prove absence.
- That the feature was *intended* to replace stored artwork with a discovered logo. The in-code comment
  ("A stored programme photo must not survive a logo-only sweep") says so, but intent is not proof.

**UNKNOWN**
- Whether Vercel/build behaviour or some manual action explains why no `logo_only` run is on record.
- Whether anyone has already noticed the dead branch.

## 8. Recommendation (not applied)

Fix the sibling **only** as a single atomic change, and in this order:

1. Change the predicate to treat `ACCEPTED_IMAGE_KINDS` as protected, mirroring `9ff021b` exactly.
2. Fix the call site in the same commit (`self.` → module function).
3. Add the real-stage regression this audit used, so the branch is exercised for the first time under test.
4. Only then is `--stage images --logo-only` safe to dispatch.

Doing step 2 alone converts a harmless dead branch into a live image destroyer. That is the specific
mistake this document exists to prevent.