#include "llvm/IR/PassManager.h"
#include "llvm/Passes/PassBuilder.h"
#include "llvm/Passes/PassPlugin.h"
#include "llvm/Analysis/LoopAnalysisManager.h"
#include "llvm/Analysis/LoopInfo.h"
#include "llvm/IR/IRBuilder.h"
#include "llvm/Support/CommandLine.h"
#include "llvm/Support/raw_ostream.h"
#include "llvm/Analysis/PostDominators.h"
#include "llvm/Support/Error.h"
#include "llvm/Support/ErrorHandling.h"
#include <string>
#include <atomic>

using namespace llvm;

namespace {

// Global stats across the compilation.
static std::atomic<uint64_t> TotalBranches{0};
static std::atomic<uint64_t> InstrumentedBranches{0};

// Print stats at program exit (plugin unload / process exit).
struct StatsPrinter {
  ~StatsPrinter() {
    errs() << "BranchRecorder statistics:\n";
    errs() << "  total conditional branches: "
           << TotalBranches.load(std::memory_order_relaxed) << "\n";
    errs() << "  instrumented branches: "
           << InstrumentedBranches.load(std::memory_order_relaxed) << "\n";
  }
} StatsPrinterInstance;

static cl::list<std::string> Whitelist(
    "whitelist",
    cl::desc("Comma-separated list of function names to instrument (empty = all)"),
    cl::ZeroOrMore, cl::CommaSeparated);

// Helper to find the required globals; exit if not found or wrong type.
static void ensureBranchGlobals(Module &M, unsigned /*ArraySize*/,
                                GlobalVariable *&OutArr, GlobalVariable *&OutLen) {
  LLVMContext &C = M.getContext();
  IntegerType *I32 = Type::getInt32Ty(C);

  // branchRecords array must exist and be [N x i32]
  if (GlobalVariable *GV = M.getGlobalVariable("branchRecords", /*AllowInternal=*/true)) {
    Type *ValTy = GV->getValueType();
    auto *ArrTy = dyn_cast<ArrayType>(ValTy);
    if (!ArrTy || !ArrTy->getElementType()->isIntegerTy(32)) {
      report_fatal_error("branchRecords must be an array of i32");
    }
    OutArr = GV;
  } else {
    report_fatal_error("Global 'branchRecords' (i32 array) not found");
  }

  // branchRecordsLen must exist and be i32
  if (GlobalVariable *GV = M.getGlobalVariable("branchRecordsLen", /*AllowInternal=*/true)) {
    if (GV->getValueType() != I32) {
      report_fatal_error("branchRecordsLen must be an i32");
    }
    OutLen = GV;
  } else {
    report_fatal_error("Global 'branchRecordsLen' (i32) not found");
  }
}

struct BranchRecorder : public PassInfoMixin<BranchRecorder> {
  // removed: bool Changed = false;

  // Instrument a single function if it matches the whitelist (or if whitelist empty).
  PreservedAnalyses run(Function &F, FunctionAnalysisManager &FAM) {
    bool InstrumentThis = true;
    if (!Whitelist.empty()) {
      InstrumentThis = false;
      for (auto &name : Whitelist) {
        if (F.getName() == name) {
          InstrumentThis = true;
          break;
        }
      }
    }

    bool Changed = false;
    uint64_t TotalInFunc = 0;
    uint64_t InstInFunc = 0;

    Module &M = *F.getParent();
    IntegerType *I32 = Type::getInt32Ty(M.getContext());

    GlobalVariable *BranchArr = nullptr;
    GlobalVariable *BranchLen = nullptr;

    for (BasicBlock &BB : F) {
      for (Instruction &I : BB) {
        auto *BI = dyn_cast<BranchInst>(&I);
        if (!BI || !BI->isConditional())
          continue;

        ++TotalInFunc;

        if (!InstrumentThis)
          continue;

        if (!BranchArr) {
          // Lookup and validate required globals on first use.
          ensureBranchGlobals(M, /*ArraySize=*/0, BranchArr, BranchLen);
        }

        IRBuilder<> B(BI);

        // load current length
        LoadInst *LenLoad = B.CreateLoad(I32, BranchLen);
        // compute ptr to branchRecords[len]
        Value *zero = ConstantInt::get(I32, 0);
        Value *idx = LenLoad; // i32
        Value *GEP = B.CreateInBoundsGEP(BranchArr->getValueType(), BranchArr, {zero, idx});

        // coerce condition to i32
        Value *Cond = BI->getCondition();
        Value *ValToStore = nullptr;
        if (Cond->getType()->isIntegerTy(1)) {
          ValToStore = B.CreateZExt(Cond, I32);
        } else if (Cond->getType()->isIntegerTy()) {
          Value *Zero = ConstantInt::get(Cond->getType(), 0);
          Value *Ne = B.CreateICmpNE(Cond, Zero);
          ValToStore = B.CreateZExt(Ne, I32);
        } else if (Cond->getType()->isFloatingPointTy()) {
          Constant *ZeroF = ConstantFP::get(Cond->getType(), 0.0);
          Value *Ne = B.CreateFCmpUNE(Cond, ZeroF);
          ValToStore = B.CreateZExt(Ne, I32);
        } else {
          // Fallback: convert to integer decision (non-zero => 1)
          Value *AsInt = B.CreatePtrToInt(Cond, I32);
          Value *Ne = B.CreateICmpNE(AsInt, ConstantInt::get(I32, 0));
          ValToStore = B.CreateZExt(Ne, I32);
        }

        // store the decision
        B.CreateStore(ValToStore, GEP);

        // increment len
        Value *One = ConstantInt::get(I32, 1);
        Value *NewLen = B.CreateAdd(LenLoad, One);
        B.CreateStore(NewLen, BranchLen);

        ++InstInFunc;
        Changed = true;
      }
    }

    // Update global stats
    TotalBranches.fetch_add(TotalInFunc, std::memory_order_relaxed);
    InstrumentedBranches.fetch_add(InstInFunc, std::memory_order_relaxed);

    return Changed ? PreservedAnalyses::none() : PreservedAnalyses::all();
  }

  static bool isRequired() { return true; }
};

} // anonymous namespace

extern "C" PassPluginLibraryInfo llvmGetPassPluginInfo() {
  return {LLVM_PLUGIN_API_VERSION, "BranchRecorder", LLVM_VERSION_STRING,
    [](PassBuilder &PB) {
      PB.registerPipelineParsingCallback(
        [](StringRef Name, FunctionPassManager &FPM,
           ArrayRef<PassBuilder::PipelineElement>) {
          if (Name == "branch-recorder") {
            FPM.addPass(BranchRecorder());
            return true;
          }
          return false;
        });
    }};
}
