# Dataspace Publishing Infographic (Codebase-Aligned)

## Alignment Review (summary)
- The provided instruction does NOT align with the current codebase in several places.
- UI modules present: Onboarding Wizard (Environment, EDC Mode, Credentials), Connection Status, Publish Submodel, Publications list/manager. No UI for Policy Editor, Catalog Browser, Transfer History, or Audit Log.
- Public API surface under /api/dataspace/* includes connections, publications, policies, health, environments, and EDC modes. There are no REST endpoints for catalog browsing, negotiation, transfer history, or audit log.
- Policy control exists via templates and policy preview/CRUD endpoints, but is not exposed as a dedicated UI editor.

## Tailored Instruction (designer-ready, aligned to repo)

### 1) Story (message architecture)
- One-sentence promise (headline):
  "Connect your AAS submodel to Manufacturing-X / Catena-X with guided onboarding and policy-driven sharing."
- Tier A (15 seconds): 4-6 benefit tiles
  - Wizard-based onboarding
  - Health-checked connection status
  - Publish AAS submodels to BaSyx + DTR + EDC
  - ODRL policy templates (membership, BPN restricted)
  - Vault-backed credentials for non-sandbox environments
- Tier B (60-90 seconds): user journey with UI panels (steps 1-4 below)
- Tier C (3-5 minutes): architecture + API map + policy snippet

### 2) Canvas + grid
- Primary: 1080x1920 (vertical)
- Grid: 12 columns, 80px margins, 24px gutters, 8pt spacing system

### 3) Visual language
- Clean industrial-tech, light base with a teal/cyan accent gradient
- Rounded cards 8-12px radius, 1px strokes
- Status colors: Connected (green), In progress (blue), Degraded (amber), Failed (red)
- Single icon style (outline)

### 4) Content blueprint (vertical layout)

A) Hero (top)
- Title + subtitle
- Pipeline visual: Submodel (AAS) -> Dataspace Connector -> Partner
- Trust badges: "Vault-backed", "Health-checked", "ODRL policies"

B) What the user does (middle)
- 4-step journey (UI panels shown as cards)
  1. Select Environment (Sandbox / Catena-X Test / Catena-X Prod / Manufacturing-X)
  2. Choose EDC Mode + Credentials (Tractus-X EDC or EDC AAS Extension)
  3. Connect + Status (progress states + health checks)
  4. Publish + Manage (Publish to Dataspace + Publications list)

C) Under the hood (bottom)
- Architecture diagram
  - React UI -> FastAPI /api/dataspace -> Dataspace services (Connection Manager, Policy Engine, Tasks)
  - External dependencies: Vault, BaSyx AAS Server, DTR, Tractus-X EDC (control/data planes)
- Compact API map of actual endpoints
- Policy template + ODRL preview snippet

### 5) Feature panel specifics (aligned to repo)

Panel 1: Environment selection
- UI: radio card list (Sandbox / Catena-X Test / Catena-X Production / Manufacturing-X)
- Note: Sandbox requires no credentials. Non-sandbox requires BPN + client credentials.

Panel 2: EDC mode + credentials
- UI: EDC Mode cards
  - Tractus-X EDC (separate control/data plane)
  - EDC AAS Extension (direct AAS endpoint integration)
- Credential fields: BPN, client_id, client_secret

Panel 3: Connect + Status
- Connection progress: Provisioning Secrets -> Configuring EDC -> Registering Connector -> Publishing Self-Description -> Connected
- Status badge: Connected / Degraded / Failed
- Health chips: DTR, EDC, Provider (with latency)

Panel 4: Publish + Publications
- Publish actions:
  - Create AAS in BaSyx
  - Register Digital Twin in DTR
  - Create EDC asset + policy
  - Make submodel discoverable
- Publications list shows: Template name, Submodel ID, AAS endpoint, EDC offer ID, status, Created timestamp
- Actions: Refresh status, Unpublish

### 6) Engineer detail (API + policy)
- API map (actual endpoints):
  - POST /api/dataspace/connections
  - GET /api/dataspace/connections
  - GET /api/dataspace/connections/{connection_id}
  - DELETE /api/dataspace/connections/{connection_id}
  - POST /api/dataspace/connections/{connection_id}/reconnect
  - POST /api/dataspace/publications
  - GET /api/dataspace/publications
  - GET /api/dataspace/publications/{publication_id}
  - PUT /api/dataspace/publications/{publication_id}
  - DELETE /api/dataspace/publications/{publication_id}
  - GET /api/dataspace/policies/templates
  - POST /api/dataspace/policies/preview
  - POST /api/dataspace/policies
  - GET /api/dataspace/policies/{policy_id}
  - PUT /api/dataspace/policies/{policy_id}
  - DELETE /api/dataspace/policies/{policy_id}
  - GET /api/dataspace/health
  - GET /api/dataspace/environments
  - GET /api/dataspace/edc-modes
- Policy template callouts:
  - Unrestricted Use
  - Membership Required
  - BPN Restricted
  - PCF Data Exchange
  - Digital Twin Access
  - Traceability Data

### 7) Production notes
- Avoid references to catalog browser, negotiation, transfer history, or audit log (not implemented in the current UI/API).
- Use real UI strings where possible: "Dataspace Publishing", "Publish to Dataspace", "Connected Dataspace".

---

## Wireframe Layout (1080x1920)

Grid assumptions:
- Margin: 80px (left/right/top/bottom)
- Gutters: 24px
- Content width: 920px

Coordinates are in px: (x, y, w, h)

Hero Section
- A1 Title block: (80, 80, 920, 120)
- A2 Pipeline visual: (80, 216, 920, 80)
- A3 Trust badges row: (80, 312, 920, 56)

Journey Section
- B0 Section heading: (80, 416, 920, 56)
- B1 Card 1 (Environment): (80, 496, 448, 320)
- B2 Card 2 (EDC mode + creds): (552, 496, 448, 320)
- B3 Card 3 (Connect + status): (80, 840, 448, 320)
- B4 Card 4 (Publish + publications): (552, 840, 448, 320)

Under-the-hood Section
- C0 Section heading: (80, 1208, 920, 48)
- C1 Architecture diagram: (80, 1264, 528, 360)
- C2 Publish flow mini-diagram: (80, 1640, 528, 200)
- C3 API map card: (632, 1264, 368, 248)
- C4 Policy snippet card: (632, 1528, 368, 176)
- C5 Status legend + health chips: (632, 1720, 368, 120)

---

## Copy Deck (final microcopy)

Hero
- Title: Dataspace Publishing for Manufacturing-X / Catena-X
- Subtitle: Guided onboarding, health-checked connections, and policy-driven sharing of AAS submodels.
- Badges: Vault-backed | Health-checked | ODRL policies
- Pipeline labels: Submodel (AAS) -> Dataspace Connector -> Partner

Journey Card 1: Select Environment
- Title: 1. Select Environment
- Body: Sandbox for local testing, or Catena-X Test/Prod and Manufacturing-X for real exchange.
- UI labels: Sandbox (default), Catena-X Test, Catena-X Production, Manufacturing-X

Journey Card 2: Choose EDC Mode + Credentials
- Title: 2. Choose EDC Integration
- Body: Pick the connector mode that matches your infrastructure.
- Subtext: Tractus-X EDC (control + data planes) or EDC AAS Extension.
- Credential note: Non-sandbox requires BPN + client credentials (stored in Vault).
- Field placeholders: BPNL000000000001, client_id, client_secret

Journey Card 3: Connect + Status
- Title: 3. Connect and Monitor
- Body: Track progress with live status and health checks.
- Progress labels: Provisioning Secrets -> Configuring EDC -> Registering Connector -> Publishing Self-Description
- Status badges: Connected | Degraded | Failed
- Health chips: DTR 120ms | EDC 95ms | Provider 110ms

Journey Card 4: Publish + Manage
- Title: 4. Publish and Manage Submodels
- Bullets:
  - Create AAS in BaSyx
  - Register Digital Twin in DTR
  - Create EDC asset + policy
  - Make submodel discoverable
- Button: Publish to Dataspace
- Publications list row: {Template} | Submodel ID | AAS Endpoint | EDC Offer | Status | Created
- Actions: Refresh | Unpublish

Under the Hood: Architecture
- Caption: React UI -> FastAPI /api/dataspace -> Dataspace Services
- Services: Connection Manager | Policy Engine | Background Tasks
- External: Vault | BaSyx AAS Server | Digital Twin Registry | Tractus-X EDC

Under the Hood: Publish Flow
- Flow: Hydrate submodel -> BaSyx AAS -> DTR -> EDC offer + policy

Under the Hood: API Map (compact)
- Connections: /connections, /connections/{id}, /connections/{id}/reconnect
- Publications: /publications, /publications/{id}
- Policies: /policies/templates, /policies/preview, /policies
- Health + Config: /health, /environments, /edc-modes

Policy Snippet (example)
- Config:
  access_type: restricted
  allowed_partners: [BPNL000000000001]
  target_paths: ["TechnicalData/ErrorCodes"]
- ODRL preview (short):
  "permission": [{"action":"use",
  "constraint":{"leftOperand":"BusinessPartnerNumber",
  "operator":"in",
  "rightOperand":["BPNL000000000001"]}}]

Status Legend
- Green: Connected
- Blue: In progress
- Amber: Degraded
- Red: Failed
