; ModuleID = 'constrained-cases/target_false_test000001.bc'
source_filename = "constrained-cases/target_false_test000001.c"
target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-f80:128-n8:16:32:64-S128"
target triple = "x86_64-pc-linux-gnu"

@branch_taken = dso_local global i32 -1, align 4, !dbg !0
@.str = private unnamed_addr constant [4 x i8] c"pub\00", align 1
@.str.1 = private unnamed_addr constant [7 x i8] c"secret\00", align 1
@.str.2 = private unnamed_addr constant [16 x i8] c"branch_taken = \00", align 1

; Function Attrs: noinline nounwind optnone uwtable
define dso_local i32 @test_branch(i32 %0, i32 %1) #0 !dbg !13 {
  %3 = alloca i32, align 4
  %4 = alloca i32, align 4
  %5 = alloca i32, align 4
  store i32 %0, i32* %3, align 4
  call void @llvm.dbg.declare(metadata i32* %3, metadata !16, metadata !DIExpression()), !dbg !17
  store i32 %1, i32* %4, align 4
  call void @llvm.dbg.declare(metadata i32* %4, metadata !18, metadata !DIExpression()), !dbg !19
  call void @llvm.dbg.declare(metadata i32* %5, metadata !20, metadata !DIExpression()), !dbg !21
  store i32 0, i32* %5, align 4, !dbg !21
  %6 = load i32, i32* %4, align 4, !dbg !22
  %7 = icmp sgt i32 %6, 0, !dbg !24
  br i1 %7, label %8, label %11, !dbg !25

8:                                                ; preds = %2
  store i32 1, i32* @branch_taken, align 4, !dbg !26
  %9 = load i32, i32* %3, align 4, !dbg !28
  %10 = add nsw i32 %9, 1, !dbg !29
  store i32 %10, i32* %5, align 4, !dbg !30
  br label %14, !dbg !31

11:                                               ; preds = %2
  store i32 0, i32* @branch_taken, align 4, !dbg !32
  %12 = load i32, i32* %3, align 4, !dbg !34
  %13 = sub nsw i32 %12, 1, !dbg !35
  store i32 %13, i32* %5, align 4, !dbg !36
  br label %14

14:                                               ; preds = %11, %8
  %15 = load i32, i32* %5, align 4, !dbg !37
  ret i32 %15, !dbg !38
}

; Function Attrs: nofree nosync nounwind readnone speculatable willreturn
declare void @llvm.dbg.declare(metadata, metadata, metadata) #1

; Function Attrs: noinline nounwind optnone uwtable
define dso_local i32 @main() #0 !dbg !39 {
  %1 = alloca i32, align 4
  %2 = alloca i32, align 4
  %3 = alloca i32, align 4
  store i32 0, i32* %1, align 4
  call void @llvm.dbg.declare(metadata i32* %2, metadata !42, metadata !DIExpression()), !dbg !43
  call void @llvm.dbg.declare(metadata i32* %3, metadata !44, metadata !DIExpression()), !dbg !45
  %4 = bitcast i32* %2 to i8*, !dbg !46
  call void @klee_make_symbolic(i8* %4, i64 4, i8* getelementptr inbounds ([4 x i8], [4 x i8]* @.str, i64 0, i64 0)), !dbg !47
  %5 = load i32, i32* %2, align 4, !dbg !48
  %6 = icmp eq i32 %5, 0, !dbg !49
  %7 = zext i1 %6 to i32, !dbg !49
  %8 = sext i32 %7 to i64, !dbg !48
  call void @klee_assume(i64 %8), !dbg !50
  %9 = bitcast i32* %3 to i8*, !dbg !51
  call void @klee_make_symbolic(i8* %9, i64 4, i8* getelementptr inbounds ([7 x i8], [7 x i8]* @.str.1, i64 0, i64 0)), !dbg !52
  %10 = load i32, i32* %2, align 4, !dbg !53
  %11 = load i32, i32* %3, align 4, !dbg !54
  %12 = call i32 @test_branch(i32 %10, i32 %11), !dbg !55
  %13 = load i32, i32* @branch_taken, align 4, !dbg !56
  call void (i8*, ...) @klee_print_expr(i8* getelementptr inbounds ([16 x i8], [16 x i8]* @.str.2, i64 0, i64 0), i32 %13), !dbg !57
  ret i32 0, !dbg !58
}

declare dso_local void @klee_make_symbolic(i8*, i64, i8*) #2

declare dso_local void @klee_assume(i64) #2

declare dso_local void @klee_print_expr(i8*, ...) #2

attributes #0 = { noinline nounwind optnone uwtable "frame-pointer"="all" "min-legal-vector-width"="0" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #1 = { nofree nosync nounwind readnone speculatable willreturn }
attributes #2 = { "frame-pointer"="all" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }

!llvm.dbg.cu = !{!2}
!llvm.module.flags = !{!7, !8, !9, !10, !11}
!llvm.ident = !{!12}

!0 = !DIGlobalVariableExpression(var: !1, expr: !DIExpression())
!1 = distinct !DIGlobalVariable(name: "branch_taken", scope: !2, file: !3, line: 9, type: !6, isLocal: false, isDefinition: true)
!2 = distinct !DICompileUnit(language: DW_LANG_C99, file: !3, producer: "Ubuntu clang version 13.0.1-2ubuntu2.2", isOptimized: false, runtimeVersion: 0, emissionKind: FullDebug, enums: !4, globals: !5, splitDebugInlining: false, nameTableKind: None)
!3 = !DIFile(filename: "constrained-cases/target_false_test000001.c", directory: "/mnt/c/Users/james/OneDrive/Documents/College Classes/CS+ Semester/TestKLEE")
!4 = !{}
!5 = !{!0}
!6 = !DIBasicType(name: "int", size: 32, encoding: DW_ATE_signed)
!7 = !{i32 7, !"Dwarf Version", i32 4}
!8 = !{i32 2, !"Debug Info Version", i32 3}
!9 = !{i32 1, !"wchar_size", i32 4}
!10 = !{i32 7, !"uwtable", i32 1}
!11 = !{i32 7, !"frame-pointer", i32 2}
!12 = !{!"Ubuntu clang version 13.0.1-2ubuntu2.2"}
!13 = distinct !DISubprogram(name: "test_branch", scope: !3, file: !3, line: 13, type: !14, scopeLine: 13, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !4)
!14 = !DISubroutineType(types: !15)
!15 = !{!6, !6, !6}
!16 = !DILocalVariable(name: "pub", arg: 1, scope: !13, file: !3, line: 13, type: !6)
!17 = !DILocation(line: 13, column: 21, scope: !13)
!18 = !DILocalVariable(name: "secret", arg: 2, scope: !13, file: !3, line: 13, type: !6)
!19 = !DILocation(line: 13, column: 30, scope: !13)
!20 = !DILocalVariable(name: "ret", scope: !13, file: !3, line: 14, type: !6)
!21 = !DILocation(line: 14, column: 9, scope: !13)
!22 = !DILocation(line: 16, column: 9, scope: !23)
!23 = distinct !DILexicalBlock(scope: !13, file: !3, line: 16, column: 9)
!24 = !DILocation(line: 16, column: 16, scope: !23)
!25 = !DILocation(line: 16, column: 9, scope: !13)
!26 = !DILocation(line: 17, column: 22, scope: !27)
!27 = distinct !DILexicalBlock(scope: !23, file: !3, line: 16, column: 21)
!28 = !DILocation(line: 18, column: 15, scope: !27)
!29 = !DILocation(line: 18, column: 19, scope: !27)
!30 = !DILocation(line: 18, column: 13, scope: !27)
!31 = !DILocation(line: 19, column: 5, scope: !27)
!32 = !DILocation(line: 20, column: 22, scope: !33)
!33 = distinct !DILexicalBlock(scope: !23, file: !3, line: 19, column: 12)
!34 = !DILocation(line: 21, column: 15, scope: !33)
!35 = !DILocation(line: 21, column: 19, scope: !33)
!36 = !DILocation(line: 21, column: 13, scope: !33)
!37 = !DILocation(line: 24, column: 12, scope: !13)
!38 = !DILocation(line: 24, column: 5, scope: !13)
!39 = distinct !DISubprogram(name: "main", scope: !3, file: !3, line: 28, type: !40, scopeLine: 28, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !4)
!40 = !DISubroutineType(types: !41)
!41 = !{!6}
!42 = !DILocalVariable(name: "pub", scope: !39, file: !3, line: 29, type: !6)
!43 = !DILocation(line: 29, column: 9, scope: !39)
!44 = !DILocalVariable(name: "secret", scope: !39, file: !3, line: 29, type: !6)
!45 = !DILocation(line: 29, column: 14, scope: !39)
!46 = !DILocation(line: 31, column: 24, scope: !39)
!47 = !DILocation(line: 31, column: 5, scope: !39)
!48 = !DILocation(line: 32, column: 17, scope: !39)
!49 = !DILocation(line: 32, column: 21, scope: !39)
!50 = !DILocation(line: 32, column: 5, scope: !39)
!51 = !DILocation(line: 33, column: 24, scope: !39)
!52 = !DILocation(line: 33, column: 5, scope: !39)
!53 = !DILocation(line: 35, column: 17, scope: !39)
!54 = !DILocation(line: 35, column: 22, scope: !39)
!55 = !DILocation(line: 35, column: 5, scope: !39)
!56 = !DILocation(line: 36, column: 40, scope: !39)
!57 = !DILocation(line: 36, column: 5, scope: !39)
!58 = !DILocation(line: 37, column: 5, scope: !39)
