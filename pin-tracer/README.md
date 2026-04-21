# Pin Replay Tracer

This directory contains the repository-owned Intel Pin tool used by replay-based reproduction. The tool records every executed instruction pointer plus the effective addresses of memory reads and writes.

## Build

Pin itself stays external to the repository. Either set `PIN_ROOT` or pass it directly on the `make` command line.

```sh
make -C pin-tracer PIN_ROOT=/path/to/pin TARGET=intel64 tools
make -C pin-tracer PIN_ROOT=/path/to/pin TARGET=ia32 tools
```

The Python reproducer builds the required target automatically when `tools.postprocess.reproduce_positives` is invoked with `--pin-root` or with `PIN_ROOT` set.

## Output

The tracer writes one event per line:

- `I <pc>` for each executed instruction
- `R <pc> <addr>` for each effective memory read address
- `W <pc> <addr>` for each effective memory write address

The reproducer compares two traces and maps the first diverging instruction back to source using DWARF debug info from the replay executable.
