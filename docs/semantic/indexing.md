# Semantic Dictionary Indexing

This project supports offline semantic dictionary lookup using a local SQLite
FTS index. You can build indexes from CSV or JSON exports and point the server
at the resulting database.

## Build an index

```bash
python backend/scripts/semantic_import.py \
  --input /path/to/eclass_export.json \
  --output /data/semantic/eclass.sqlite
```

Supported input fields (CSV header or JSON keys):
- `canonicalId` (required)
- `canonicalIri`
- `kind` (property|class|unit|value)
- `preferredName` (JSON map or string)
- `definition` (JSON map or string)
- `datatypeHint`
- `unitHint`
- `synonyms` (JSON list or comma-separated string)

## Configure the server

Set the environment variables to point at the index files:

```bash
SEMANTIC_ENABLED=true
SEMANTIC_PREFER_IRI=true
SEMANTIC_ECLASS_OFFLINE_ENABLED=true
SEMANTIC_IEC_CDD_OFFLINE_ENABLED=true
ECLASS_INDEX_PATH=/data/semantic/eclass.sqlite
IEC_CDD_INDEX_PATH=/data/semantic/iec_cdd.sqlite
```

If the SQLite index is not found, the backend falls back to sample JSON indexes
bundled in `backend/app/services/semantic/data`.

## Online provider (optional)

Enable the ECLASS webservice provider by setting:

```bash
SEMANTIC_ECLASS_ONLINE_ENABLED=true
ECLASS_API_BASE=https://your-eclass-gateway.example.com
ECLASS_SEARCH_URL=/search
ECLASS_RESOLVE_URL=/resolve
ECLASS_CERT_PATH=/run/secrets/eclass_cert.pem
ECLASS_KEY_PATH=/run/secrets/eclass_key.pem
```

The online provider expects JSON responses that already map to the normalized
fields (`canonicalId`, `preferredName`, `definition`, etc.). If you use a custom
gateway, ensure it returns that shape or extend the provider mapping.

## Notes

- Do not commit licensed ECLASS/IEC CDD exports to the repo.
- Keep the SQLite index on persistent storage for production deployments.
