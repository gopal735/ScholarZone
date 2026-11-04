# Third-Party Notices

This file documents the third-party dependencies used in ScholarZone, their versions, and their respective licenses. All third-party code retains its original license. ScholarZone claims no ownership over these dependencies.

## Backend Dependencies (Python)

| Package | Version | License | Source |
|---------|---------|---------|--------|
| annotated-doc | 0.0.5 | MIT | PyPI |
| annotated-types | 0.8.0 | MIT | PyPI |
| anyio | 4.14.2 | MIT | PyPI |
| click | 8.4.2 | BSD-3-Clause | PyPI |
| colorama | 0.4.6 | BSD-3-Clause | PyPI |
| cryptography | >=42,<51 | Apache-2.0 / BSD-3-Clause | PyPI |
| fastapi | 0.141.1 | MIT | PyPI |
| h11 | 0.16.0 | MIT | PyPI |
| httpx | >=0.27,<0.29 | MIT | PyPI |
| idna | 3.18 | BSD-3-Clause | PyPI |
| pdfplumber | >=0.11,<1 | MIT | PyPI |
| Pillow | latest | HPND | PyPI |
| pydantic | 2.13.4 | MIT | PyPI |
| pydantic_core | 2.46.4 | MIT | PyPI |
| python-dotenv | latest | BSD-3-Clause | PyPI |
| PyYAML | >=6.0,<7 | MIT | PyPI |
| pypdf | >=5.0,<7 | BSD-3-Clause | PyPI |
| resend | latest | MIT | PyPI |
| SQLAlchemy | >=2.0,<2.1 | MIT | PyPI |
| starlette | 1.4.1 | BSD-3-Clause | PyPI |
| typing-inspection | 0.4.2 | MIT | PyPI |
| typing_extensions | 4.16.0 | PSF-2.0 | PyPI |
| uvicorn | 0.52.1 | BSD-3-Clause | PyPI |
| psycopg[binary] | >=3.2,<4 | LGPL-3.0-or-later | PyPI |
| pytest | latest | MIT | PyPI |
| pytest-asyncio | >=0.23,<1 | Apache-2.0 | PyPI |

## Frontend Dependencies (JavaScript/TypeScript)

### Production Dependencies

| Package | Version | License | Source |
|---------|---------|---------|--------|
| motion | ^13.5.1 | MIT | npm |
| react | ^19.2.8 | MIT | npm |
| react-dom | ^19.2.8 | MIT | npm |
| react-router-dom | ^7.18.2 | MIT | npm |
| three | ^0.160.0 | MIT | npm |

### Development Dependencies

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

## External Services and APIs

The following external services are used by ScholarZone. They are not dependencies in the traditional sense but are integrated via API calls:

- **Neon PostgreSQL** — Managed PostgreSQL database hosting
- **Resend** — Transactional email service
- **GitHub Actions** — CI/CD platform
- **Cloudflare Pages** — Static site hosting (alternative)
- **Vercel** — Static site hosting (current)
- **SnapDeploy** — Deployment platform (historical)

## Fonts and Design Assets

- **Inter font** (via CSS `@font-face` or CDN) — SIL Open Font License 1.1
- **Lucide React icons** (if used) — ISC License

## Data Sources

Scholarship data is aggregated from public official sources including:
- University websites
- Government education portals
- EU programme pages (Erasmus+, etc.)
- National scholarship agencies (DAAD, MEXT, GKS, etc.)

Factual scholarship data is not subject to copyright. Source attribution is maintained via `official_source` and `official_source_url` fields in the dataset.

---

*Generated on 2026-11-04. Run `pip-licenses` and `npm ls --json` for a complete, up-to-date list.*