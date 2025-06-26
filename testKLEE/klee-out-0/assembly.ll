; ModuleID = '/mnt/c/Users/james/OneDrive/Documents/College Classes/CS+ Semester/TestKLEE/tests/test1.bc'
source_filename = "/mnt/c/Users/james/OneDrive/Documents/College Classes/CS+ Semester/TestKLEE/tests/test1.c"
target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-f80:128-n8:16:32:64-S128"
target triple = "x86_64-pc-linux-gnu"

@branch_taken = dso_local global i32 -1, align 4, !dbg !0
@.str = private unnamed_addr constant [4 x i8] c"pub\00", align 1
@.str.1 = private unnamed_addr constant [7 x i8] c"secret\00", align 1
@.str.2 = private unnamed_addr constant [16 x i8] c"branch_taken = \00", align 1

; Function Attrs: noinline nounwind optnone uwtable
define dso_local i32 @test_branch(i32 %0, i32 %1) #0 !dbg !14 {
  %3 = alloca i32, align 4
  %4 = alloca i32, align 4
  %5 = alloca i32, align 4
  store i32 %0, i32* %3, align 4
  call void @llvm.dbg.declare(metadata i32* %3, metadata !17, metadata !DIExpression()), !dbg !18
  store i32 %1, i32* %4, align 4
  call void @llvm.dbg.declare(metadata i32* %4, metadata !19, metadata !DIExpression()), !dbg !20
  call void @llvm.dbg.declare(metadata i32* %5, metadata !21, metadata !DIExpression()), !dbg !22
  store i32 0, i32* %5, align 4, !dbg !22
  %6 = load i32, i32* %4, align 4, !dbg !23
  %7 = icmp sgt i32 %6, 0, !dbg !25
  br i1 %7, label %8, label %11, !dbg !26

8:                                                ; preds = %2
  store i32 1, i32* @branch_taken, align 4, !dbg !27
  %9 = load i32, i32* %3, align 4, !dbg !29
  %10 = add nsw i32 %9, 1, !dbg !30
  store i32 %10, i32* %5, align 4, !dbg !31
  br label %14, !dbg !32

11:                                               ; preds = %2
  store i32 0, i32* @branch_taken, align 4, !dbg !33
  %12 = load i32, i32* %3, align 4, !dbg !35
  %13 = sub nsw i32 %12, 1, !dbg !36
  store i32 %13, i32* %5, align 4, !dbg !37
  br label %14

14:                                               ; preds = %11, %8
  %15 = load i32, i32* %5, align 4, !dbg !38
  ret i32 %15, !dbg !39
}

; Function Attrs: nofree nosync nounwind readnone speculatable willreturn
declare void @llvm.dbg.declare(metadata, metadata, metadata) #1

; Function Attrs: noinline nounwind optnone uwtable
define dso_local i32 @main() #0 !dbg !40 {
  %1 = alloca i32, align 4
  %2 = alloca i32, align 4
  %3 = alloca i32, align 4
  store i32 0, i32* %1, align 4
  call void @llvm.dbg.declare(metadata i32* %2, metadata !43, metadata !DIExpression()), !dbg !44
  call void @llvm.dbg.declare(metadata i32* %3, metadata !45, metadata !DIExpression()), !dbg !46
  %4 = bitcast i32* %2 to i8*, !dbg !47
  call void @klee_make_symbolic(i8* %4, i64 4, i8* getelementptr inbounds ([4 x i8], [4 x i8]* @.str, i64 0, i64 0)), !dbg !48
  %5 = bitcast i32* %3 to i8*, !dbg !49
  call void @klee_make_symbolic(i8* %5, i64 4, i8* getelementptr inbounds ([7 x i8], [7 x i8]* @.str.1, i64 0, i64 0)), !dbg !50
  %6 = load i32, i32* %2, align 4, !dbg !51
  %7 = load i32, i32* %3, align 4, !dbg !52
  %8 = call i32 @test_branch(i32 %6, i32 %7), !dbg !53
  %9 = load i32, i32* @branch_taken, align 4, !dbg !54
  call void (i8*, ...) @klee_print_expr(i8* getelementptr inbounds ([16 x i8], [16 x i8]* @.str.2, i64 0, i64 0), i32 %9), !dbg !55
  ret i32 0, !dbg !56
}

declare dso_local void @klee_make_symbolic(i8*, i64, i8*) #2

declare dso_local void @klee_print_expr(i8*, ...) #2

attributes #0 = { noinline nounwind optnone uwtable "frame-pointer"="all" "min-legal-vector-width"="0" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #1 = { nofree nosync nounwind readnone speculatable willreturn }
attributes #2 = { "frame-pointer"="all" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }

!llvm.dbg.cu = !{!2}
!llvm.module.flags = !{!8, !9, !10, !11, !12}
!llvm.ident = !{!13}

!0 = !DIGlobalVariableExpression(var: !1, expr: !DIExpression())
!1 = distinct !DIGlobalVariable(name: "branch_taken", scope: !2, file: !6, line: 9, type: !7, isLocal: false, isDefinition: true)
!2 = distinct !DICompileUnit(language: DW_LANG_C99, file: !3, producer: "Ubuntu clang version 13.0.1-2ubuntu2.2", isOptimized: false, runtimeVersion: 0, emissionKind: FullDebug, enums: !4, globals: !5, splitDebugInlining: false, nameTableKind: None)
!3 = !DIFile(filename: "/mnt/c/Users/james/OneDrive/Documents/College Classes/CS+ Semester/TestKLEE/tests/test1.c", directory: "/mnt/c/Users/james/OneDrive/Documents/College Classes/CS+ Semester/TestKLEE")
!4 = !{}
!5 = !{!0}
!6 = !DIFile(filename: "tests/test1.c", directory: "/mnt/c/Users/james/OneDrive/Documents/College Classes/CS+ Semester/TestKLEE")
!7 = !DIBasicType(name: "int", size: 32, encoding: DW_ATE_signed)
!8 = !{i32 7, !"Dwarf Version", i32 4}
!9 = !{i32 2, !"Debug Info Version", i32 3}
!10 = !{i32 1, !"wchar_size", i32 4}
!11 = !{i32 7, !"uwtable", i32 1}
!12 = !{i32 7, !"frame-pointer", i32 2}
!13 = !{!"Ubuntu clang version 13.0.1-2ubuntu2.2"}
!14 = distinct !DISubprogram(name: "test_branch", scope: !6, file: !6, line: 13, type: !15, scopeLine: 13, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !4)
!15 = !DISubroutineType(types: !16)
!16 = !{!7, !7, !7}
!17 = !DILocalVariable(name: "pub", arg: 1, scope: !14, file: !6, line: 13, type: !7)
!18 = !DILocation(line: 13, column: 21, scope: !14)
!19 = !DILocalVariable(name: "secret", arg: 2, scope: !14, file: !6, line: 13, type: !7)
!20 = !DILocation(line: 13, column: 30, scope: !14)
!21 = !DILocalVariable(name: "ret", scope: !14, file: !6, line: 14, type: !7)
!22 = !DILocation(line: 14, column: 9, scope: !14)
!23 = !DILocation(line: 16, column: 9, scope: !24)
!24 = distinct !DILexicalBlock(scope: !14, file: !6, line: 16, column: 9)
!25 = !DILocation(line: 16, column: 16, scope: !24)
!26 = !DILocation(line: 16, column: 9, scope: !14)
!27 = !DILocation(line: 17, column: 22, scope: !28)
!28 = distinct !DILexicalBlock(scope: !24, file: !6, line: 16, column: 21)
!29 = !DILocation(line: 18, column: 15, scope: !28)
!30 = !DILocation(line: 18, column: 19, scope: !28)
!31 = !DILocation(line: 18, column: 13, scope: !28)
!32 = !DILocation(line: 19, column: 5, scope: !28)
!33 = !DILocation(line: 20, column: 22, scope: !34)
!34 = distinct !DILexicalBlock(scope: !24, file: !6, line: 19, column: 12)
!35 = !DILocation(line: 21, column: 15, scope: !34)
!36 = !DILocation(line: 21, column: 19, scope: !34)
!37 = !DILocation(line: 21, column: 13, scope: !34)
!38 = !DILocation(line: 24, column: 12, scope: !14)
!39 = !DILocation(line: 24, column: 5, scope: !14)
!40 = distinct !DISubprogram(name: "main", scope: !6, file: !6, line: 28, type: !41, scopeLine: 28, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !4)
!41 = !DISubroutineType(types: !42)
!42 = !{!7}
!43 = !DILocalVariable(name: "pub", scope: !40, file: !6, line: 29, type: !7)
!44 = !DILocation(line: 29, column: 9, scope: !40)
!45 = !DILocalVariable(name: "secret", scope: !40, file: !6, line: 29, type: !7)
!46 = !DILocation(line: 29, column: 14, scope: !40)
!47 = !DILocation(line: 31, column: 24, scope: !40)
!48 = !DILocation(line: 31, column: 5, scope: !40)
!49 = !DILocation(line: 32, column: 24, scope: !40)
!50 = !DILocation(line: 32, column: 5, scope: !40)
!51 = !DILocation(line: 34, column: 17, scope: !40)
!52 = !DILocation(line: 34, column: 22, scope: !40)
!53 = !DILocation(line: 34, column: 5, scope: !40)
!54 = !DILocation(line: 35, column: 40, scope: !40)
!55 = !DILocation(line: 35, column: 5, scope: !40)
!56 = !DILocation(line: 36, column: 5, scope: !40)
