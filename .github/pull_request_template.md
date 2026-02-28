## Summary

- 

## Change Type

- [ ] Bug fix
- [ ] Enhancement
- [ ] Security hardening
- [ ] Documentation/process

## Validation

- [ ] `PYTHONPATH=backend pytest backend/tests` (if backend touched)
- [ ] `npm --prefix frontend run lint` (if frontend touched)
- [ ] `npm --prefix frontend run type-check` (if frontend touched)
- [ ] `npm --prefix frontend run test:unit` (if frontend touched)
- [ ] `mkdocs build --strict` (if docs or `.github` process files touched)
- [ ] E2E core smoke (if UI/backend behavior changed)

### Optional Profile Validation (run when touched)

- [ ] `E2E_PROFILE=magic-import npm --prefix frontend run test:e2e`
- [ ] `E2E_PROFILE=dataspace npm --prefix frontend run test:e2e`
- [ ] `E2E_PROFILE=plc npm --prefix frontend run test:e2e`

## Contract/Behavior Changes

- [ ] API contract changed
- [ ] Frontend type contract changed
- [ ] Feature flag behavior changed
- [ ] No user-facing contract changes

## Checklist

- [ ] No fix without a test
- [ ] Added/updated docs for behavior changes
- [ ] Core docker compose workflow remains intact (`docker compose up`)
- [ ] Updated `REVIEW_REPORT.md` for P0/P1 or security/correctness findings
