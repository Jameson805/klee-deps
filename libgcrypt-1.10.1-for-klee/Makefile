# Toolchain
CC = clang-13
LD = llvm-link-13

# Paths
SRC_DIR = libgcrypt-1.10.1
GPG_ERROR_DIR = libgpg-error-1.44/src
BUILD_DIR = build

# Files
KLEE_DRIVER_SRCS = klee_driver.c
BINSEC_DRIVER_SRCS = binsec_driver.c
STUB_SRC = stubs.c

# Only needed libgpg-error files
LIBGPG_ERROR_SRCS = \
    $(GPG_ERROR_DIR)/strsource.c \
    $(GPG_ERROR_DIR)/strerror.c \
    $(GPG_ERROR_DIR)/code-to-errno.c \
    $(GPG_ERROR_DIR)/init.c \
    $(GPG_ERROR_DIR)/visibility.c \
    $(GPG_ERROR_DIR)/estream.c \
    $(GPG_ERROR_DIR)/code-from-errno.c \
    $(GPG_ERROR_DIR)/posix-lock.c

# libgcrypt MPI files
MPI_SRC_DIR = $(SRC_DIR)/mpi
MPI_SRCS = $(wildcard $(MPI_SRC_DIR)/*.c)

SRCS = $(SRC_DIR)/src/visibility.c \
    $(SRC_DIR)/src/global.c \
    $(SRC_DIR)/src/fips.c \
    $(SRC_DIR)/src/misc.c \
    $(SRC_DIR)/src/secmem.c \
    $(SRC_DIR)/src/stdmem.c

# Derived bitcode paths
BCS = $(patsubst %.c,$(BUILD_DIR)/%.bc,$(KLEE_DRIVER_SRCS)) \
    $(patsubst $(GPG_ERROR_DIR)/%.c,$(BUILD_DIR)/libgpg-error/%.bc,$(LIBGPG_ERROR_SRCS)) \
    $(patsubst $(SRC_DIR)/src/%.c,$(BUILD_DIR)/libgcrypt/src/%.bc,$(SRCS)) \
    $(patsubst $(MPI_SRC_DIR)/%.c,$(BUILD_DIR)/libgcrypt/mpi/%.bc,$(MPI_SRCS))

FINAL_BC = $(BUILD_DIR)/klee.bc

BINSEC_OBJS = $(patsubst %.c,$(BUILD_DIR)/%.binsec.o,$(BINSEC_DRIVER_SRCS)) \
    $(patsubst $(GPG_ERROR_DIR)/%.c,$(BUILD_DIR)/libgpg-error/%.binsec.o,$(LIBGPG_ERROR_SRCS)) \
    $(patsubst $(SRC_DIR)/src/%.c,$(BUILD_DIR)/libgcrypt/src/%.binsec.o,$(SRCS)) \
    $(patsubst $(MPI_SRC_DIR)/%.c,$(BUILD_DIR)/libgcrypt/mpi/%.binsec.o,$(MPI_SRCS))

BINSEC_FINAL = $(BUILD_DIR)/modpow_binsec

# Flags
CFLAGS_COMMON = -I$(SRC_DIR) -I$(SRC_DIR)/src -I$(SRC_DIR)/mpi \
         -O0 -Xclang -disable-O0-optnone -g -c

ERROR_CFLAGS_COMMON = -isystem libgpg-error-1.44 -I$(GPG_ERROR_DIR) \
         -DHAVE_CONFIG_H -DLOCALEDIR=0 \
         -O0 -Xclang -disable-O0-optnone -g -c

CFLAGS_KLEE = $(CFLAGS_COMMON) -I/home/theta-lin/klee-controlflow/include -emit-llvm
ERROR_CFLAGS_KLEE = $(ERROR_CFLAGS_COMMON) -I/home/theta-lin/klee-controlflow/include -emit-llvm

CFLAGS_BINSEC = $(CFLAGS_COMMON)
ERROR_CFLAGS_BINSEC = $(ERROR_CFLAGS_COMMON) -static

# Targets
.PHONY: all

all: $(FINAL_BC) $(BINSEC_FINAL)

$(FINAL_BC): $(BCS)
	@echo "LD (llvm-link-13) -> $@"
	$(LD) $^ -o $@

# Compile driver
$(BUILD_DIR)/%.bc: %.c
	@echo "CC -> $@"
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS_KLEE) $< -o $@

# Compile libgpg-error sources
$(BUILD_DIR)/libgpg-error/%.bc: $(GPG_ERROR_DIR)/%.c
	@echo "CC -> $@"
	@mkdir -p $(dir $@)
	$(CC) $(ERROR_CFLAGS_KLEE) $< -o $@

# Compile libgcrypt sources
$(BUILD_DIR)/libgcrypt/src/%.bc: $(SRC_DIR)/src/%.c
	@echo "CC -> $@"
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS_KLEE) $< -o $@

# Compile libgcrypt sources
$(BUILD_DIR)/libgcrypt/mpi/%.bc: $(MPI_SRC_DIR)/%.c
	@echo "CC -> $@"
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS_KLEE) $< -o $@

$(BINSEC_FINAL): $(BINSEC_OBJS)
	@echo "CC (clang-13) -> $@"
	$(CC) $^ -o $@

# Compile driver
$(BUILD_DIR)/%.binsec.o: %.c
	@echo "CC -> $@"
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS_BINSEC) $< -o $@

# Compile libgpg-error sources
$(BUILD_DIR)/libgpg-error/%.binsec.o: $(GPG_ERROR_DIR)/%.c
	@echo "CC -> $@"
	@mkdir -p $(dir $@)
	$(CC) $(ERROR_CFLAGS_BINSEC) $< -o $@

# Compile libgcrypt sources
$(BUILD_DIR)/libgcrypt/src/%.binsec.o: $(SRC_DIR)/src/%.c
	@echo "CC -> $@"
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS_BINSEC) $< -o $@

# Compile libgcrypt sources
$(BUILD_DIR)/libgcrypt/mpi/%.binsec.o: $(MPI_SRC_DIR)/%.c
	@echo "CC -> $@"
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS_BINSEC) $< -o $@

clean:
	rm -rf $(BUILD_DIR)
