# Toolchain
CC = clang-13
LD = llvm-link-13

# Paths
SRC_DIR = openssl-1.1.1q
BUILD_DIR = build
DRIVER_SRC = mod_exp_mont_driver.c
DRIVER_BC = $(BUILD_DIR)/mod_exp_mont_driver.bc
STUBS_SRC = stubs.c
STUBS_BC = $(BUILD_DIR)/stubs.bc

# Source files
BN_SRC_DIR = $(SRC_DIR)/crypto/bn
BN_SRCS = $(wildcard $(BN_SRC_DIR)/*.c)

SUPPORT_SRCS := \
  $(SRC_DIR)/crypto/mem.c \
  $(SRC_DIR)/crypto/o_str.c \
  $(SRC_DIR)/crypto/ctype.c \
  $(SRC_DIR)/crypto/init.c \
  $(SRC_DIR)/crypto/cryptlib.c \
  $(SRC_DIR)/crypto/threads_pthread.c \
  $(SRC_DIR)/crypto/bn/bn_ctx.c \
  $(SRC_DIR)/crypto/err/err.c \
  $(SRC_DIR)/crypto/err/err_all.c \
  $(SRC_DIR)/crypto/err/err_prn.c

OPENSSL_SRCS = $(BN_SRCS) $(SUPPORT_SRCS)

OPENSSL_BCS = $(patsubst $(SRC_DIR)/%.c,$(BUILD_DIR)/openssl/%.bc,$(OPENSSL_SRCS))

FINAL_BC = $(BUILD_DIR)/klee.bc

# Flags
CFLAGS = -DOPENSSL_NO_ASM -UOPENSSL_BN_ASM_PART_WORDS \
         -I$(SRC_DIR)/include -I$(SRC_DIR) -I$(SRC_DIR)/crypto/include \
         -I/home/james/klee-deps/klee-controlflow/include \
         -O0 -Xclang -disable-O0-optnone -emit-llvm -g -c

# Build rules
.PHONY: all clean klee

all: klee

klee: $(FINAL_BC)

$(FINAL_BC): $(OPENSSL_BCS) $(DRIVER_BC) $(STUBS_BC)
	@echo "LD (llvm-link-13) -> $@"
	$(LD) $^ -o $@

$(BUILD_DIR)/openssl/%.bc: $(SRC_DIR)/%.c
	@echo "CC (clang-13) -> $@"
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $< -o $@

$(DRIVER_BC): $(DRIVER_SRC)
	@echo "CC (clang-13) -> $@"
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $< -o $@

$(STUBS_BC): $(STUBS_SRC)
	@echo "CC (clang-13) -> $@"
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $< -o $@

clean:
	rm -rf $(BUILD_DIR)
