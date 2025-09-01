# Compiler and Linker
CC=clang-13
LD=llvm-link-13 # Used only for the klee target

# --- Common Settings ---
# Base source files
SOURCES = $(wildcard library/*.c)

# Base CFLAGS for all targets
BASE_CFLAGS = -isystem include/mbedtls -isystem library -I include -I /home/theta-lin/klee-controlflow/include -O0 -Xclang -disable-O0-optnone -g

# Linker flags (currently empty)
LDFLAGS =

# --- Klee Target (compiles to LLVM bitcode) ---
KLEE_SRCS = $(SOURCES) klee_main.c
KLEE_OBJS = $(KLEE_SRCS:.c=.klee.bc)
KLEE_CFLAGS = $(BASE_CFLAGS) -emit-llvm

# --- Trace Target (compiles to a native binary) ---
TRACE_SRCS = $(SOURCES) trace_main.c trace_cb.c
TRACE_OBJS = $(TRACE_SRCS:.c=.trace.o)
# Flags for compiling C to native object files (.o) WITHOUT the debug flag
TRACE_CFLAGS = $(BASE_CFLAGS) -fsanitize-coverage=trace-pc-guard

# --- BinSec/Rel Target (native, static linking) ---
BINSEC_SRCS = $(SOURCES) binsec_main.c
BINSEC_OBJS = $(BINSEC_SRCS:.c=.binsec.o)
BINSEC_CFLAGS = $(BASE_CFLAGS)
BINSEC_LD_FLAGS = -static

# --- Build Targets ---
.PHONY: all

# Default target builds both klee's bitcode and trace's executable
all: klee.bc trace modpow_binsec

# Phony target to build klee bitcode
klee: klee.bc

# Linking rule for the final 'klee' bitcode
klee.bc: $(KLEE_OBJS)
	@echo "LD (llvm-link-13) -> $@"
	$(LD) $(LDFLAGS) $^ -o $@

# Linking rule for the final 'trace' executable binary
trace: $(TRACE_OBJS)
	@echo "LD (clang-13) -> $@"
	$(CC) $(TRACE_CFLAGS) $^ -o $@

# Linking rule for the final 'modpow_binsec' executable binary
modpow_binsec: $(BINSEC_OBJS)
	@echo "LD (clang-13) -> $@"
	$(CC) $(BINSEC_LD_FLAGS) $^ -o $@

# --- Compilation Pattern Rules ---
# Rule to compile .c to .klee.bc for the klee target
%.klee.bc: %.c
	@echo "CC (clang-13) -> $@"
	$(CC) $(KLEE_CFLAGS) -c $< -o $@

# Rule to compile .c to .trace.o for the trace target
%.trace.o: %.c
	@echo "CC (clang-13) -> $@"
	$(CC) $(TRACE_CFLAGS) -c $< -o $@

# Rule to compile .c to .binsec.o for the binsec target
%.binsec.o: %.c
	@echo "CC (clang-13) -> $@"
	$(CC) $(BINSEC_CFLAGS) -c $< -o $@

# --- Clean Rule ---
clean:
	@echo "Cleaning up generated files..."
	find . -name '*.klee.bc' -delete
	find . -name '*.trace.o' -delete
	rm -f klee.bc trace
	