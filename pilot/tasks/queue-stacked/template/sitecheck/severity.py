"""검사마다의 심각도. 표기 방식은 아직 정해지지 않았다."""

from __future__ import annotations

SEVERITY = {
    "alias_cycle": "warn",
    "bool_literal": "error",
    "charset": "info",
    "comment_tag": "warn",
    "dup_keys": "error",
    "empty_section": "info",
    "encoding": "warn",
    "env_prefix": "error",
    "indent": "info",
    "known_hosts": "warn",
    "line_length": "error",
    "list_order": "info",
    "name_case": "warn",
    "null_value": "error",
    "owner_field": "info",
    "path_shape": "warn",
    "port_range": "error",
    "required_keys": "info",
    "schema_version": "warn",
    "size_limit": "error",
    "tab_mix": "info",
    "time_window": "warn",
    "trailing_ws": "error",
    "url_scheme": "info",
}
