# TejaratYar 4.0 Trade Ready — Changelog

## Front-end (self-contained, trader-first)
- Removed the external Tailwind CDN dependency; rewrote the UI as a self-contained design system with the local Vazirmatn font. The app now renders even fully offline.
- Added guided intake with demo scenarios, inline validation and a toast notification system (replaced `alert()`).
- Secure job access: token sent via the `X-Job-Token` header; file downloads happen through fetch + Blob so the token never appears in the URL / logs.
- Added "resume last job" persistence via `localStorage` so a refresh no longer loses a running/completed dossier.
- Added searchable, filterable and sortable tables for the Longlist, scoring matrix and source log.
- Added an interactive Landed-Cost calculator, a side-by-side supplier comparison view, and a print-ready executive summary.
- One-click copy of RFQ emails; live progress screen with elapsed timer and stage timeline.
- Clear action-plan guidance instead of a confusing empty result when the honest output is `Not Ready`.

## Back-end (safe, low-risk)
- Service and dossier metadata version bumped to `4.0-trade-ready`.
- Header-based token auth is covered by an automated test (query-token fallback preserved for compatibility).
- The honest evidence-first core (20-supplier gate, No Recommendation when short, unverified claims capped) is unchanged.

---

# TejaratYar 3.0 Professional — Changelog

## Branding and positioning

- Rebranded product from an import assignment tool to **تجارت‌یار / TejaratYar**.
- Removed all instructor, course, classroom and academic-project references.
- Added professional product positioning: Trade Decision Intelligence.
- Added creator credit: **Setayesh Jafari / ستایش جعفری**.

## Professional interface

- New executive headline and report-owner/project fields.
- Added organization, dossier title and report-purpose inputs.
- Added Evidence-first, Entity Resolution, Decision Gates and Executive Deliverables capability cards.
- Added professional Executive Dashboard and KPI cards.
- Redesigned regulatory section with explicit description, status and required action.
- Added v3.0 Professional badge and cache-busted assets.

## Professional deliverables

- Reworked Word cover, headers, footers and document metadata.
- Added organization, report purpose, version and developer metadata.
- Renamed deliverables for professional use.
- Updated Excel cover and workbook metadata.
- Added professional product overview and demo guide.

## Engineering

- Renamed payload metadata from student fields to report-owner fields.
- Added explicit Asia/Tehran timezone handling.
- Updated app service/version metadata to `tejaratyar / 3.0-professional`.
- Updated Colab notebook branding and deployment settings.
- Updated Docker, Render and Liara service names.
- All 13 automated tests pass; Python, JavaScript and Notebook syntax checks pass.
