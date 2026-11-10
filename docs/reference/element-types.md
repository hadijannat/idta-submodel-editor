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


## Repeatable Elements

Many templates let an element occur several times without using a list: the
element has a cardinality of `ZeroToMany` or `OneToMany` and every occurrence
is a sibling with an idShort of its own. In the form such an element has an
"Add another ..." button, and each further occurrence can be removed again.
The first occurrence is the element itself and cannot be removed.

This applies to elements directly inside the submodel, a collection or an
entity. Items of a `SubmodelElementList` repeat through their list, and
`Operation`, `Capability` and `BasicEventElement` are read-only.

In form data the further occurrences are listed on the element:

```json
{
  "elements": {
    "Phone": {
      "value": "+49 30 1234",
      "occurrences": [{ "value": "+49 30 5678" }]
    }
  }
}
```

Each occurrence has the same shape as the element and is validated like it.
The schema marks such elements with `repeatable: true`, and `occurrences` on
any other element is a validation error.

On export every occurrence becomes a sibling right after the element. Its
idShort continues the counter of the template (`Mode__00__` is followed by
`Mode__01__`); an idShort without a counter gets one appended, so `Phone` is
followed by `Phone__01__`. A new occurrence starts empty and does not inherit
example values from the template.

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
