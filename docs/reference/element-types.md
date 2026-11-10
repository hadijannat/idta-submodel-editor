# Supported Element Types

The editor supports the following AAS SubmodelElement types:

| Element Type | Editing Support |
|--------------|-----------------|
| Property | Full |
| SubmodelElementCollection | Full (recursive) |
| SubmodelElementList | Full (add/remove items) |
| MultiLanguageProperty | Full (tabbed interface) |
| File | Full (path/URL + content type) |
| Range | Full (min/max) |
| ReferenceElement | Full |
| Entity | Full |
| Blob | Partial (upload/download + content type + payload edit) |
| RelationshipElement | Full (first/second reference editing) |
| AnnotatedRelationshipElement | Partial (first/second + annotation value editing) |
| Operation | Read-only |
| Capability | Read-only |
| BasicEventElement | Read-only |

## Element Type Details

### Property
Standard key-value fields with type validation based on `valueType` (string, int, double, boolean, etc.).

### SubmodelElementCollection
Container element rendered as a collapsible section. Supports unlimited nesting depth.

### SubmodelElementList
Ordered list of elements with add/remove controls. Supports typed items and cardinality constraints.

### MultiLanguageProperty
Language-tagged strings rendered with a tabbed interface for multiple locales.

### File
File reference with path/URL input and MIME type selector. Supports upload or external URL.

### Range
Min/max value pair with numeric validation.

### ReferenceElement
Reference to external AAS elements with key chain editing.

### Entity
Entity with global/self-managed asset ID and statements collection. A
self-managed entity is identified by its asset ID, so the Global Asset ID is
required for it; templates usually leave it empty for you to fill in.

### Blob
Editable payload and content type. Supports upload/download and `base64:` payloads for binary data.

### RelationshipElement
Editable `first` and `second` references.

### AnnotatedRelationshipElement
Editable relationship references plus annotation value editing for available annotation elements.

### Operation
Rendered as read-only metadata because invocation is runtime-dependent and not part of template value hydration.


## Reading Templates

Published templates are read as they are, including content that the AAS
metamodel only accepts in a finished submodel:

- a self-managed entity whose asset ID is still to be entered
- a list declared with an abstract element type (`SubmodelElement`,
  `DataElement`, `EventElement`) that holds elements of different types
- a qualifier type that is repeated on one element (the first one is used)
- package parts that are marked as external although they are in the package

If something still cannot be read, the form says so above the first field
("This template could not be read completely") with the number of missing
elements and the reason. The same list is returned as `readWarnings` by the
schema endpoints. It also notes when a package holds several submodels, of
which the form shows one.
