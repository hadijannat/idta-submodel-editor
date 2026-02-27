# Contributing to IDTA Submodel Editor

Thank you for contributing.

## Development Setup

### Option 1: Dev Container (recommended)

1. Open the repository in VS Code.
2. Select `Reopen in Container`.
3. Start services:
   - Backend: `cd backend && uvicorn app.main:app --reload --port 8000`
   - Frontend: `cd frontend && npm run dev`

### Option 2: Local environment

1. Backend:
   - `cd backend`
   - `python -m venv .venv`
   - `source .venv/bin/activate`
   - `pip install -r requirements.txt`
   - `uvicorn app.main:app --reload --port 8000`
2. Frontend:
   - `cd frontend`
   - `npm ci`
   - `npm run dev`

### Option 3: Full stack via Compose

- `docker compose up`

## Test Matrix

Run the relevant checks for the area you changed:

- Backend tests:
  - `PYTHONPATH=backend pytest backend/tests`
- Frontend checks:
  - `npm --prefix frontend run lint`
  - `npm --prefix frontend run type-check`
  - `npm --prefix frontend run test:unit`
- Frontend build:
  - `npm --prefix frontend run build`
- Docs:
  - `mkdocs build --strict`
- Optional E2E smoke:
  - `npm --prefix frontend run test:e2e:smoke`

## Pull Request Expectations

- Keep PRs small and theme-focused.
- Include:
  - Summary of behavior changes.
  - Test evidence (commands and results).
  - Screenshots for UI changes.
  - Config/env changes if any.
- Follow the Review Playbook:
  - `docs/reference/review-playbook.md`
- If you touched high-risk correctness/security flows, update:
  - `REVIEW_REPORT.md`

## Branch and Commit Guidelines

- Use clear, imperative commit messages.
- Do not mix unrelated changes in one PR.
- Rebase or merge `main` regularly to reduce conflicts.

## Attribution

Contributors are recognized via:
- Git history
- `AUTHORS.md`
- Release notes (for major changes)

## Code of Conduct

Be respectful and constructive in all interactions.

## License

By contributing, you agree your contributions are licensed under the MIT License.
