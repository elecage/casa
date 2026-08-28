"""옛 등록 방식. 이름과 함수를 손으로 묶어 둔 표다."""

from __future__ import annotations

from .checks.alias_cycle import check_alias_cycle
from .checks.bool_literal import check_bool_literal
from .checks.charset import check_charset
from .checks.comment_tag import check_comment_tag
from .checks.dup_keys import check_dup_keys
from .checks.empty_section import check_empty_section
from .checks.encoding import check_encoding
from .checks.env_prefix import check_env_prefix
from .checks.indent import check_indent
from .checks.known_hosts import check_known_hosts
from .checks.line_length import check_line_length
from .checks.list_order import check_list_order
from .checks.name_case import check_name_case
from .checks.null_value import check_null_value
from .checks.owner_field import check_owner_field
from .checks.path_shape import check_path_shape
from .checks.port_range import check_port_range
from .checks.required_keys import check_required_keys
from .checks.size_limit import check_size_limit
from .checks.tab_mix import check_tab_mix
from .checks.time_window import check_time_window
from .checks.trailing_ws import check_trailing_ws
from .checks.url_scheme import check_url_scheme


LEGACY_CHECKS = {
    "alias_cycle": check_alias_cycle,
    "bool_literal": check_bool_literal,
    "charset": check_charset,
    "comment_tag": check_comment_tag,
    "dup_keys": check_dup_keys,
    "empty_section": check_empty_section,
    "encoding": check_encoding,
    "env_prefix": check_env_prefix,
    "indent": check_indent,
    "known_hosts": check_known_hosts,
    "line_length": check_line_length,
    "list_order": check_list_order,
    "name_case": check_name_case,
    "null_value": check_null_value,
    "owner_field": check_owner_field,
    "path_shape": check_path_shape,
    "port_range": check_port_range,
    "required_keys": check_required_keys,
    "size_limit": check_size_limit,
    "tab_mix": check_tab_mix,
    "time_window": check_time_window,
    "trailing_ws": check_trailing_ws,
    "url_scheme": check_url_scheme,
}
