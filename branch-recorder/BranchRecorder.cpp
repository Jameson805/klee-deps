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

struct BranchRecorder : public PassInfoMixin<BranchRecorder> {
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
    LLVMContext &C = M.getContext();
    IntegerType *I32 = Type::getInt32Ty(C);

    // Declare (or reuse) stub: void __record_branch(i32 decision, i8* file, i32 line, i32 col)
    FunctionType *FT =
        FunctionType::get(Type::getVoidTy(C),
                          {I32, Type::getInt8PtrTy(C), I32, I32}, false);
    FunctionCallee Recorder = M.getOrInsertFunction("__record_branch", FT);

    for (BasicBlock &BB : F) {
      for (Instruction &I : BB) {
        auto *BI = dyn_cast<BranchInst>(&I);
        if (!BI || !BI->isConditional())
          continue;

        ++TotalInFunc;
        if (!InstrumentThis)
          continue;

        IRBuilder<> B(BI);

        // Normalize branch condition to i32 {0,1}
        Value *Cond = BI->getCondition();
        Value *Decision = nullptr;
        if (Cond->getType()->isIntegerTy(1)) {
          Decision = B.CreateZExt(Cond, I32);
        } else if (Cond->getType()->isIntegerTy()) {
          Value *Zero = ConstantInt::get(Cond->getType(), 0);
            Decision = B.CreateZExt(B.CreateICmpNE(Cond, Zero), I32);
        } else if (Cond->getType()->isFloatingPointTy()) {
          Constant *ZeroF = ConstantFP::get(Cond->getType(), 0.0);
          Decision = B.CreateZExt(B.CreateFCmpUNE(Cond, ZeroF), I32);
        } else {
          // Fallback: pointer/non-integer => compare against null after ptrtoint
          Value *AsInt = B.CreatePtrToInt(Cond, I32);
          Decision = B.CreateZExt(
              B.CreateICmpNE(AsInt, ConstantInt::get(I32, 0)), I32);
        }

        // Extract debug info (file, line, col); fallback to "unknown", 0, 0
        std::string File = "unknown";
        unsigned Line = 0;
        unsigned Col = 0;
        if (DebugLoc DL = BI->getDebugLoc()) {
          Line = DL.getLine();
          Col  = DL.getCol();
          File = DL->getFilename().str();
        }

        // Create constant global for file string
        Constant *FileConst = ConstantDataArray::getString(C, File, true);
        auto *ArrTy = cast<ArrayType>(FileConst->getType());
        GlobalVariable *FileGV = new GlobalVariable(
            M, FileConst->getType(), true, GlobalValue::PrivateLinkage,
            FileConst,
            "__br_file_" + std::to_string(Line) + "_" + std::to_string(Col));
        FileGV->setUnnamedAddr(GlobalValue::UnnamedAddr::Global);
        Value *ZeroIdx = ConstantInt::get(I32, 0);
        Value *FilePtr = B.CreateInBoundsGEP(
            FileConst->getType(), FileGV, {ZeroIdx, ZeroIdx});

        Value *LineVal = ConstantInt::get(I32, Line);
        Value *ColVal  = ConstantInt::get(I32, Col);

        // Call stub
        B.CreateCall(Recorder, {Decision, FilePtr, LineVal, ColVal});

        ++InstInFunc;
        Changed = true;
      }
    }

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
