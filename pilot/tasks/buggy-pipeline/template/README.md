# loglab

Small library that turns CSV access logs into per-time-window traffic
reports.

Pipeline: `loader` (CSV → rows) → `parser` (rows → records) →
`windowing` (records → fixed-size time windows) → `aggregate`
(per-window stats) → `report` (final dict / text).

## Usage

```python
from loglab import run
result = run(["data/sample.csv"])
```

## Tests

```
python -m pytest
```
