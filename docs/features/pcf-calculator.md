# PCF Calculator & Validator (Carbon Footprint)

Calculate Product Carbon Footprint (PCF) values and validate against IDTA 02023 specification requirements. This tool appears automatically when editing Carbon Footprint templates.

![PCF Calculator Live Demo](../pcf/pcf-calculator-live-demo.gif)

## PCF Declaration

Set required PCF metadata for the active ProductCarbonFootprint instance:

- **Reference impact unit** (e.g., `piece`, `kg`, `kWh`) writes to `ReferenceImpactUnitForCalculation`
- **Quantity of measure** writes to `QuantityOfMeasureForCalculation`
- **Publication date** writes to `PublicationDate`
- **Active instance targeting** supports templates with multiple `ProductCarbonFootprint` entries
- **Lifecycle phase awareness** shows how many `LifeCyclePhases` are selected and flags when none are set

## CO₂e Calculator

Build emission activity tables and compute total CO₂e with a few clicks:

- **Add emission activities** with name, GHG Protocol category (Scope 1/2/3), quantity, and unit
- **Search emission factors** from a curated dataset with source, region, and year metadata
- **Dataset transparency** shows the emission factor dataset version and factor count in the UI
- **Unit-aware calculations** with kg↔t conversion, freight `tkm` support, and warnings for incompatible units
- **Per-activity + total CO₂e** plus support for negative quantities (offsets) with warnings
- **Apply to form** writes the calculated total directly to the active `PcfCO2eq` field
- **Activity traceability** stores the full calculation payload (activities + factor metadata) in `metadata.pcf`
- **PCFActivities list** auto-injected on export when missing (toggle via `PCF_ACTIVITY_LIST_INJECTION_ENABLED`), populated with activity details and `ActivityCO2eKg`
- **Export trace** adds PCF calculation qualifiers and attaches `pcf-calculation.json` for audit-ready provenance

| Screenshot | Description |
|------------|-------------|
| ![Add Activities](../pcf/pcf-step-1-activities.png) | Add emission activities with quantities and factors |
| ![Search Factors](../pcf/pcf-step-2-search-factors.png) | Search and select from 20+ emission factors |
| ![Calculate](../pcf/pcf-step-3-calculate.png) | PCF Declaration + calculation totals with per-activity CO₂e |

## IDTA 02023 Validator

Validate your Carbon Footprint data against the official IDTA 02023 specification:

- **Blocking errors** for required fields: `PcfCO2eq`, `ReferenceImpactUnitForCalculation`, `QuantityOfMeasureForCalculation`, `PublicationDate`, `LifeCyclePhases`
- **Warnings** for recommended fields, value list conformance, and invalid date order
- **Cross-field validation**: `ExpirationDate` must be after `PublicationDate`
- **Completeness score** shows percentage of PCF fields filled
- **Export-time enforcement**: Carbon Footprint exports are blocked if validation fails

## Emission Factors Database

The built-in database includes common emission factors from recognized authorities:

| Category | Examples | Sources |
|----------|----------|---------|
| Electricity | US/EU/UK/Germany grid averages | EPA eGRID, EEA, UBA, DEFRA |
| Fuels | Natural gas, diesel, gasoline | EPA, DEFRA |
| Transport | Road freight, air freight, sea freight | DEFRA |
| Materials | Steel, aluminum, plastics (primary & recycled) | ecoinvent |
| Water | Supply and treatment | DEFRA |

Factors include value, unit, source reference, region, and year for full traceability. The UI surfaces dataset version/count via `/api/pcf/health`.

## API Endpoints

- `POST /api/pcf/calculate` - Calculate CO₂e emissions from activity data
- `POST /api/pcf/validate` - Validate PCF form data against IDTA 02023 rules
- `GET /api/pcf/factors/search` - Search emission factors by name, source, or region
- `GET /api/pcf/factors/{factor_id}` - Get a specific emission factor by ID
- `GET /api/pcf/health` - PCF service health + emission factor dataset metadata
