CC=clang
KLEE_LD=llvm-link
BINSEC_LD_FLAGS=-static

CFLAGS=-isystem include -I include -I /home/theta-lin/klee-controlflow/include -emit-llvm -c -g -O0 -Xclang -disable-O0-optnone
BINSEC_CFLAGS=-isystem include -I include -c -g -O0 -Xclang -disable-O0-optnone

COMMON_SRCS = i32_add.c i32_bitlen.c i32_decmod.c i32_decode.c i32_decred.c \
       i32_div32.c i32_encode.c i32_fmont.c i32_iszero.c i32_modpow.c \
       i32_montmul.c i32_mulacc.c i32_muladd.c i32_ninv32.c i32_reduce.c \
       i32_sub.c i32_tmont.c ccopy.c

KLEE_SRCS   = $(COMMON_SRCS) klee_wrapper.c
BINSEC_SRCS = $(COMMON_SRCS) binsec_wrapper.c

KLEE_OBJS     = $(KLEE_SRCS:.c=.bc)
BINSEC_OBJS = $(BINSEC_SRCS:.c=.binsec.o)

all: testall.bc testall_binsec

clean: rm *.bc *.o

testall.bc: $(KLEE_OBJS)
	$(KLEE_LD) $^ -o $@

%.bc: %.c
	$(CC) $(CFLAGS) -o $@ -c $<

testall_binsec: $(BINSEC_OBJS)
	$(CC) $(BINSEC_LD_FLAGS) $^ -o $@

%.binsec.o: %.c
	$(CC) $(BINSEC_CFLAGS) -o $@ -c $<

.PHONY: all

# test1.bc : i32_modpow.bc
# 	$(LD) $^ -o $@

# test2.bc: i32_add.bc i32_bitlen.bc i32_decmod.bc i32_decode.bc i32_decred.bc i32_div32.bc i32_encode.bc i32_fmont.bc i32_iszero.bc i32_modpow.bc i32_montmul.bc i32_mulacc.bc i32_muladd.bc i32_ninv32.bc i32_reduce.bc i32_sub.bc i32_tmont.bc ccopy.bc
# 	$(LD) $^ -o $@

# .PHONY: testall
# testall: testall.bc
# 	./run.sh $< results_with_source.txt