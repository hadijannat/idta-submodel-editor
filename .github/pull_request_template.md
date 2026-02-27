## Summary

- 

## Change Type

- [ ] Bug fix
- [ ] Enhancement
- [ ] Security hardening
- [ ] Documentation/process

## Validation

- [ ] `PYTHONPATH=backend pytest backend/tests`
- [ ] `npm run lint`
- [ ] `npm run type-check`
- [ ] `npm run test:unit`
- [ ] E2E core smoke (if UI/backend behavior changed)

### Optional Profile Validation (run when touched)

- [ ] `E2E_PROFILE=magic-import npm run test:e2e`
- [ ] `E2E_PROFILE=dataspace npm run test:e2e`
- [ ] `E2E_PROFILE=plc npm run test:e2e`

## Contract/Behavior Changes

- [ ] API contract changed
- [ ] Frontend type contract changed
- [ ] Feature flag behavior changed
- [ ] No user-facing contract changes

## Checklist

- [ ] No fix without a test
- [ ] Added/updated docs for behavior changes
- [ ] Core docker-compose workflow remains intact (`docker-compose up`)
