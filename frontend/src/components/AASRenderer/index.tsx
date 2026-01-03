/**
 * Main recursive AASRenderer component.
 *
 * This component interprets the UI schema and renders appropriate
 * form fields for each SubmodelElement type.
 */

import React from 'react';
import { useFormContext } from 'react-hook-form';
import type { UIElementSchema } from '../../types/ui-schema';
import { isRequired } from '../../types/aas-elements';
import PropertyField from './PropertyField';
import CollectionField from './CollectionField';
import ListField from './ListField';
import MultiLangField from './MultiLangField';
import FileField from './FileField';
import RangeField from './RangeField';
import ReferenceField from './ReferenceField';

interface AASRendererProps {
  /** Element schema to render */
  schema: UIElementSchema;
  /** Form path for the element (e.g., "elements.ManufacturerName") */
  path: string;
  /** Current nesting depth (for styling) */
  depth?: number;
}

/**
 * Recursive renderer for SubmodelElements.
 *
 * Renders the appropriate field component based on the element's modelType.
 * For nested elements (SMC, SML, Entity), it recursively renders children.
 */
export const AASRenderer: React.FC<AASRendererProps> = ({
  schema,
  path,
  depth = 0,
}) => {
  const { control } = useFormContext();

  const getLabel = () => schema.semanticLabel || schema.idShort;
  const required = isRequired(schema.cardinality);

  const renderElement = () => {
    switch (schema.modelType) {
      case 'Property':
        return (
          <PropertyField
            path={`${path}.value`}
            schema={schema}
            label={getLabel()}
            required={required}
          />
        );

      case 'SubmodelElementCollection':
        return (
          <CollectionField path={path} schema={schema} depth={depth}>
            {schema.elements?.map((childSchema) => (
              <AASRenderer
                key={childSchema.idShort}
                schema={childSchema}
                path={`${path}.elements.${childSchema.idShort}`}
                depth={depth + 1}
              />
            ))}
          </CollectionField>
        );

      case 'SubmodelElementList':
        return (
          <ListField
            path={path}
            schema={schema}
            depth={depth}
            renderItem={(itemPath, index, itemSchema) => (
              <AASRenderer
                key={index}
                schema={itemSchema}
                path={itemPath}
                depth={depth + 1}
              />
            )}
          />
        );

      case 'MultiLanguageProperty':
        return (
          <MultiLangField
            path={`${path}.value`}
            schema={schema}
            label={getLabel()}
            required={required}
          />
        );

      case 'File':
        return (
          <FileField
            path={path}
            schema={schema}
            label={getLabel()}
            required={required}
          />
        );

      case 'Range':
        return (
          <RangeField
            path={path}
            schema={schema}
            label={getLabel()}
            required={required}
          />
        );

      case 'ReferenceElement':
        return (
          <ReferenceField
            path={`${path}.value`}
            schema={schema}
            label={getLabel()}
            required={required}
          />
        );

      case 'Entity':
        return (
          <CollectionField
            path={path}
            schema={schema}
            depth={depth}
            title={`${getLabel()} (Entity)`}
          >
            {schema.globalAssetId !== undefined && (
              <PropertyField
                path={`${path}.globalAssetId`}
                schema={{
                  ...schema,
                  modelType: 'Property',
                  valueType: 'xs:string',
                  idShort: 'globalAssetId',
                }}
                label="Global Asset ID"
                required={false}
              />
            )}
            {schema.statements?.map((stmtSchema) => (
              <AASRenderer
                key={stmtSchema.idShort}
                schema={stmtSchema}
                path={`${path}.statements.${stmtSchema.idShort}`}
                depth={depth + 1}
              />
            ))}
          </CollectionField>
        );

      case 'Blob':
        return (
          <div className="aas-element aas-blob" style={{ marginLeft: depth * 16 }}>
            <label className="aas-label">{getLabel()}</label>
            <span className="aas-unsupported">Blob editing not supported in UI</span>
          </div>
        );

      case 'RelationshipElement':
      case 'AnnotatedRelationshipElement':
        return (
          <div className="aas-element aas-relationship" style={{ marginLeft: depth * 16 }}>
            <label className="aas-label">{getLabel()}</label>
            <div className="aas-relationship-fields">
              <ReferenceField
                path={`${path}.first`}
                schema={schema}
                label="First"
                required={required}
              />
              <ReferenceField
                path={`${path}.second`}
                schema={schema}
                label="Second"
                required={required}
              />
            </div>
          </div>
        );

      case 'Operation':
      case 'Capability':
      case 'BasicEventElement':
        return (
          <div className="aas-element aas-readonly" style={{ marginLeft: depth * 16 }}>
            <label className="aas-label">{getLabel()}</label>
            <span className="aas-unsupported">
              {schema.modelType} is read-only
            </span>
          </div>
        );

      default:
        return (
          <div className="aas-element aas-unknown" style={{ marginLeft: depth * 16 }}>
            <label className="aas-label">{getLabel()}</label>
            <span className="aas-warning">
              Unsupported element type: {schema.modelType}
            </span>
          </div>
        );
    }
  };

  return (
    <div
      className={`aas-renderer aas-depth-${depth}`}
      data-model-type={schema.modelType}
      data-id-short={schema.idShort}
    >
      {renderElement()}
    </div>
  );
};

export default AASRenderer;
