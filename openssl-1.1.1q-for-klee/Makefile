# Toolchain
CC = clang-13
LD = llvm-link-13

# Paths
SRC_DIR = openssl-1.1.1q
BUILD_DIR = build
STUBS_SRC = stubs.c
STUBS_BC = $(BUILD_DIR)/stubs.bc

# Driver files
DRIVER_SRCS = mod_exp_mont_driver.c mod_exp_recp_driver.c
DRIVER_BCS = $(patsubst %.c,$(BUILD_DIR)/%.bc,$(DRIVER_SRCS))

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

# Final linked outputs per driver
FINAL_MONT_BC = $(BUILD_DIR)/klee_mont.bc
FINAL_RECP_BC = $(BUILD_DIR)/klee_recp.bc

# Flags
CFLAGS = -DOPENSSL_NO_ASM -UOPENSSL_BN_ASM_PART_WORDS \
         -I$(SRC_DIR)/include -I$(SRC_DIR) -I$(SRC_DIR)/crypto/include \
         -I/home/james/klee-deps/klee-controlflow/include \
         -O0 -Xclang -disable-O0-optnone -emit-llvm -g -c

# Build rules
.PHONY: all clean mont recp

all: mont recp

mont: $(FINAL_MONT_BC)
recp: $(FINAL_RECP_BC)

# Link mont driver + OpenSSL + stubs
$(FINAL_MONT_BC): $(OPENSSL_BCS) $(BUILD_DIR)/mod_exp_mont_driver.bc $(STUBS_BC)
	@echo "LD (llvm-link-13) -> $@"
	$(LD) $^ -o $@

# Link recp driver + OpenSSL + stubs
$(FINAL_RECP_BC): $(OPENSSL_BCS) $(BUILD_DIR)/mod_exp_recp_driver.bc $(STUBS_BC)
	@echo "LD (llvm-link-13) -> $@"
	$(LD) $^ -o $@

# Compile OpenSSL source files to .bc
$(BUILD_DIR)/openssl/%.bc: $(SRC_DIR)/%.c
	@echo "CC (clang-13) -> $@"
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $< -o $@

# Compile driver .c files to .bc
$(BUILD_DIR)/%.bc: %.c
	@echo "CC (clang-13) -> $@"
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $< -o $@

# Compile stubs
$(STUBS_BC): $(STUBS_SRC)
	@echo "CC (clang-13) -> $@"
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $< -o $@

clean:
	rm -rf $(BUILD_DIR)
