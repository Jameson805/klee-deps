# BINSEC External Calls

This note documents the external-call limitations we have hit while running
BINSEC on the benchmarks in this repository, especially OpenSSL 1.1.1q,
Libgcrypt 1.10.1, and Mbed TLS 3.2.1.

The short version is:

- BINSEC works best when the benchmark executable is a normal non-PIE ELF whose
  crypto/library code is linked into the binary, but libc remains dynamically
  imported through ordinary PLT entries.
- BINSEC works poorly when execution reaches dynamic-loader machinery,
  finalization code, or glibc IFUNC dispatch.
- Our current workflow therefore prefers dynamic libc boundaries plus explicit
  BINSEC replacements for imported functions that are actually reached.

## Problem Shape

When BINSEC starts from `main`, it symbolically executes the benchmark binary
without a real userspace loader or full libc runtime. That creates several
failure modes around external calls:

1. Ordinary dynamic imports reached through `.plt`.
2. Special dynamic imports reached through `.plt.got`.
3. Static linking of glibc helpers that internally rely on IFUNC dispatch or
   loader-managed relocation state.
4. Startup and teardown code that is not part of the crypto primitive under
   test, but still gets explored because the benchmark begins at `main`.

Those cases look similar in the log, but they are not the same problem and do
not have the same fix.

## Case 1: Dynamic Linking Through Normal PLT Entries

This is the easiest case.

If the final benchmark executable imports a libc function through an ordinary
PLT stub, BINSEC can usually replace that function with a script stub. Typical
examples are `memcpy@plt`, `memset@plt`, `malloc@plt`, `fprintf@plt`, and so on.

Our current shared BINSEC prelude lives in:

- `configs/binsec/binsec_base.cfg`

The generator produces benchmark-local cfg files and then rewrites shared names
to the actual symbol surface of the built ELF in:

- `tools/generate_runner_artifacts.py`
- `tools/build_benchmark.py`

For example, a shared block like:

```cfg
replace <memcpy> (dest, src, n) by
  ...
end
```

is rewritten to:

```cfg
replace <memcpy@plt> (dest, src, n) by
  ...
end
```

when the final executable imports `memcpy` dynamically.

### Why We Prefer PLT Here

If a function remains an imported PLT call, the symbolic boundary is simple:
BINSEC sees one named call edge that we can stub directly.

This is the main reason our BINSEC build mode does **not** use `-fno-plt`, while
the non-BINSEC modes still do.

Relevant code:

- `tools/build_benchmark.py`

Current flag policy:

```python
noind_flags = ["-fno-pie", "-no-pie" if mode == "abacus" else "-Wl,-no-pie"]
if mode != "binsec":
    noind_flags.insert(1, "-fno-plt")

dep_cflags.append("-fno-pie")
if mode != "binsec":
    dep_cflags.append("-fno-plt")
dep_ldflags.append("-no-pie" if mode == "abacus" else "-Wl,-no-pie")
```

So for BINSEC we currently prefer:

- `-fno-pie`
- `-Wl,-no-pie`
- no `-fno-plt`

That gives us stable entry addresses and keeps libc imports as ordinary PLT
calls that are easy to intercept.

## Case 2: Dynamic Linking Through `.plt.got`

This is the awkward case.

Some imported functions do not appear as ordinary `.plt` stubs. A recurring
example is:

- `__cxa_finalize@plt`

In the affected binaries it lives in `.plt.got`, not `.plt`. BINSEC currently
does not handle this as cleanly as ordinary PLT hooks in our script flow.

In practice we observed:

- `halt at <__cxa_finalize@plt>` can fail during initial-state resolution.
- `replace <__cxa_finalize@plt> by ... end` can also fail during initial-state
  resolution.
- `replace <__cxa_finalize> by ... end` is not a reliable workaround either.

This is why the builder distinguishes ordinary PLT entries from `.plt.got`
entries.

Relevant code:

- `tools/build_benchmark.py`

The current behavior is:

- generate replacements for resolvable ordinary `.plt` / `.plt.sec` imports
- leave unresolved `.plt.got` imports as warnings

Example warning shape:

```text
WARNING: generated BINSEC config does not handle some PLT imports for fix_pub:
__cxa_finalize@plt. Starting BINSEC from <main> can fall into an unresolved PLT
resolver path if one of these is called.
```

### What This Usually Means Semantically

In our benchmarks, `__cxa_finalize@plt` is usually teardown noise rather than
the crypto primitive itself. It becomes a problem only when BINSEC explores a
path that enters finalization code.

Examples:

- OpenSSL paths that appear to wander into atexit/destructor cleanup.
- Libgcrypt/OpenSSL binaries that import `__cxa_atexit` and `__cxa_finalize`.

## Case 3: Static Linking and glibc IFUNC

This is the hardest case and the main reason we moved away from statically
linking glibc into BINSEC targets.

When glibc code such as `memcpy`, `memset`, or related helpers is linked
statically, those functions may not remain simple direct implementations.
Instead they can involve:

- IFUNC dispatch
- resolver-selected implementations
- relocation state initialized by the loader
- indirect jumps through loader-populated addresses

BINSEC does not model the host dynamic loader or IFUNC resolution process well
enough for this to be robust.

The symptom is often:

- jumps into non-executable addresses
- confusing resolver trampolines
- behavior that is much harder to stub than a normal `foo@plt` import

For this reason, our preferred BINSEC shape is **not** “fully static final
executable”. It is:

- benchmark/library code linked into the binary as needed
- libc kept dynamic
- imported libc calls handled at the PLT boundary

## Case 4: Startup and Teardown Machinery

Even when the binary shape is otherwise good, starting from `main` can still
pull BINSEC into code that is not relevant to the benchmark.

Examples we have seen:

- Libgcrypt initialization via `gcry_check_version(NULL)`
- FIPS/config probing via `getenv`, `access`, `fopen`, `fgets`, `feof`
- OpenSSL atexit/finalization registration

These paths are real code, but they are not the crypto primitive we want to
prove. They consume exploration budget and can trigger external-call failures.

Our runner change in:

- `include/runner.h`

uses `exit(driver_main())` for BINSEC mode so that normal benchmark completion
stops at `exit@plt` rather than returning past `main` into synthetic teardown.

That helped, but it does not eliminate all cleanup-related side paths.

## Current Repository Approach

Our current workflow combines several tactics.

### 1. Prefer Dynamic libc Boundaries

We build BINSEC targets as non-PIE executables and intentionally keep libc as a
dynamic import boundary.

Important flags and choices:

- `-fno-pie`
- `-Wl,-no-pie`
- do **not** use `-fno-plt` for BINSEC

For OpenSSL specifically, the benchmark descriptor currently uses:

```toml
./Configure --debug no-shared no-asm no-tests -DOPENSSL_AES_CONST_TIME {openssl_arch}
```

from:

- `configs/benchmarks/openssl.toml`

This means OpenSSL itself is built without shared `libcrypto.so`, but the final
benchmark executable still imports libc dynamically.

For Libgcrypt, the benchmark descriptor builds static library artifacts but also
keeps libc dynamic at the final executable boundary:

- `configs/benchmarks/libgcrypt.toml`

The relevant dependency configure flags are:

- `--enable-static`
- `--disable-shared`
- `--disable-asm` for Libgcrypt

Again, the point is not “everything static”; the point is “crypto library code
in the binary, libc still imported normally”.

### 2. Shared Stubs in `binsec_base.cfg`

We keep a shared set of replacements in:

- `configs/binsec/binsec_base.cfg`

These include memory, allocator, stdio, and environment helpers that we have
actually reached in the benchmarks.

Recent examples include:

- `getenv`
- `access`
- `fgets`
- `feof`
- `realloc`
- `explicit_bzero`

The goal is not to model libc perfectly. The goal is to keep execution on the
benchmark path and to give optional environment/file probes a conservative,
simple result.

### 3. Rewrite Shared Names to Real ELF Symbols

The builder rewrites abstract shared names like `memcpy` to the symbol shape the
binary actually exposes.

Relevant code:

- `tools/build_benchmark.py`

The rewrite logic uses ELF inspection to discover:

- defined symbols
- relocated symbols
- PLT entries

The current implementation uses:

- `pyelftools`
- `capstone`

instead of shelling out to `readelf` or `objdump` for the core discovery step.

### 4. Warn on Unhandled PLT Imports at Build Time

The builder prints a warning if generated cfgs still leave reachable imports
unstubbed.

This matters because a run that starts from `main` can otherwise fall into lazy
binding or resolver paths and then die much later with a generic `0x000000`
cut.

### 5. Use Runtime Assertion Stubs for Unresolved Ordinary PLT Imports

For unresolved imports that BINSEC can resolve as ordinary PLT stubs, the
builder now emits loud failure stubs instead of silent `halt at` guards.

The generated shape is:

```cfg
replace <symbol@plt> by
  assert 0x0<1> = 0x1<1>
  halt
end
```

This produces visible errors such as:

```text
[sse:error] Assertion failed @ 0x402030 (<getenv@plt>)
```

That is much more useful than a silent stop.

### 6. Keep `.plt.got` Imports as Warnings

We do **not** automatically emit replacement or halt directives for `.plt.got`
imports such as `__cxa_finalize@plt`, because that broke initial-state
resolution in our tests.

## Alternative Approaches

These are the alternatives we considered, along with the tradeoffs.

### Alternative A: Keep Adding Shared Stubs

This is the current pragmatic default.

Pros:

- simple to implement
- scales well when only a few imports are actually reached
- works well for ordinary `.plt` imports

Cons:

- easy to accidentally over-model libc with unrealistic behavior
- startup code can drag us into many unrelated helper functions
- does not solve `.plt.got` / finalization cases

### Alternative B: Make the Benchmark Entry Narrower

Instead of starting from a public top-level library API that performs global
initialization, call the narrower internal crypto function directly.

This is often the best semantic fix for libraries like Libgcrypt, where
`gcry_check_version()` and related initialization routines bring in a lot of
runtime machinery.

Pros:

- avoids unrelated startup/config/FIPS paths
- reduces the number of required external stubs
- keeps exploration budget focused on the cryptographic core

Cons:

- more benchmark-specific work
- requires understanding internal APIs and invariants

### Alternative C: Static-Link Everything

We do **not** recommend this for glibc-backed BINSEC targets.

Pros:

- fewer imported libc edges on paper

Cons:

- glibc IFUNC and loader-dependent dispatch become much harder to analyze
- many helpers no longer appear as easy-to-hook `@plt` imports
- can produce exactly the kind of opaque indirect control flow we are trying to
  avoid

### Alternative D: Catch Missing Calls Only at Runtime

This is useful only if runtime reporting is explicit.

Silent `halt at <foo@plt>` guards were not good enough because they only looked
like normal termination. The current assert-fail replacement stubs are a better
version of this idea.

### Alternative E: Suppress Cleanup Registration

For libraries like OpenSSL, another option is to change the benchmark build or
library configuration so atexit/destructor cleanup is not registered.

Pros:

- directly targets teardown noise

Cons:

- more intrusive than a simple stub
- may require library-specific source/config changes
- easy to diverge from upstream runtime behavior

## Recommended Practice in This Repository

For new BINSEC-integrated benchmarks, prefer the following order:

1. Build a non-PIE executable with dynamic libc imports.
2. Do not use `-fno-plt` in BINSEC mode.
3. Keep shared stubs in `configs/binsec/binsec_base.cfg` small and purposeful.
4. Let `tools/build_benchmark.py` rewrite generic names to `@plt` when
   available.
5. Use build-time warnings and runtime assertion stubs to identify the next
   missing ordinary PLT import.
6. If startup code keeps pulling in unrelated libc/runtime behavior, narrow the
   benchmark entry instead of endlessly stubbing the world.
7. Treat unresolved `.plt.got` imports, especially `__cxa_finalize@plt`, as a
   separate class of teardown/loader limitation.

## Current Known Limitations

- `__cxa_finalize@plt` remains warning-only in our current workflow.
- `0x000000` non-executable cuts can still appear on side paths that enter
  teardown/finalization machinery.
- A real leak finding can still be valid even when those side paths exist; the
  cleanup cuts mainly indicate incomplete coverage, not necessarily a bad main
  result.

## Files to Read Alongside This Note

- `configs/binsec/binsec_base.cfg`
- `tools/build_benchmark.py`
- `tools/generate_runner_artifacts.py`
- `configs/benchmarks/openssl.toml`
- `configs/benchmarks/libgcrypt.toml`
- `include/runner.h`
- `docs/runner-config.md`