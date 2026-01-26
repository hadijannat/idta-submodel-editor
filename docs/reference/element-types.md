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
| Blob | Read-only |
| RelationshipElement | Partial |
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
Entity with global/self-managed asset ID and statements collection.
