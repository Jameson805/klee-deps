#!/usr/bin/env python3
"""Generate deterministic BearSSL expanded-schedule defaults.

The BearSSL CBC table benchmarks expose expanded schedule storage directly as
`skey_buf`. ABACUS needs a concrete seed before it marks that buffer symbolic,
so the seed should be a real expanded schedule rather than an arbitrary integer.
This compatibility utility prints the BearSSL rows from
`generate_crypto_input_defaults`, which owns the shared key choices.
"""

from __future__ import annotations

import sys
from subprocess import CalledProcessError

from tools.utilities.generate_crypto_input_defaults import build_parser, generate_bearssl_schedules


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        output = generate_bearssl_schedules(args.cc)
    except CalledProcessError as error:
        print(f"error: helper command failed with exit code {error.returncode}", file=sys.stderr)
        return error.returncode or 1
    except OSError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(output, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
