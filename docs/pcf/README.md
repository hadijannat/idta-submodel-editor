# PCF Calculator & Validator Documentation

This folder contains screenshots and documentation for the PCF (Product Carbon Footprint) Calculator & Validator feature.

## Required Screenshots

The following screenshots are referenced in the main README and should be captured:

### Live Demo GIF
- **File**: `pcf-calculator-live-demo.gif`
- **Content**: Full workflow showing:
  1. Selecting a Carbon Footprint template
  2. Adding emission activities
  3. Searching and selecting emission factors
  4. Calculating total CO2e
  5. Applying to form
  6. Running validation
  7. Exporting

### Step-by-Step Screenshots

| File | Description |
|------|-------------|
| `pcf-step-1-activities.png` | Activity table with 2-3 emission activities added (electricity, transport, materials) |
| `pcf-step-2-search-factors.png` | Emission factor search modal open with search results visible |
| `pcf-step-3-calculate.png` | Calculated results showing dataset metadata, total CO2e, and per-activity values |

## Capturing Screenshots

### Recommended Setup

1. Start the application:
   ```bash
   docker-compose up
   ```

2. Navigate to `http://localhost:8080`

3. Select the **Carbon Footprint** template (IDTA 02023)

4. Proceed to Step 4 (Fill Required Fields) - the PCF panel will appear

### Demo Data for Screenshots

Example activities to add for visually appealing screenshots:

| Activity | Category | Quantity | Unit | Factor | Factor Unit |
|----------|----------|----------|------|--------|-------------|
| Grid Electricity | Scope 2 | 10000 | kWh | 0.417 | kg CO2e/kWh |
| Truck Transport | Scope 3 | 500 | tkm | 0.107 | kg CO2e/tkm |
| Steel Components | Scope 3 | 100 | kg | 2.1 | kg CO2e/kg |

This gives a total of ~4,393.5 kg CO2e - a realistic value for demonstration.

### GIF Recording

Use a screen recording tool (e.g., Kap on macOS, LICEcap, or ShareX on Windows) to capture:

- Resolution: 1280x720 or similar
- Frame rate: 10-15 fps
- Duration: 30-60 seconds
- Focus on the PCF panel area
- Ensure the dataset metadata banner is visible (version + factor count)
- The PCF activity list injection banner should appear if the template lacks `PCFActivities`

## Feature Overview

### Components

- **PCFCalculator**: Activity table with factor search integration
- **PCFValidator**: IDTA 02023 compliance checker
- **PCFPanel**: Container combining both tools
- **PCFActivities injection**: Adds a list-based activity trace when the template is missing one

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/pcf/calculate` | POST | Calculate CO2e from activities |
| `/api/pcf/validate` | POST | Validate against IDTA 02023 |
| `/api/pcf/factors/search` | GET | Search emission factors |
| `/api/pcf/factors/{id}` | GET | Get factor by ID |
| `/api/pcf/health` | GET | Health + emission factor dataset metadata |

### Emission Factors Database

The built-in database includes 20+ factors from:
- EPA (US environmental data)
- DEFRA (UK government factors)
- ecoinvent (LCA database)
- EEA (European Environment Agency)
- UBA (German Federal Environment Agency)

Categories covered:
- Electricity grids (US, EU, UK, Germany)
- Fuels (natural gas, diesel, gasoline)
- Transport (road, air, sea freight)
- Materials (steel, aluminum, plastics)
- Water (supply and treatment)
