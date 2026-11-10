/**
 * Default form data for a new element: a new list item, or a further
 * occurrence of a repeatable element.
 */

import type { UIElementSchema } from '../../types/ui-schema';
import type { ElementFormData } from '../../types/aas-elements';

/**
 * Create default value for a new list item, or for a further occurrence of a
 * repeatable element.
 */
export function createDefaultItem(template: UIElementSchema | null): ElementFormData {
  const withSemanticDefaults = (
    defaults: ElementFormData,
    source?: UIElementSchema | null
  ): ElementFormData => ({
    ...defaults,
    semanticId: source?.semanticId ?? null,
    valueId: source?.valueId ?? null,
    semanticIdListElement: source?.semanticIdListElement ?? null,
  });

  if (!template) return withSemanticDefaults({ value: '' });

  switch (template.modelType) {
    case 'Property':
      return withSemanticDefaults(
        { value: template.inputType === 'checkbox' ? (template.value ?? false) : '' },
        template
      );

    case 'MultiLanguageProperty':
      return withSemanticDefaults({ value: {} }, template);

    case 'SubmodelElementCollection': {
      const elements: Record<string, ElementFormData> = {};
      for (const child of template.elements || []) {
        elements[child.idShort] = createDefaultItem(child);
      }
      return withSemanticDefaults({ elements }, template);
    }

    case 'SubmodelElementList':
      return withSemanticDefaults({
        items: (template.items || []).map((item) => createDefaultItem(item)),
        semanticIdListElement: template.semanticIdListElement ?? null,
      }, template);

    case 'Range':
      return withSemanticDefaults({ min: '', max: '' }, template);

    case 'File':
      return withSemanticDefaults({
        value: template.value ?? '',
        contentType: template.contentType ?? '',
      }, template);

    case 'Blob':
      return withSemanticDefaults({
        value: template.value ?? '',
        contentType: template.contentType ?? 'application/octet-stream',
        valueEncoding: template.valueEncoding ?? 'utf-8',
      }, template);

    case 'ReferenceElement':
      return withSemanticDefaults({ value: '' }, template);

    case 'Entity': {
      const statements: Record<string, ElementFormData> = {};
      for (const statement of template.statements || []) {
        statements[statement.idShort] = createDefaultItem(statement);
      }
      return withSemanticDefaults({
        globalAssetId: template.globalAssetId ?? '',
        statements,
      }, template);
    }

    case 'RelationshipElement':
      return withSemanticDefaults({
        first: template.first ?? '',
        second: template.second ?? '',
      }, template);

    case 'AnnotatedRelationshipElement':
      return withSemanticDefaults({
        first: template.first ?? '',
        second: template.second ?? '',
        annotations: (template.annotations || []).map((annotation) =>
          createDefaultItem(annotation)
        ),
      }, template);

    default:
      return withSemanticDefaults({ value: '' }, template);
  }
}
