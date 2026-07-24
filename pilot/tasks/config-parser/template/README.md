# minicfg

A small INI-like configuration parser: sections, comments, quoted values
with escapes, and line continuation. The public API is `minicfg.parse`,
which turns configuration text into a flat `{key: value}` dictionary.

The full parsing contract is documented in the `parse` docstring
(`src/minicfg/parser.py`). Run the tests with `python -m pytest`.
