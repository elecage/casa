# exportkit

Exports lists of records (dicts with `id`, `name`, `value`) to pluggable
output formats. Formats live in `src/exportkit/exporters/`, one module per
format, and register themselves into the registry at import time.

```python
from exportkit import registry
text = registry.get("json").export(records)
```

## Supported formats

| format | extension |
|---|---|
| `csv` | `.csv` |
| `json` | `.json` |
| `xml` | `.xml` |
| `yaml` | `.yaml` |

This table is the public reference for consumers — keep it in sync with
the registry.
