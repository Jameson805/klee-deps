# Toolchain
CC = clang-13
LD = llvm-link-13

# Paths
SRC_DIR = libgcrypt-1.10.1
GPG_ERROR_DIR = libgpg-error-1.44/src
BUILD_DIR = build

# Files
DRIVER_SRCS = driver.c
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
DRIVER_BCS = $(patsubst %.c,$(BUILD_DIR)/%.bc,$(DRIVER_SRCS))
# STUB_BC = $(BUILD_DIR)/stub.bc
GPG_BCS = $(patsubst $(GPG_ERROR_DIR)/%.c,$(BUILD_DIR)/libgpg-error/%.bc,$(LIBGPG_ERROR_SRCS))
GCRYPT_BCS = $(patsubst $(SRC_DIR)/src/%.c,$(BUILD_DIR)/libgcrypt/src/%.bc,$(SRCS)) \
    $(patsubst $(MPI_SRC_DIR)/%.c,$(BUILD_DIR)/libgcrypt/mpi/%.bc,$(MPI_SRCS))

FINAL_BC = $(BUILD_DIR)/klee.bc

# Flags
CFLAGS = -I$(SRC_DIR) -I$(SRC_DIR)/src -I$(SRC_DIR)/mpi \
         -I/home/james/klee-deps/klee-controlflow/include \
         -O0 -Xclang -disable-O0-optnone -emit-llvm -g -c

ERROR_CFLAGS = -isystem libgpg-error-1.44 -I$(GPG_ERROR_DIR) \
         -I/home/theta-lin/klee-controlflow/include \
         -DHAVE_CONFIG_H -DLOCALEDIR=0\
         -O0 -Xclang -disable-O0-optnone -emit-llvm -g -c

# Targets
.PHONY: all clean

all: $(FINAL_BC)

$(FINAL_BC): $(DRIVER_BCS) $(GPG_BCS) $(GCRYPT_BCS)
	@echo "LD (llvm-link-13) -> $@"
	$(LD) $^ -o $@

# Compile driver and stub
$(BUILD_DIR)/%.bc: %.c
	@echo "CC -> $@"
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $< -o $@

# Explicit rule for stub.c
$(STUB_BC): $(STUB_SRC)
	@echo "CC -> $@"
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $< -o $@

# Compile libgpg-error sources
$(BUILD_DIR)/libgpg-error/%.bc: $(GPG_ERROR_DIR)/%.c
	@echo "CC -> $@"
	@mkdir -p $(dir $@)
	$(CC) $(ERROR_CFLAGS) $< -o $@

# Compile libgcrypt sources
$(BUILD_DIR)/libgcrypt/src/%.bc: $(SRC_DIR)/src/%.c
	@echo "CC -> $@"
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $< -o $@

# Compile libgcrypt sources
$(BUILD_DIR)/libgcrypt/mpi/%.bc: $(MPI_SRC_DIR)/%.c
	@echo "CC -> $@"
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $< -o $@

clean:
	rm -rf $(BUILD_DIR)
