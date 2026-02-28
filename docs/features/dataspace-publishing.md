# Dataspace Publishing (Manufacturing-X / Catena-X)

Connect your submodels to a dataspace with a guided wizard, Vault-backed credential storage, and real health checks. The connector supports sandbox mode for local testing and Catena-X / Manufacturing-X environments for production-aligned deployments.

---

## Highlights

- **Wizard-based onboarding** with environment selection and EDC mode
- **Policy Builder** — Visual ODRL policy construction with pre-built templates
- **Multiple Environments** — Sandbox, Catena-X Test, Catena-X Production
- **EDC Modes** — Tractus-X EDC or AAS Extension mode
- **Vault-backed secrets** (required for non-sandbox environments)
- **Health-driven status** (Connected / Degraded / Failed) based on real endpoint checks
- **Contract Negotiation** — Full EDC contract workflow with asset/policy/agreement management
- **Audit Logging** — Track all dataspace operations

---

## Quick Start (Local)

```bash
# Start core stack
docker compose up -d

# Enable dataspace in backend + configure Vault token
DATASPACE_ENABLED=true VAULT_TOKEN=dev-root-token docker compose up -d backend

# Start Vault (dataspace profile)
docker compose --profile dataspace up -d vault
```

## Full Dataspace Stack (EDC + DTR + BaSyx)

The full dataspace profile uses public images (Tractus-X, BaSyx, Vault, Postgres). Start directly:

```bash
docker compose --profile dataspace up -d
```

---

## Environments

The connector supports multiple dataspace environments:

| Environment | Description | Use Case |
|-------------|-------------|----------|
| `sandbox` | Local development stack | Development, testing |
| `catena-x-test` | Catena-X test environment | Integration testing |
| `catena-x-prod` | Catena-X production | Production deployment |

### Selecting Environment

```bash
# Via environment variable
DATASPACE_DEFAULT_ENVIRONMENT=catena-x-test docker compose up

# Or via API
curl -X POST /api/dataspace/connections \
  -H "Content-Type: application/json" \
  -d '{"environment": "catena-x-test", "edc_mode": "tractus-x"}'
```

---

## EDC Connector Modes

Two modes are available for EDC integration:

### Tractus-X Mode (Default)

Full-featured EDC with separate control and data planes:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Control Plane  │────►│   Data Plane    │────►│  Partner EDC    │
│  (Policy, Contracts)  │  (Data Transfer)│     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

**Configuration:**

```bash
EDC_CONTROL_PLANE_URL=http://edc-control-plane:19192
EDC_DATA_PLANE_URL=http://edc-data-plane:19291
EDC_API_KEY=your-api-key
```

### AAS Extension Mode

Simplified mode using EDC AAS Extension for direct AAS integration:

```
┌─────────────────┐     ┌─────────────────┐
│  EDC + AAS Ext  │────►│  Partner EDC    │
│  (All-in-one)   │     │                 │
└─────────────────┘     └─────────────────┘
```

**Configuration:**

```bash
DATASPACE_DEFAULT_EDC_MODE=aas-extension
EDC_AAS_EXTENSION_URL=http://edc-aas:8080
```

---

## Policy Builder

Create ODRL policies visually with the Policy Builder component.

### Pre-built Templates

| Template | Description |
|----------|-------------|
| `unrestricted` | Allow all access (no constraints) |
| `membership` | Require Catena-X membership verification |
| `bpn-restricted` | Restrict to specific Business Partner Numbers |

### Custom Policies

Build custom ODRL policies with:

- **Access Level Selection** — Public, membership, or restricted
- **Partner Selection** — Allow-list of BPNs
- **Element Selection** — Partial submodel access

### API Usage

```bash
# Preview ODRL from policy config
curl -X POST /api/dataspace/policies/preview \
  -H "Content-Type: application/json" \
  -d '{
    "template": "bpn-restricted",
    "allowed_bpns": ["BPNL000000000001", "BPNL000000000002"]
  }'

# Create policy
curl -X POST /api/dataspace/policies \
  -H "Content-Type: application/json" \
  -d '{
    "name": "partner-access",
    "odrl": { ... }
  }'
```

### Example ODRL Output

```json
{
  "@context": "https://www.w3.org/ns/odrl/2/",
  "@type": "Offer",
  "permission": [{
    "action": "use",
    "constraint": [{
      "leftOperand": "BusinessPartnerNumber",
      "operator": "isAnyOf",
      "rightOperand": ["BPNL000000000001", "BPNL000000000002"]
    }]
  }]
}
```

---

## Publication Workflow

### 1. Connect to Dataspace

```bash
curl -X POST /api/dataspace/connections \
  -H "Content-Type: application/json" \
  -d '{
    "environment": "sandbox",
    "edc_mode": "tractus-x"
  }'
```

### 2. Publish Submodel

```bash
curl -X POST /api/dataspace/publications \
  -H "Content-Type: application/json" \
  -d '{
    "connection_id": "conn_123",
    "template_name": "DigitalNameplate",
    "form_data": { ... },
    "policy_id": "policy_456"
  }'
```

### 3. Monitor Status

```bash
# Get publication status
curl /api/dataspace/publications/pub_789

# List all publications
curl /api/dataspace/publications?connection_id=conn_123
```

---

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `DATASPACE_ENABLED` | Enable dataspace features | false |
| `DATASPACE_CACHE_DIR` | Cache directory | ./cache/dataspace |
| `DATASPACE_DEFAULT_ENVIRONMENT` | Default environment | sandbox |
| `DATASPACE_DEFAULT_EDC_MODE` | Default EDC mode | tractus-x |
| `BASYX_AAS_SERVER_URL` | BaSyx AAS server URL | http://basyx-aas-server:4001 |
| `BASYX_REGISTRY_URL` | BaSyx registry URL | http://basyx-registry:4002 |
| `EDC_CONTROL_PLANE_URL` | EDC control plane URL | http://edc-control-plane:19192 |
| `EDC_DATA_PLANE_URL` | EDC data plane URL | http://edc-data-plane:19291 |
| `EDC_API_KEY` | EDC Management API key | - |
| `EDC_AAS_EXTENSION_URL` | EDC AAS Extension URL | - |
| `DTR_URL` | Digital Twin Registry URL | http://dtr:4003 |
| `VAULT_URL` | Vault URL | http://vault:8200 |
| `VAULT_TOKEN` | Vault token | - |
| `CATENA_X_BPN` | Business Partner Number | - |

---

## API Reference

### Connection Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/dataspace/connections` | Start dataspace onboarding |
| GET | `/api/dataspace/connections` | List all connections |
| GET | `/api/dataspace/connections/{id}` | Get connection status with health |
| DELETE | `/api/dataspace/connections/{id}` | Disconnect from dataspace |
| POST | `/api/dataspace/connections/{id}/reconnect` | Reconnect failed connection |

### Publication Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/dataspace/publications` | Publish submodel to dataspace |
| GET | `/api/dataspace/publications` | List publications |
| GET | `/api/dataspace/publications/{id}` | Get publication details |
| PUT | `/api/dataspace/publications/{id}` | Update published submodel |
| DELETE | `/api/dataspace/publications/{id}` | Unpublish submodel |

### Policy Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/dataspace/policies/templates` | Get pre-built policy templates |
| POST | `/api/dataspace/policies/preview` | Preview ODRL from policy config |
| POST | `/api/dataspace/policies` | Create new policy |
| GET | `/api/dataspace/policies/{id}` | Get policy details |
| PUT | `/api/dataspace/policies/{id}` | Update policy |
| DELETE | `/api/dataspace/policies/{id}` | Delete policy |

### Health & Discovery

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/dataspace/health` | Check dataspace component health |
| GET | `/api/dataspace/environments` | List available environments |
| GET | `/api/dataspace/edc-modes` | List available EDC modes |

---

## Architecture

The dataspace connector integrates with:

```
┌─────────────────────────────────────────────────────────────┐
│                     IDTA Editor Backend                      │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐   │
│  │  Connection   │  │   Publisher   │  │    Policy     │   │
│  │   Manager     │  │               │  │    Engine     │   │
│  └───────┬───────┘  └───────┬───────┘  └───────┬───────┘   │
└──────────┼──────────────────┼──────────────────┼───────────┘
           │                  │                  │
           ▼                  ▼                  ▼
┌──────────────────┐  ┌───────────────┐  ┌───────────────┐
│  Eclipse BaSyx   │  │  Tractus-X    │  │   HashiCorp   │
│   AAS Server     │  │     EDC       │  │     Vault     │
└──────────────────┘  └───────────────┘  └───────────────┘
           │                  │
           ▼                  ▼
┌──────────────────┐  ┌───────────────┐
│  Digital Twin    │  │   Partner     │
│    Registry      │  │     EDC       │
└──────────────────┘  └───────────────┘
```

- **Eclipse BaSyx AAS Server** — Hosts submodel instances
- **Catena-X Digital Twin Registry (DTR)** — Registers digital twins for discovery
- **Tractus-X EDC** — Handles sovereign data exchange with ODRL policies
- **HashiCorp Vault** — Secures credentials and certificates

---

## AAS Browser Integration

Published submodels can be explored using the embedded Mnestix AAS Browser:

| Variable | Description | Default |
|----------|-------------|---------|
| `MNESTIX_ENABLED` | Enable AAS Browser | true |
| `MNESTIX_URL` | Mnestix instance URL | http://mnestix:3000 |

Access at http://localhost:3000 when running with the dataspace profile.

---

## See Also

- [PLC4X Bridge](plc4x-bridge.md) — Real-time PLC data for dataspace publishing
- [Template Operations](template-ops.md) — Managing template versions
- [Configuration Reference](../reference/configuration.md)
