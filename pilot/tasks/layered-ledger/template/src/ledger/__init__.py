"""ledger — a small layered money system.

Layers: money (value object) -> validation (boundary gate) -> domain
(operations) -> serialize (formatting boundary) -> repository (store) ->
api (entry points). A single cross-cutting contract runs through all of
them; see each module's docstring.
"""

from .money import Money

__all__ = ["Money"]
