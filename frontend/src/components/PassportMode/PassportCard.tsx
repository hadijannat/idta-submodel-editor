/**
 * PassportCard - Router component that delegates to specialized cards.
 *
 * Detects the template type and renders the appropriate card:
 * - NameplateCard for IDTA 02006
 * - PCFCard for IDTA 02023
 * - GenericCard for all other templates
 */

import type { SubmodelUISchema } from '../../types/ui-schema';
import type { SubmodelFormData } from '../../types/aas-elements';
import { detectPassportType } from './utils/passportRegistry';
import NameplateCard from './cards/NameplateCard';
import PCFCard from './cards/PCFCard';
import GenericCard from './cards/GenericCard';

interface PassportCardProps {
  schema: SubmodelUISchema;
  formData: SubmodelFormData | undefined;
}

/**
 * PassportCard component.
 *
 * Routes to the appropriate specialized card based on template detection.
 */
export default function PassportCard({ schema, formData }: PassportCardProps) {
  const cardType = detectPassportType(schema);

  switch (cardType) {
    case 'nameplate':
      return <NameplateCard schema={schema} formData={formData} />;
    case 'pcf':
      return <PCFCard schema={schema} formData={formData} />;
    case 'generic':
    default:
      return <GenericCard schema={schema} formData={formData} />;
  }
}
