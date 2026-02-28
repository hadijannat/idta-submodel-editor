# PLC4X Bridge

Real-time shopfloor data integration via Apache PLC4X, supporting 30+ industrial protocols.

## Overview

The PLC4X Bridge is a separate Java/Spring Boot microservice that:

- Connects to industrial PLCs using Apache PLC4X
- Polls tag values at configurable intervals
- Updates BaSyx AAS Server submodel properties in real-time

---

## Architecture

```
PLC ──────────► PlcReader ──────────► ContinuousReader ──────────► AasUpdater ──────────► BaSyx
  (Protocol)     (Connect)             (Poll @ interval)           (Update)              (AAS Server)
```

### Components

| Component | Description |
|-----------|-------------|
| `PlcReader` | Protocol-agnostic PLC4X connection and tag reading |
| `ContinuousReader` | Scheduled polling with configurable intervals |
| `AasUpdater` | Updates BaSyx submodel properties from tag values |
| `PlcController` | REST API for connection management and mappings |

---

## Supported Protocols

Via Apache PLC4X:

| Protocol | Connection String Example |
|----------|--------------------------|
| **S7 (Siemens)** | `s7://192.168.1.10` |
| **Modbus TCP** | `modbus-tcp://192.168.1.10:502` |
| **Modbus RTU** | `modbus-rtu:///dev/ttyUSB0` |
| **OPC UA** | `opcua:tcp://192.168.1.10:4840` |
| **EtherNet/IP** | `eip://192.168.1.10` |
| **BACnet** | `bacnet-ip://192.168.1.10:47808` |
| **ADS (Beckhoff)** | `ads:tcp://192.168.1.10` |
| **KNX** | `knxnet-ip://192.168.1.10:3671` |

Plus 20+ additional protocols. See [PLC4X documentation](https://plc4x.apache.org/) for the full list.

---

## Quick Start

### Docker Compose

```bash
# Start PLC bridge with required BaSyx services
docker compose --profile plc up

# Or run with full dataspace stack
docker compose --profile dataspace --profile plc up
```

### Manual Setup

```bash
cd plc4x-bridge
./mvnw spring-boot:run
```

---

## Configuration

### Backend Integration

| Variable | Description | Default |
|----------|-------------|---------|
| `PLC4X_BRIDGE_ENABLED` | Enable PLC bridge feature | false |
| `PLC4X_BRIDGE_URL` | PLC4X Bridge microservice URL | - |

### Bridge Settings (application.yml)

| Property | Description | Default |
|----------|-------------|---------|
| `plc.connection-string` | PLC4X connection string | - |
| `plc.read-interval` | Polling interval in milliseconds | 1000 |
| `mapping.update-mode` | Update mode (ON_CHANGE / ALWAYS) | ON_CHANGE |
| `mapping.change-threshold` | Deadband for ON_CHANGE mode | 0.01 |
| `basyx.aas-server.url` | BaSyx AAS Server URL | http://basyx-aas-server:4001 |

### Example Configuration

```yaml
# plc4x-bridge/src/main/resources/application.yml
plc:
  connection-string: s7://192.168.1.10
  read-interval: 500

mapping:
  update-mode: ON_CHANGE
  change-threshold: 0.01

basyx:
  aas-server:
    url: http://basyx-aas-server:4001
```

---

## Tag Mapping

Map PLC tags to AAS submodel properties:

```bash
curl -X POST http://localhost:8090/api/plc/mappings \
  -H "Content-Type: application/json" \
  -d '{
    "mappings": [
      {
        "tag": "%DB1.DBD0:REAL",
        "submodel_id": "urn:example:submodel:1",
        "property_path": "Temperature/CurrentValue"
      },
      {
        "tag": "%DB1.DBD4:REAL",
        "submodel_id": "urn:example:submodel:1",
        "property_path": "Pressure/CurrentValue"
      }
    ]
  }'
```

### Tag Address Syntax

Tag addresses follow PLC4X syntax. Examples for S7:

| Tag Address | Description |
|-------------|-------------|
| `%DB1.DBD0:REAL` | Data block 1, double word 0, real type |
| `%M0.0:BOOL` | Memory bit 0.0 |
| `%IW0:INT` | Input word 0 |
| `%QW0:INT` | Output word 0 |

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/plc/status` | Get connection status |
| POST | `/api/plc/connect` | Connect to PLC |
| POST | `/api/plc/disconnect` | Disconnect from PLC |
| GET | `/api/plc/tags` | List discovered tags |
| POST | `/api/plc/mappings` | Configure tag-to-AAS mappings |
| GET | `/api/plc/readings` | Get current tag values |

### Status Response

```json
{
  "connected": true,
  "connection_string": "s7://192.168.1.10",
  "last_read": "2024-01-15T10:30:00Z",
  "active_mappings": 5,
  "read_errors": 0
}
```

---

## Update Modes

### ON_CHANGE (Default)

Only updates AAS properties when values change beyond the threshold:

```yaml
mapping:
  update-mode: ON_CHANGE
  change-threshold: 0.01  # 1% change required
```

Reduces network traffic and BaSyx load for stable values.

### ALWAYS

Updates AAS properties on every poll cycle:

```yaml
mapping:
  update-mode: ALWAYS
```

Use for time-series data or when every reading matters.

---

## Error Handling

The bridge handles common PLC communication issues:

| Error | Behavior |
|-------|----------|
| Connection lost | Automatic reconnection with backoff |
| Tag not found | Logged and skipped, other tags continue |
| Type mismatch | Logged with warning, value conversion attempted |
| AAS update failed | Retried with exponential backoff |

---

## Monitoring

The bridge exposes Spring Boot Actuator endpoints:

```bash
# Health check
curl http://localhost:8090/actuator/health

# Metrics
curl http://localhost:8090/actuator/metrics/plc.reads.total
curl http://localhost:8090/actuator/metrics/plc.updates.total
```

---

## See Also

- [Dataspace Publishing](dataspace-publishing.md) — Publish PLC data to dataspaces
- [Configuration Reference](../reference/configuration.md)
- [Apache PLC4X Documentation](https://plc4x.apache.org/)
