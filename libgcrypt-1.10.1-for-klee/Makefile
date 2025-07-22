# Toolchain
CC = clang-13
LD = llvm-link-13

# Paths
SRC_DIR = libgcrypt-1.10.1
BUILD_DIR = build

# Driver files
DRIVER_SRCS = driver.c
DRIVER_BCS = $(patsubst %.c,$(BUILD_DIR)/%.bc,$(DRIVER_SRCS))

# Libgcrypt source files (only MPI used, exact existing files)
MPI_SRC_DIR = $(SRC_DIR)/mpi
MPI_SRCS := \
    $(MPI_SRC_DIR)/mpicoder.c \
    $(MPI_SRC_DIR)/mpih-div.c \
    $(MPI_SRC_DIR)/mpih-mul.c \
    $(MPI_SRC_DIR)/mpi-add.c \
    $(MPI_SRC_DIR)/mpi-bit.c \
    $(MPI_SRC_DIR)/mpi-cmp.c \
    $(MPI_SRC_DIR)/mpi-div.c \
    $(MPI_SRC_DIR)/mpi-gcd.c \
    $(MPI_SRC_DIR)/mpi-inv.c \
    $(MPI_SRC_DIR)/mpi-mul.c \
    $(MPI_SRC_DIR)/mpi-pow.c \
    $(MPI_SRC_DIR)/mpi-scan.c \
    $(MPI_SRC_DIR)/mpiutil.c

LIBGCRYPT_BCS = $(patsubst $(SRC_DIR)/%.c,$(BUILD_DIR)/libgcrypt/%.bc,$(MPI_SRCS))

# Final linked output
FINAL_BC = $(BUILD_DIR)/klee.bc

# Flags
CFLAGS = -I$(SRC_DIR) -I$(SRC_DIR)/src -I$(SRC_DIR)/mpi \
         -I/home/james/klee-deps/klee-controlflow/include \
         -O0 -Xclang -disable-O0-optnone -emit-llvm -g -c

# Build targets
.PHONY: all clean

all: $(FINAL_BC)

# Link final bitcode: driver + libgcrypt
$(FINAL_BC): $(LIBGCRYPT_BCS) $(DRIVER_BCS)
	@echo "LD (llvm-link-13) -> $@"
	$(LD) $^ -o $@

# Compile libgcrypt source files to .bc
$(BUILD_DIR)/libgcrypt/%.bc: $(SRC_DIR)/%.c
	@echo "CC (clang-13) -> $@"
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $< -o $@

# Compile driver(s)
$(BUILD_DIR)/%.bc: %.c
	@echo "CC (clang-13) -> $@"
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $< -o $@

clean:
	rm -rf $(BUILD_DIR)
