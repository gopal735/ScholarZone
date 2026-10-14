"""Build an index-only version of scholarzone_maintenance.py = HEAD + list-shape only.

Starts from the working-tree file (which contains BOTH the list-shape release and
an unrelated concurrent verification workstream) and reverses exactly the seven
concurrent hunks. The result is asserted to contain no concurrent residue, then
written out so `git diff --no-index` can produce a list-shape-only patch for
`git apply --cached`.

The working tree is never modified.
"""
import subprocess, sys, pathlib

SRC = pathlib.Path('backend/app/jobs/scholarzone_maintenance.py')
text = SRC.read_text(encoding='utf-8')
original_len = len(text)

# (label, exact_text_to_remove, replacement)
REVERSALS = [
    ("R1 import re (only used by the note-truncation helper)",
     "import re\n",
     ""),

    ("R2 NOTE_LIMIT / _SENTENCE_END / _note_text helper",
     '''#: The widest prefix of a verification note that fits ``verification_notes``. The
#: column is a bounded Text, so a long finding is shortened rather than refused.
NOTE_LIMIT = 400

_SENTENCE_END = re.compile(r"[.!?][\\"')\\]]?(\\s|$)")


def _note_text(value: object) -> str:
    """Shorten a verification finding to whole sentences.

    A note that has been cut mid-sentence reads as though the finding itself stops
    there, which is a different and weaker claim than the one that was made. 197 of
    the stored confirmations were cut mid-word this way. When a finding is longer
    than the column it is therefore trimmed at the last sentence boundary inside
    the limit, and the fact that it was shortened is stated rather than left for a
    reader to notice.
    """
    text = " ".join(str(value or "").split())
    if not text:
        return ""
    if len(text) <= NOTE_LIMIT:
        return text
    window = text[: NOTE_LIMIT + 1]
    ends = [m.end() for m in _SENTENCE_END.finditer(window)]
    body = text[: ends[-1]].strip() if ends else ""
    if not body:
        # No sentence finishes inside the limit. Keeping the clipped text would
        # publish a half-sentence as the finding, so the text is cut at the last
        # word that fits and the note says it is an extract.
        return f"(extract) {text[:NOTE_LIMIT].rsplit(' ', 1)[0].strip()} (truncated)"
    return f"{body} (truncated)"


''',
     ""),

    ("R3 _note_text call site -> original 400-char slice",
     'int(entry["id"]): _note_text(entry.get("evidence"))',
     'int(entry["id"]): (entry.get("evidence") or "").strip()[:400]'),

    ("R4 row.verified -> row.is_verified fix (unrelated verification bug)",
     '''                # The mapped column is `is_verified`. Assigning `verified` set an
                # unmapped attribute on the ORM object, so a record confirmed by
                # this stage could still carry is_verified = False and be hidden by
                # the public quality gate while its own status says active. The
                # boolean is legacy and must not create the badge, but it must not
                # contradict the authoritative state either.
                row.is_verified = True
''',
     '                row.verified = True\n'),

    ("R5 deadline_semantics import",
     "        from app.services.deadline_semantics import coerce_deadline_precision\n",
     ""),

    ("R6 deadline-removal comment + clearable tuple",
     '''        # A deadline that is not a deadline is removed rather than repaired.
        #
        # Extraction occasionally lands on a sentence about something else
        # entirely - a fee-payment window, a tuition-refund clause, an
        # enrolment instruction - and stores that fragment as the deadline. The
        # value is then worse than empty: it is confidently wrong, and it is
        # wrong in a way an applicant would act on. Removing it is the only safe
        # edit, because the correct date is a separate finding that has to arrive
        # with its own evidence; inventing one here would replace a false claim
        # with a false claim.
        #
        # `deadline_precision` is NOT NULL, so it cannot be cleared to null. It
        # falls back through the same deadline semantics every other record uses,
        # which resolves an absent statement to "unknown" - the honest answer.
        clearable = ("deadline_display", "deadline_date", "deadline_precision")

''',
     ""),

    ("R7 explicit clear_fields removal block",
     '''                # Removal is explicit and per field. `clear_fields` is a list
                # rather than a null so "this correction says nothing about the
                # deadline" and "this correction removes the deadline" cannot be
                # confused: an absent key must never clear a field by accident.
                requested_clear = entry.get("clear_fields")
                if isinstance(requested_clear, list):
                    for field in clearable:
                        if field not in requested_clear:
                            continue
                        if not _is_column(Scholarship, field):
                            continue
                        value = (
                            coerce_deadline_precision(None)
                            if field == "deadline_precision"
                            else None
                        )
                        if getattr(row, field, None) == value:
                            continue
                        setattr(row, field, value)
                        changed.append(field)
''',
     ""),
]

ok = True
for label, target, replacement in REVERSALS:
    n = text.count(target)
    if n != 1:
        print(f"ABORT {label}: expected exactly 1 occurrence, found {n}")
        ok = False
        continue
    text = text.replace(target, replacement, 1)
    print(f"reversed  {label}  (-{len(target) - len(replacement)} chars)")

if not ok:
    sys.exit("Refusing to continue: an anchor was ambiguous.")

# ---- assertions: no concurrent residue may remain ----
RESIDUE = [
    "import re", "NOTE_LIMIT", "_SENTENCE_END", "_note_text",
    "deadline_semantics", "coerce_deadline_precision", "clearable",
    "requested_clear", "row.is_verified = True",
]
print()
bad = [r for r in RESIDUE if r in text]
if bad:
    sys.exit(f"ABORT: concurrent residue still present: {bad}")
print("no concurrent residue remains")

# ---- assertions: list-shape release must be intact ----
REQUIRED = [
    '"repair_list_columns", "purge_closed"',
    '"repair_list_columns": ()',
    "def do_repair_list_columns() -> dict:",
    "from app.services.list_columns import ListColumnShapeError, normalize_list_column",
    '"coverage": "coverage"',
    '"application_method": "application_method"',
    "skipped_bad_shape",
    "_is_json_column(Scholarship, column)",
    '"repair_list_columns": do_repair_list_columns,',
    "normalize_list_column",
]
missing = [r for r in REQUIRED if r not in text]
if missing:
    sys.exit(f"ABORT: list-shape release incomplete, missing: {missing}")
print("list-shape release intact:", len(REQUIRED), "anchors present")

# text columns must no longer claim coverage/application_method
if '"coverage": "text"' in text or '"application_method": "text"' in text:
    sys.exit("ABORT: stale text mapping for a JSON list column still present")
print("stale text mappings removed")

out = pathlib.Path('C:/Users/GopaL/AppData/Local/Temp/kilo/mnt_head_plus_listshape.py')
out.write_text(text, encoding='utf-8', newline='\n')
print()
print(f"working file {original_len} chars -> reconstruction {len(text)} chars")
print("wrote", out)

head = subprocess.run(
    ['git', 'show', 'HEAD:backend/app/jobs/scholarzone_maintenance.py'],
    capture_output=True, text=True, encoding='utf-8', check=True).stdout
base = pathlib.Path('C:/Users/GopaL/AppData/Local/Temp/kilo/mnt_head.py')
base.write_text(head, encoding='utf-8', newline='\n')
print("wrote", base)
