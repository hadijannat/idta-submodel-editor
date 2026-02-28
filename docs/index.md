# IDTA Submodel Editor Documentation

This documentation site is the canonical reference for features, configuration, and API behavior.

For quick onboarding and local run commands, start with the repository README:
- [Repository README](https://github.com/hadijannat/idta-submodel-editor/blob/main/README.md)

## Start Here

- New to the project: read [Features Overview](features/README.md)
- Configuring environments: [Configuration Reference](reference/configuration.md)
- Integrating programmatically: [API Endpoints Reference](reference/api-endpoints.md)
- Reviewing supported model elements: [Element Types](reference/element-types.md)

## Feature Guides

- [Smart Mapper](features/smart-mapper.md)
- [Magic Import](features/magic-import.md)
- [Template Operations](features/template-ops.md)
- [Passport Mode](features/passport-mode.md)
- [Semantic Lookup](features/semantic-lookup.md)
- [PCF Calculator](features/pcf-calculator.md)
- [Dataspace Publishing](features/dataspace-publishing.md)
- [PLC4X Bridge](features/plc4x-bridge.md)

## Reference Guides

- [Configuration Reference](reference/configuration.md)
- [API Endpoints Reference](reference/api-endpoints.md)
- [Element Types](reference/element-types.md)
- [Review Playbook](reference/review-playbook.md)

## Operational Notes

- Swagger UI (`/api/docs`) is available when backend `ENV != production`.
- Mnestix browser is exposed at `http://localhost:3001` when using the `dataspace` profile.
- Running the `auth` compose profile adds Keycloak, but authentication is only enforced when OIDC is enabled in backend configuration.
- Keycloak maps to host port `8081` by default (`KEYCLOAK_HOST_PORT`), so auth profile can run with frontend.

## CI and Automation

- CI pipeline: [`ci.yml`](https://github.com/hadijannat/idta-submodel-editor/blob/main/.github/workflows/ci.yml)
- Scheduled/manual E2E pipeline: [`e2e-tests.yml`](https://github.com/hadijannat/idta-submodel-editor/blob/main/.github/workflows/e2e-tests.yml)
- Fixture refresh workflow: [`fixtures-refresh.yml`](https://github.com/hadijannat/idta-submodel-editor/blob/main/.github/workflows/fixtures-refresh.yml)
- Docs build/deploy workflow: [`docs.yml`](https://github.com/hadijannat/idta-submodel-editor/blob/main/.github/workflows/docs.yml)
