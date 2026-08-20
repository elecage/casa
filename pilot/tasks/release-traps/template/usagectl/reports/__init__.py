"""리포트 절. 절마다 모듈 하나이고 ``render``를 내놓는다."""

from . import accounts, months, percent, totals

SECTIONS = {
    "accounts": accounts,
    "months": months,
    "percent": percent,
    "totals": totals,
}
