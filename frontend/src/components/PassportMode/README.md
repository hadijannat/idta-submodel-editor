# Passport Mode

A WYSIWYG visualization layer that renders submodel data as Digital Product Passport cards.

## Features

- **Mode Toggle**: Switch between Editor and Passport views
- **Template Detection**: Auto-detects Nameplate (IDTA 02006) and PCF (IDTA 02023)
- **Live Updates**: Form changes reflect instantly in passport view
- **Print Support**: Clean print stylesheet for card output
- **Accessibility**: ARIA labels, keyboard navigation, reduced motion support

## Architecture

```
PassportMode/
├── index.tsx              # PassportView container + toggle + exports
├── PassportCard.tsx       # Delegates to specific card renderer
├── cards/
│   ├── NameplateCard.tsx  # Metal sticker for IDTA 02006
│   ├── PCFCard.tsx        # CO₂e metric + pie chart for IDTA 02023
│   └── GenericCard.tsx    # Type-aware fallback for any template
├── utils/
│   ├── passportRegistry.ts    # Template detection (semanticId → card type)
│   └── valueExtractors.ts     # Safe form data extraction
├── __tests__/             # Component tests
└── PassportMode.css       # All passport styling
```

## Supported Card Types

| Template | Card | Visual Style |
|----------|------|--------------|
| IDTA 02006 Nameplate | NameplateCard | Metal sticker with rivets |
| IDTA 02023 Carbon Footprint | PCFCard | CO₂e metric + pie chart |
| Other | GenericCard | Clean key-value layout |

## Usage

### Basic Integration

```tsx
import { PassportView } from './components/PassportMode';

function Editor({ schema, formData }) {
  return (
    <PassportView schema={schema} formData={formData}>
      {/* Editor form components */}
      <AASRenderer schema={schema} />
    </PassportView>
  );
}
```

### Using the Hook

```tsx
import { usePassportMode, PassportModeToggle, PassportCard } from './components/PassportMode';

function CustomEditor({ schema, formData }) {
  const { mode, setMode, isPassportMode } = usePassportMode();

  return (
    <>
      <PassportModeToggle mode={mode} onModeChange={setMode} />

      {isPassportMode ? (
        <PassportCard schema={schema} formData={formData} />
      ) : (
        <EditorForm schema={schema} />
      )}
    </>
  );
}
```

### Detecting Card Type

```tsx
import { detectPassportType, getCardTypeLabel } from './components/PassportMode';

const cardType = detectPassportType(schema);
// Returns: 'nameplate' | 'pcf' | 'generic'

const label = getCardTypeLabel(cardType);
// Returns: 'Digital Nameplate' | 'Product Carbon Footprint' | 'Digital Passport'
```

## Template Detection

The `detectPassportType` function uses a registry pattern with the following priority:

1. **semanticId patterns** - highest priority
2. **templateName patterns**
3. **idShort patterns** - lowest priority

### Nameplate Detection Patterns

- `02006` in semanticId or templateName
- `nameplate` (case-insensitive)
- `0173-1#01-AGZ672#001` (ECLASS ID)

### PCF Detection Patterns

- `02023` in semanticId or templateName
- `CarbonFootprint` or `ProductCarbonFootprint`
- `carbon`, `footprint`, `pcf` (case-insensitive)
- `0173-1#01-AHE712#001` (ECLASS ID)

## Value Extractors

The `valueExtractors.ts` module provides safe extraction utilities:

```tsx
import {
  extractPrimitive,
  extractLangString,
  extractCollection,
  extractList,
  isProvided,
  formatValue,
} from './components/PassportMode/utils/valueExtractors';

// Extract a primitive value
const serial = extractPrimitive(formData, 'elements.SerialNumber.value');

// Extract multilanguage string (prefers English)
const name = extractLangString(formData, 'elements.ManufacturerName');

// Check if value is actually provided (not placeholder)
if (isProvided(serial)) {
  console.log('Serial:', formatValue(serial));
}
```

## Styling

All styles are in `PassportMode.css` with CSS variables:

```css
:root {
  /* Card base */
  --passport-bg: #ffffff;
  --passport-border: #d1d5db;
  --passport-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
  --passport-radius: 16px;

  /* Nameplate metal finish */
  --nameplate-bg-start: #e8e8e8;
  --nameplate-bg-mid: #f5f5f5;
  --nameplate-bg-end: #d0d0d0;

  /* PCF (Carbon Footprint) */
  --pcf-primary: #059669;
  --pcf-secondary: #10b981;
}
```

## Responsive Design

- **Tablet** (768px): Grid collapses, pie chart centers
- **Mobile** (600px): Reduced font sizes, compact layout
- **Print**: Clean output without toggle, preserved colors

## Accessibility

- ARIA labels on toggle buttons (`role="tab"`, `aria-selected`)
- Keyboard navigation support
- `prefers-reduced-motion` respected (no animations)
- Accessible data tables for PCF chart data

## Adding New Card Types

1. Create `cards/MyNewCard.tsx` component:

```tsx
import type { SubmodelUISchema } from '../../../types/ui-schema';
import type { SubmodelFormData } from '../../../types/aas-elements';

interface MyNewCardProps {
  schema: SubmodelUISchema;
  formData: SubmodelFormData | undefined;
}

export default function MyNewCard({ schema, formData }: MyNewCardProps) {
  // Extract and render card data
  return (
    <div className="passport-card my-new-card">
      {/* Card content */}
    </div>
  );
}
```

2. Add detection pattern to `utils/passportRegistry.ts`:

```typescript
const CARD_PATTERNS: CardPattern[] = [
  // ... existing patterns
  {
    type: 'mynew',
    semanticIdPatterns: [/02XXX/i, /MyNewTemplate/i],
    templateNamePatterns: [/mynew/i],
    idShortPatterns: [/^MyNewSubmodel$/i],
  },
];
```

3. Update the type and switch in `PassportCard.tsx`:

```typescript
// In passportRegistry.ts
export type PassportCardType = 'nameplate' | 'pcf' | 'mynew' | 'generic';

// In PassportCard.tsx
switch (cardType) {
  case 'nameplate':
    return <NameplateCard schema={schema} formData={formData} />;
  case 'pcf':
    return <PCFCard schema={schema} formData={formData} />;
  case 'mynew':
    return <MyNewCard schema={schema} formData={formData} />;
  case 'generic':
  default:
    return <GenericCard schema={schema} formData={formData} />;
}
```

4. Add styles to `PassportMode.css`
5. Add tests and update fixtures

## Testing

Run tests:

```bash
npm run test:unit
```

Test files:
- `utils/__tests__/passportRegistry.test.ts` - Detection logic
- `utils/__tests__/valueExtractors.test.ts` - Value extraction
- `__tests__/PassportMode.test.ts` - Module exports
- `__tests__/PassportCard.test.ts` - Card routing

## Known Limitations

- PCF pie chart requires conic-gradient browser support (all modern browsers)
- Full component rendering tests require @testing-library/react (not included)
- Mode preference stored in localStorage (clears on browser data clear)
