#include "llvm/IR/PassManager.h"
#include "llvm/Passes/PassBuilder.h"
#include "llvm/Passes/PassPlugin.h"
#include "llvm/Analysis/LoopAnalysisManager.h"
#include "llvm/Analysis/LoopInfo.h"
#include "llvm/IR/Instructions.h"
#include "llvm/IR/IRBuilder.h"
#include "llvm/Support/CommandLine.h"
#include "llvm/Support/raw_ostream.h"
#include "llvm/Support/Error.h"
#include <string>
#include <atomic>

using namespace llvm;

namespace {

static std::atomic<unsigned long> StatTotalLoops{0};
static std::atomic<unsigned long> StatChangedLoops{0};
static std::atomic<unsigned long> StatExcludedLoops{0};

// Print stats at program exit (plugin unload / process exit).
struct StatsPrinter {
  ~StatsPrinter() {
    errs() << "LoopLimiter statistics:\n";
    errs() << "  total loops: " << StatTotalLoops.load() << "\n";
    errs() << "  loops instrumented: " << StatChangedLoops.load() << "\n";
    errs() << "  loops excluded (by whitelist/blacklist): " << StatExcludedLoops.load() << "\n";
  }
} StatsPrinterInstance;

static cl::opt<unsigned> MaxIterations("max-iterations",
  cl::desc("The max number of iterations for KLEE to explore"), cl::Required);

static cl::list<std::string> Whitelist(
    "whitelist",
    cl::desc("Comma-separated list of function names to instrument (empty = all)"),
    cl::ZeroOrMore, cl::CommaSeparated);

static cl::list<std::string> Blacklist(
    "blacklist",
    cl::desc("Comma-separated list of function names to skip instrumenting"),
    cl::ZeroOrMore, cl::CommaSeparated);

static cl::opt<bool> BreakMode("break",
    cl::desc("Branch to an after-loop target instead of calling klee_silent_exit if possible"),
    cl::init(false));

struct LoopLimiter : public PassInfoMixin<LoopLimiter> {
  PreservedAnalyses run(Function &F, FunctionAnalysisManager &FAM) {
    if (!Whitelist.empty() && !Blacklist.empty()) {
      report_fatal_error("LoopLimiter: --whitelist and --blacklist are mutually exclusive");
    }

    LoopInfo &LI = FAM.getResult<LoopAnalysis>(F);

    // Count all loops in this function (including nested).
    SmallVector<Loop*, 8> CountWork;
    CountWork.append(LI.begin(), LI.end());
    unsigned FuncLoopCount = 0;
    for (unsigned idx = 0; idx < CountWork.size(); ++idx) {
      Loop *L = CountWork[idx];
      ++FuncLoopCount;
      for (Loop *Sub : L->getSubLoops())
        CountWork.push_back(Sub);
    }

    // Update global total loops.
    StatTotalLoops.fetch_add(FuncLoopCount);

    // Decide whether to instrument this function:
    // - If whitelist provided: instrument only functions in the whitelist.
    // - Else if blacklist provided: instrument all functions except those in the blacklist.
    // - Else: instrument all functions.
    bool Allowed = true;
    if (!Whitelist.empty()) {
      Allowed = false;
      for (const auto &Name : Whitelist) {
        if (F.getName() == Name) { Allowed = true; break; }
      }
    } else if (!Blacklist.empty()) {
      for (const auto &Name : Blacklist) {
        if (F.getName() == Name) { Allowed = false; break; }
      }
    }

    if (!Allowed) {
      // Count loops excluded by whitelist/blacklist.
      StatExcludedLoops.fetch_add(FuncLoopCount);
      return PreservedAnalyses::all();
    }

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

      bool UseBreakMode = BreakMode;
      BranchInst *CanonicalExitBranch = nullptr;
      BasicBlock *LoopSuccessor = nullptr;
      BasicBlock *ExitSuccessor = nullptr;
      if (BreakMode) {
        // Conservatively reuse the loop's existing canonical exit edge after
        // loop-simplify. The older synthetic "jump after the loop" rewrite
        // could bypass PHIs on real benchmarks such as OpenSSL.
        auto *HeaderBranch = dyn_cast<BranchInst>(Header->getTerminator());
        if (!HeaderBranch || !HeaderBranch->isConditional()) {
          errs() << "warning: loop in function '" << F.getName()
                 << "' cannot be break-instrumented conservatively because the loop header is not conditionally exiting; falling back to klee_silent_exit\n";
          UseBreakMode = false;
        } else {
          BasicBlock *Succ0 = HeaderBranch->getSuccessor(0);
          BasicBlock *Succ1 = HeaderBranch->getSuccessor(1);
          bool Succ0InLoop = L->contains(Succ0);
          bool Succ1InLoop = L->contains(Succ1);
          if (Succ0InLoop == Succ1InLoop) {
            errs() << "warning: loop in function '" << F.getName()
                   << "' cannot be break-instrumented conservatively because the loop header does not have exactly one in-loop and one out-of-loop successor after loop-simplify; falling back to klee_silent_exit\n";
            UseBreakMode = false;
          } else {
            CanonicalExitBranch = HeaderBranch;
            LoopSuccessor = Succ0InLoop ? Succ0 : Succ1;
            ExitSuccessor = Succ0InLoop ? Succ1 : Succ0;
          }
        }
      }

      // Instrument this loop:
      Changed = true;
      StatChangedLoops.fetch_add(1);

      // Create a unique named alloca at the entry block insertion point.
      std::string CounterName = "loop.counter." + std::to_string(LoopIdx++);
      AllocaInst *Counter = EntryBuilder.CreateAlloca(Type::getInt32Ty(Context), nullptr, CounterName);
      Counter->setAlignment(Align(4));

      // Initialize counter to 0 at the preheader (before the loop body is entered).
      Builder.SetInsertPoint(Preheader->getTerminator());
      Builder.CreateStore(Builder.getInt32(0), Counter);

      if (UseBreakMode) {
        // Keep the original loop exit structure and only widen the exit
        // predicate with the loop bound check.
        Builder.SetInsertPoint(CanonicalExitBranch);
        Value *CurrentCount = Builder.CreateLoad(Type::getInt32Ty(Context), Counter, "counter.val");
        Value *Limit = Builder.getInt32(static_cast<int>(MaxIterations));
        Value *Compare = Builder.CreateICmpSGE(CurrentCount, Limit, "bound.check");
        Value *OriginalCondition = CanonicalExitBranch->getCondition();
        BasicBlock *TrueSuccessor = CanonicalExitBranch->getSuccessor(0);
        BasicBlock *FalseSuccessor = CanonicalExitBranch->getSuccessor(1);

        Value *NewCondition = nullptr;
        if (CanonicalExitBranch->getSuccessor(0) == ExitSuccessor) {
          NewCondition = Builder.CreateOr(OriginalCondition, Compare, "loop.exit.or.bound");
        } else {
          Value *NotCompare = Builder.CreateNot(Compare, "bound.check.not");
          NewCondition = Builder.CreateAnd(OriginalCondition, NotCompare, "loop.stay.and.not.bound");
        }

        CanonicalExitBranch->eraseFromParent();
        Builder.SetInsertPoint(Header);
        Builder.CreateCondBr(NewCondition, TrueSuccessor, FalseSuccessor);
      } else {
        // Create a synthetic exit path only when we terminate the path locally.
        BasicBlock *ExitBB = BasicBlock::Create(Context, "klee.exit.bb", &F);
        BasicBlock *ContinueBB = Header->splitBasicBlock(Header->getFirstNonPHI(), "loop.body.bb");

        Builder.SetInsertPoint(ExitBB);
        Builder.CreateCall(ExitFunc, {ConstantInt::get(Type::getInt32Ty(Context), 1)});
        Builder.CreateUnreachable();

        Header->getTerminator()->eraseFromParent();
        Builder.SetInsertPoint(Header);

        Value *CurrentCount = Builder.CreateLoad(Type::getInt32Ty(Context), Counter, "counter.val");
        Value *Limit = Builder.getInt32(static_cast<int>(MaxIterations));
        Value *Compare = Builder.CreateICmpSGE(CurrentCount, Limit, "bound.check");
        Builder.CreateCondBr(Compare, ExitBB, ContinueBB);
      }

      // 6. Increment the counter in every latch before the back-edge is taken.
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
