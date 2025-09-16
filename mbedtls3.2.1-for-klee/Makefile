# Compiler and Linker
CC=clang-13
LD=llvm-link-13 # Used only for the klee target

# --- Common Settings ---
# Base source files (exclude main.c since it's the old driver)
SOURCES = $(filter-out mbedtls3.2.1/main.c,$(wildcard mbedtls3.2.1/library/*.c))

# Base CFLAGS for all targets
BASE_CFLAGS = -isystem mbedtls3.2.1/include/mbedtls -isystem mbedtls3.2.1/library \
              -I mbedtls3.2.1/include -I /home/james/klee-deps/klee-controlflow/include \
              -O0 -Xclang -disable-O0-optnone -g

# Linker flags (currently empty)
LDFLAGS =

# --- Klee Target (compiles to LLVM bitcode) ---
KLEE_SRCS = $(SOURCES) klee_driver.c bignum_sliced_full.c
KLEE_OBJS = $(KLEE_SRCS:.c=.klee.bc)
KLEE_CFLAGS = $(BASE_CFLAGS) -emit-llvm

# --- Trace Target (compiles to a native binary) ---
TRACE_SRCS = $(SOURCES) trace_cb.c
TRACE_OBJS = $(TRACE_SRCS:.c=.trace.o)
TRACE_CFLAGS = $(BASE_CFLAGS) -fsanitize-coverage=trace-pc-guard -DTRACE

# --- Build Targets ---
.PHONY: all klee clean

# Default target builds both klee's bitcode and trace's executable
all: klee.bc trace

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

# --- Compilation Pattern Rules ---
%.klee.bc: %.c
	@echo "CC (clang-13) -> $@"
	$(CC) $(KLEE_CFLAGS) -c $< -o $@

%.trace.o: %.c
	@echo "CC (clang-13) -> $@"
	$(CC) $(TRACE_CFLAGS) -c $< -o $@

# --- Clean Rule ---
clean:
	@echo "Cleaning up generated files..."
	find . -name '*.klee.bc' -delete
	find . -name '*.trace.o' -delete
	rm -f klee.bc trace
