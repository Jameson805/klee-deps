#include "llvm/IR/PassManager.h"
#include "llvm/Passes/PassBuilder.h"
#include "llvm/Passes/PassPlugin.h"
#include "llvm/Analysis/LoopAnalysisManager.h"
#include "llvm/Analysis/LoopInfo.h"
#include "llvm/IR/IRBuilder.h"
#include "llvm/Support/CommandLine.h"
#include "llvm/Support/raw_ostream.h"
#include <string>

using namespace llvm;

namespace {

static cl::opt<unsigned> MaxIterations("max-iterations",
  cl::desc("The max number of iterations for KLEE to explore"), cl::Required);

static cl::list<std::string> Functions(
    "functions",
    cl::desc("Comma-separated list of function names to instrument (empty = all)"),
    cl::ZeroOrMore, cl::CommaSeparated);

struct LoopLimiter : public PassInfoMixin<LoopLimiter> {
  PreservedAnalyses run(Function &F, FunctionAnalysisManager &FAM) {
    // If a whitelist is provided, only instrument functions in it.
    if (!Functions.empty()) {
      bool Allowed = false;
      for (const auto &Name : Functions) {
        if (F.getName() == Name) {
          Allowed = true;
          break;
        }
      }
      if (!Allowed)
        return PreservedAnalyses::all();
    }

    LoopInfo &LI = FAM.getResult<LoopAnalysis>(F);
    Module *M = F.getParent();
    LLVMContext &Context = M->getContext();
    IRBuilder<> Builder(Context);

    SmallVector<Loop*, 8> Worklist;
    Worklist.append(LI.begin(), LI.end());

    if (Worklist.empty()) {
      return PreservedAnalyses::all();
    }

    bool Changed = false;

    // 1. Declare klee_silent_exit as void(i32)
    FunctionType *ExitFnType = FunctionType::get(Type::getVoidTy(Context), {Type::getInt32Ty(Context)}, false);
    FunctionCallee ExitFunc = M->getOrInsertFunction("klee_silent_exit", ExitFnType);

    // Entry builder for stable alloca insertion point
    IRBuilder<> EntryBuilder(&F.getEntryBlock(), F.getEntryBlock().getFirstInsertionPt());
    unsigned LoopIdx = 0;

    while (!Worklist.empty()) {
      Loop *L = Worklist.pop_back_val();

      for (Loop *SubL : L->getSubLoops()) {
        Worklist.push_back(SubL);
      }

      BasicBlock *Preheader = L->getLoopPreheader();
      BasicBlock *Header = L->getHeader();

      if (!Preheader || !Header) {
        errs() << "warning: skipping loop in function '" << F.getName()
               << "' because it has no preheader/header\n";
        continue;
      }

      // Collect all loop latches (support multiple back-edges).
      SmallVector<BasicBlock*, 4> Latches;
      L->getLoopLatches(Latches);
      if (Latches.empty()) {
        errs() << "warning: skipping loop in function '" << F.getName()
               << "' because it has no latch\n";
        continue;
      }

      Changed = true;

      // Create a unique named alloca at the entry block insertion point.
      std::string CounterName = "loop.counter." + std::to_string(LoopIdx++);
      AllocaInst *Counter = EntryBuilder.CreateAlloca(Type::getInt32Ty(Context), nullptr, CounterName);
      Counter->setAlignment(Align(4));

      // Initialize counter to 0 at the preheader (before the loop body is entered).
      Builder.SetInsertPoint(Preheader->getTerminator());
      Builder.CreateStore(Builder.getInt32(0), Counter);

      // 2. Create new basic blocks for the if-then structure
      BasicBlock *ExitBB = BasicBlock::Create(Context, "klee.exit.bb", &F);
      BasicBlock *ContinueBB = Header->splitBasicBlock(Header->getFirstNonPHI(), "loop.body.bb");

      // 3. Populate the exit block
      Builder.SetInsertPoint(ExitBB);
      Builder.CreateCall(ExitFunc, {ConstantInt::get(Type::getInt32Ty(Context), 1)});
      Builder.CreateUnreachable(); // klee_silent_exit does not return

      // 4. Modify the original header to add the conditional branch
      Header->getTerminator()->eraseFromParent(); // Erase the old unconditional branch
      Builder.SetInsertPoint(Header);

      Value *CurrentCount = Builder.CreateLoad(Type::getInt32Ty(Context), Counter, "counter.val");
      Value *Limit = Builder.getInt32(static_cast<int>(MaxIterations));
      Value *Compare = Builder.CreateICmpSGE(CurrentCount, Limit, "bound.check"); // check for >=
      Builder.CreateCondBr(Compare, ExitBB, ContinueBB);

      // 5. Increment the counter in every latch before the back-edge is taken.
      for (BasicBlock *Latch : Latches) {
        Builder.SetInsertPoint(Latch->getTerminator());
        Value *OldVal = Builder.CreateLoad(Type::getInt32Ty(Context), Counter, "counter.old");
        Value *NewVal = Builder.CreateAdd(OldVal, Builder.getInt32(1), "counter.new");
        Builder.CreateStore(NewVal, Counter);
      }
    }

    return Changed ? PreservedAnalyses::none() : PreservedAnalyses::all();
  }

  static bool isRequired() { return true; }
};

} // anonymous namespace

extern "C" PassPluginLibraryInfo llvmGetPassPluginInfo() {
  return {LLVM_PLUGIN_API_VERSION, "LoopLimiter", LLVM_VERSION_STRING,
    [](PassBuilder &PB) {
      PB.registerPipelineParsingCallback(
        [](StringRef Name, FunctionPassManager &FPM,
           ArrayRef<PassBuilder::PipelineElement>) {
          if (Name == "loop-limiter") {
            FPM.addPass(LoopLimiter());
            return true;
          }
          return false;
        });
    }};
}
