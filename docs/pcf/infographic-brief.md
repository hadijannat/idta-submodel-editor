# Infographic Design Brief: PCF Calculator & Validator

## Goal
Create a single-page infographic that explains how the PCF Calculator & Validator turns raw activity data into an IDTA 02023‑compliant Product Carbon Footprint. It must be understandable to non‑technical audiences while giving enough technical depth for sustainability and digital‑twin teams.

## Target audiences
- Sustainability and ESG teams
- Manufacturing operations / process engineers
- Digital twin / AAS engineers
- Auditors and compliance stakeholders

## Format
- Primary: 1080x1350 (LinkedIn portrait)
- Secondary: 1920x1080 (presentation slide)
- Safe margins: 64px

## Visual direction
- Clean, technical, trustworthy.
- Avoid stock “leaf” clichés; use precise icons and schematic lines.
- Style: light background with subtle grid or dot pattern.

## Typography (avoid default stacks)
- Headings: Space Grotesk or IBM Plex Sans
- Body: IBM Plex Sans or Source Sans 3
- Numerals: tabular variant for totals

## Color palette (accessible)
- Charcoal: #1F2937 (text)
- Off‑white: #F7F7F5 (background)
- Teal: #0F766E (primary accent)
- Moss: #5A7D3A (secondary accent)
- Amber: #D97706 (warnings)
- Slate: #94A3B8 (lines/labels)

## Layout (top to bottom)
1) **Header**
   - Title: “Product Carbon Footprint Calculator & Validator”
   - Subtitle: “From activity data to IDTA 02023‑compliant PCF in seconds”
   - Small badge: “Open Source • AAS‑ready”

2) **Problem Snapshot** (left‑right callout)
   - Left: “Spreadsheet sprawl” icon + 2 bullets (manual, no traceability)
   - Right: “Audit pain” icon + 2 bullets (source ambiguity, rework)

3) **How It Works (Pipeline)**
   - Horizontal pipeline with 5 boxes:
     1. Activities (electricity, transport, materials)
     2. Emission Factors (source/region/year)
     3. CO2e Calculation (Activity × Factor)
     4. Validation (IDTA 02023 rules)
     5. Export (AASX/JSON with trace)
   - Use arrows + small icons for each step.

4) **Calculator Spotlight (center feature)**
   - Mini mock of the PCF panel with 3 callouts:
     - “PCF Declaration” (reference unit, quantity, publication date)
     - “Activity table + factors”
     - “Total CO2e + Apply to Form”

5) **Validation Rules (right column)**
   - Two tiers:
     - Blocking: PcfCO2eq, ReferenceImpactUnitForCalculation, QuantityOfMeasureForCalculation, PublicationDate, LifeCyclePhases
     - Warnings: recommended fields, value list guidance, ExpirationDate > PublicationDate

6) **Standards + Provenance (bottom)**
   - Logos/labels: IDTA 02023, GHG Protocol scopes, AAS
   - Provenance note: “Calculation JSON + PCFActivities entry attached on export”

## Content copy (short, ready‑to‑use)
- “CO2e = Activity × Emission Factor”
- “Factor metadata: source, region, year”
- “Live compliance checks before export”
- “Audit‑ready trace in AAS output”

## Icons / visuals
- Activities: bolt, truck, factory
- Factors: database + tag
- Calculation: calculator
- Validation: shield/checklist
- Export: file box or AAS cube

## Data example (use in mock)
- Activity: Grid electricity
- Quantity: 10,000 kWh
- Factor: 0.417 kg CO2e/kWh
- Total: 4,170 kg CO2e

## Accessibility
- Minimum 4.5:1 contrast for text
- Use icons + labels, not color alone

## Deliverables
- 1x PNG (1080x1350)
- 1x PNG (1920x1080)
- Source file (Figma/Sketch)
