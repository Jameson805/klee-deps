CC = clang-13
OPT = opt-13
KLEE_INCLUDE = /home/james/klee-deps/klee-controlflow/include
LLVM_LINK = /usr/lib/llvm-13/bin/llvm-link
CFLAGS = -I. -I$(KLEE_INCLUDE) -emit-llvm -c -g -O0 -Xclang -disable-llvm-passes

TEST ?= test1

all: $(TEST).bc

branch_tracker.bc: branch_tracker.c
	$(CC) $(CFLAGS) branch_tracker.c -o $@

$(TEST).tmp.bc: $(TEST).c
	$(CC) $(CFLAGS) $(TEST).c -o $@

$(TEST).bc: $(TEST).tmp.bc branch_tracker.bc
	$(LLVM_LINK) $^ -o linked.bc
	$(OPT) -O0 linked.bc -o $@
	rm -f linked.bc

clean:
	rm -f *.bc *.o *.out *.ktest klee-out-* *.path *.err linked.bc
