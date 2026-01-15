import type { SubmodelUISchema, UIElementSchema } from '../types/ui-schema';
import type { ElementFormData, SubmodelFormData } from '../types/aas-elements';
import { isRequired } from '../types/aas-elements';

export type CompletionMetrics = {
  required: number;
  completed: number;
};

export const hasValue = (value: unknown): boolean => {
  if (value === null || value === undefined) return false;
  if (typeof value === 'string') return value.trim().length > 0;
  if (typeof value === 'number') return true;
  if (typeof value === 'boolean') return true;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === 'object') {
    return Object.values(value).some(hasValue);
  }
  return true;
};

export const countElementCompletion = (
  element: UIElementSchema,
  data?: ElementFormData
): CompletionMetrics => {
  const required = isRequired(element.cardinality);

  switch (element.modelType) {
    case 'SubmodelElementCollection': {
      const children = element.elements ?? [];
      return children.reduce<CompletionMetrics>(
        (acc, child) => {
          const childData = data?.elements?.[child.idShort];
          const counts = countElementCompletion(child, childData);
          acc.required += counts.required;
          acc.completed += counts.completed;
          return acc;
        },
        { required: 0, completed: 0 }
      );
    }

    case 'Entity': {
      const statements = element.statements ?? [];
      return statements.reduce<CompletionMetrics>(
        (acc, child) => {
          const childData = data?.statements?.[child.idShort];
          const counts = countElementCompletion(child, childData);
          acc.required += counts.required;
          acc.completed += counts.completed;
          return acc;
        },
        { required: 0, completed: 0 }
      );
    }

    case 'SubmodelElementList': {
      const items = data?.items ?? [];
      if (items.length === 0) {
        return required ? { required: 1, completed: 0 } : { required: 0, completed: 0 };
      }

      if (element.itemTemplate) {
        return items.reduce<CompletionMetrics>(
          (acc, item) => {
            const counts = countElementCompletion(element.itemTemplate as UIElementSchema, item);
            acc.required += counts.required;
            acc.completed += counts.completed;
            return acc;
          },
          { required: 0, completed: 0 }
        );
      }

      return required ? { required: 1, completed: 1 } : { required: 0, completed: 0 };
    }

    case 'Range': {
      if (!required) return { required: 0, completed: 0 };
      const filled = hasValue(data?.min) && hasValue(data?.max);
      return { required: 1, completed: filled ? 1 : 0 };
    }

    case 'MultiLanguageProperty': {
      if (!required) return { required: 0, completed: 0 };
      const filled = hasValue(data?.value);
      return { required: 1, completed: filled ? 1 : 0 };
    }

    default: {
      if (!required) return { required: 0, completed: 0 };
      const filled = hasValue(data?.value);
      return { required: 1, completed: filled ? 1 : 0 };
    }
  }
};

export const computeCompletion = (
  schema: SubmodelUISchema | null,
  values?: SubmodelFormData
): CompletionMetrics => {
  if (!schema) return { required: 0, completed: 0 };

  return schema.elements.reduce<CompletionMetrics>(
    (acc, element) => {
      const elementData = values?.elements?.[element.idShort];
      const counts = countElementCompletion(element, elementData);
      acc.required += counts.required;
      acc.completed += counts.completed;
      return acc;
    },
    { required: 0, completed: 0 }
  );
};
