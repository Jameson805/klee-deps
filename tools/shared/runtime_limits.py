"""Runtime safety limits used by command-line tooling."""

from __future__ import annotations


def configure_int_max_str_digits(limit: int = 100000) -> None:
    """Raise Python's int-string conversion limit when supported.

    Python 3.11+ defaults to a low guardrail for decimal int<->str conversion,
    which can break parsing of very large counterexample values.
    """
    import sys

    setter = getattr(sys, "set_int_max_str_digits", None)
    if callable(setter):
        setter(limit)
