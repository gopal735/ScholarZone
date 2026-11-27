# Legacy import files (SUPERSEDED - NOT IMPORTABLE)

Every file in `legacy/import-files/` is retained for audit history only.

- Status: **SUPERSEDED**
- Importable: **No**
- Production use: **Prohibited**

These files are not importable and must never be read as canonical package input.
They contain obsolete counts (including the old 6-insert and 19-cycle claims),
unsupported lifecycle values, or duplicate plans that rewrote URLs or resolved
funding automatically.

The authoritative package files live in the parent package directory and are
enumerated in `final_reconciliation_manifest.json`. See
`legacy/import-files/manifest.json` for the per-file replacement mapping.
