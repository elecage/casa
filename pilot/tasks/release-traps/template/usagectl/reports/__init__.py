"""리포트 절. 절마다 모듈 하나이고 ``render``를 내놓는다."""

from . import accounts, daily, months, percent, sources, totals

SECTIONS = {
    "accounts": accounts,
    "daily": daily,
    "months": months,
    "percent": percent,
    "sources": sources,
    "totals": totals,
}
