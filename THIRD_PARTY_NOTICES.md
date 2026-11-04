# Third-Party Notices

This file documents the third-party dependencies used in ScholarZone, their versions, and their respective licenses. All third-party code retains its original license. ScholarZone claims no ownership over these dependencies.

## Summary

| Category | Direct Dependencies | Transitive Dependencies (unique) |
|----------|-------------------|----------------------------------|
| Python (backend) | 26 | Not separately tracked (pip installs transitive) |
| JavaScript Production (frontend) | 5 | 13 |
| JavaScript Development (frontend) | 14 | 235 |

---

## Backend Dependencies (Python)

From `backend/requirements.txt` — declared direct dependencies with version specifiers:

| Package | Version Specifier | License | Source |
|---------|-------------------|---------|--------|
| annotated-doc | ==0.0.5 | MIT | PyPI |
| annotated-types | ==0.8.0 | MIT | PyPI |
| anyio | ==4.14.2 | MIT | PyPI |
| click | ==8.4.2 | BSD-3-Clause | PyPI |
| colorama | ==0.4.6 | BSD-3-Clause | PyPI |
| cryptography | >=42,<51 | Apache-2.0 / BSD-3-Clause | PyPI |
| fastapi | ==0.141.1 | MIT | PyPI |
| h11 | ==0.16.0 | MIT | PyPI |
| idna | ==3.18 | BSD-3-Clause | PyPI |
| pydantic | ==2.13.4 | MIT | PyPI |
| pydantic_core | ==2.46.4 | MIT | PyPI |
| starlette | ==1.4.1 | BSD-3-Clause | PyPI |
| typing-inspection | ==0.4.2 | MIT | PyPI |
| typing_extensions | ==4.16.0 | PSF-2.0 | PyPI |
| uvicorn | ==0.52.1 | BSD-3-Clause | PyPI |
| SQLAlchemy | >=2.0,<2.1 | MIT | PyPI |
| psycopg[binary] | >=3.2,<4 | LGPL-3.0-or-later | PyPI |
| httpx | >=0.27,<0.29 | MIT | PyPI |
| resend | unspecified | MIT | PyPI |
| python-dotenv | unspecified | BSD-3-Clause | PyPI |
| Pillow | unspecified | HPND | PyPI |
| beautifulsoup4 | unspecified | MIT | PyPI |
| PyYAML | >=6.0,<7 | MIT | PyPI |
| pypdf | >=5.0,<7 | BSD-3-Clause | PyPI |
| pdfplumber | >=0.11,<1 | MIT | PyPI |
| pytest | unspecified | MIT | PyPI |
| pytest-asyncio | >=0.23,<1 | Apache-2.0 | PyPI |

**Note:** Several packages use version ranges or "unspecified" in requirements.txt. The exact resolved versions depend on the resolver at install time. Run `pip freeze` in a clean environment for exact pinned versions.

---

## Frontend Dependencies (JavaScript/TypeScript)

### Direct Production Dependencies (from `frontend/package.json`)

| Package | Version | License | Source |
|---------|---------|---------|--------|
| motion | ^13.5.1 | MIT | npm |
| react | ^19.2.8 | MIT | npm |
| react-dom | ^19.2.8 | MIT | npm |
| react-router-dom | ^7.18.2 | MIT | npm |
| three | ^0.160.0 | MIT | npm |

### Direct Development Dependencies (from `frontend/package.json`)

| Package | Version | License | Source |
|---------|---------|---------|--------|
| @eslint/js | ^10.0.1 | MIT | npm |
| @testing-library/jest-dom | ^7.0.1 | MIT | npm |
| @testing-library/react | ^16.3.3 | MIT | npm |
| @testing-library/user-event | ^14.6.7 | MIT | npm |
| @types/react | ^19.2.17 | MIT | npm |
| @types/react-dom | ^19.2.3 | MIT | npm |
| @vitejs/plugin-react | ^6.0.4 | MIT | npm |
| eslint | ^10.8.0 | MIT | npm |
| eslint-plugin-react-hooks | ^7.1.1 | MIT | npm |
| eslint-plugin-react-refresh | ^0.5.3 | MIT | npm |
| globals | ^17.7.0 | MIT | npm |
| jsdom | ^29.1.1 | MIT | npm |
| vite | ^8.2.0 | MIT | npm |
| vitest | ^5.0.3 | MIT | npm |

### Transitive Production Dependencies (from `frontend/package-lock.json`, unique)

| Package | Version | License | Source |
|---------|---------|---------|--------|
| cookie | 1.1.1 | MIT | npm |
| framer-motion | 13.5.1 | MIT | npm |
| motion | 13.5.1 | MIT | npm |
| motion-dom | 13.5.1 | MIT | npm |
| motion-utils | 13.5.0 | MIT | npm |
| react | 19.3.0 | MIT | npm |
| react-dom | 19.3.0 | MIT | npm |
| react-router | 7.18.4 | MIT | npm |
| react-router-dom | 7.18.4 | MIT | npm |
| scheduler | 0.28.0 | MIT | npm |
| set-cookie-parser | 2.7.2 | MIT | npm |
| three | 0.160.0 | MIT | npm |
| tslib | 2.8.1 | MIT | npm |

### Transitive Development Dependencies (from `frontend/package-lock.json`, unique — 235 packages)

Key transitive development dependencies include: @babel/* (20 packages), @eslint/* (8 packages), @rollup/* (12 packages), @types/* (15 packages), @vitest/* (3 packages), eslint ecosystem (15 packages), vite/rolldown toolchain (25 packages), testing libraries (10 packages), and numerous utility packages. Full list available via `npm ls --json --all`.

**Note:** All transitive dependencies inherit their original licenses. The vast majority are MIT, BSD, Apache-2.0, or ISC licensed.

---

## External Services and APIs

The following external services are used by ScholarZone. They are not software dependencies but integrated services:

- **Neon PostgreSQL** — Managed PostgreSQL database hosting
- **Resend** — Transactional email service
- **GitHub Actions** — CI/CD platform
- **Vercel** — Static site hosting (current frontend deployment)
- **SnapDeploy** — Container hosting (backend API, evaluated)
- **Cloudflare Pages** — Static site hosting (evaluated alternative)

---

## Fonts and Design Assets

| Asset | License | Source |
|-------|---------|--------|
| Inter font | SIL Open Font License 1.1 | Google Fonts / self-hosted |
| Lucide React icons (if used) | ISC | lucide.dev |

---

## Data Sources

Scholarship data is aggregated from public official sources including:

- University websites
- Government education portals
- EU programme pages (Erasmus+, etc.)
- National scholarship agencies (DAAD, MEXT, GKS, etc.)

Factual scholarship data is not subject to copyright. Source attribution is maintained via `official_source` and `official_source_url` fields in the dataset.

---

## License Verification

To verify licenses independently:

```bash
# Python
pip install pip-licenses
pip-licenses --format=json --with-urls --with-description

# JavaScript
npm ls --json --all > npm-deps.json
# Or use license-checker:
npx license-checker --json --out licenses.json
```

---

*Generated on 2026-11-04 from `backend/requirements.txt`, `frontend/package.json`, and `frontend/package-lock.json`. Run the verification commands above for a complete, up-to-date list with resolved transitive versions and SPDX identifiers.*