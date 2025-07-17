#!/bin/bash
set -e

# Paths to tools
CLANG=clang-13
LLVM_LINK=llvm-link-13
KLEE=~/klee-deps/klee-controlflow/build/bin/klee

# Include paths
MBEDTLS_INCLUDE=./mbedtls/include
KLEE_INCLUDE=~/klee-deps/klee-controlflow/include

# Clean previous bitcode and KLEE output
rm -f *.bc linked.bc
rm -rf klee-out-0

echo "Compiling mbedtls driver to bitcode..."
$CLANG -I${MBEDTLS_INCLUDE} -I${KLEE_INCLUDE} -emit-llvm -c -g mbedtls_driver.c -o mbedtls_driver.bc

echo "Generating bitcode for mbedtls library via Makefile..."
make -C mbedtls/library llvm-bc

echo "Linking all bitcode files..."
$LLVM_LINK -o linked.bc mbedtls_driver.bc mbedtls/library/llvm-bc/*.bc

echo "Running KLEE..."
$KLEE \
  --output-dir=klee-out-0 \
  --max-tests=1000 \
  --max-depth=1000 \
  --max-time=1800 \
  --search=nurs:covnew \
  --search=dfs \
  linked.bc

echo "KLEE run complete."
