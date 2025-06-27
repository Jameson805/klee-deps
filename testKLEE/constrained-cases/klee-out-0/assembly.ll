; ModuleID = 'constrained-cases/target_true_test000064.bc'
source_filename = "constrained-cases/target_true_test000064.c"
target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-f80:128-n8:16:32:64-S128"
target triple = "x86_64-pc-linux-gnu"

@.str = private unnamed_addr constant [4 x i8] c"pub\00", align 1
@.str.1 = private unnamed_addr constant [7 x i8] c"secret\00", align 1

; Function Attrs: noinline nounwind optnone uwtable
define dso_local i32 @test_branch(i32 %0, i32 %1) #0 !dbg !9 {
  %3 = alloca i32, align 4
  %4 = alloca i32, align 4
  %5 = alloca i32, align 4
  store i32 %0, i32* %3, align 4
  call void @llvm.dbg.declare(metadata i32* %3, metadata !13, metadata !DIExpression()), !dbg !14
  store i32 %1, i32* %4, align 4
  call void @llvm.dbg.declare(metadata i32* %4, metadata !15, metadata !DIExpression()), !dbg !16
  call void @llvm.dbg.declare(metadata i32* %5, metadata !17, metadata !DIExpression()), !dbg !19
  store i32 0, i32* %5, align 4, !dbg !19
  br label %6, !dbg !20

6:                                                ; preds = %13, %2
  %7 = load i32, i32* %5, align 4, !dbg !21
  %8 = load i32, i32* %4, align 4, !dbg !23
  %9 = icmp slt i32 %7, %8, !dbg !24
  br i1 %9, label %10, label %16, !dbg !25

10:                                               ; preds = %6
  %11 = load i32, i32* %3, align 4, !dbg !26
  %12 = add nsw i32 %11, 1, !dbg !26
  store i32 %12, i32* %3, align 4, !dbg !26
  br label %13, !dbg !28

13:                                               ; preds = %10
  %14 = load i32, i32* %5, align 4, !dbg !29
  %15 = add nsw i32 %14, 1, !dbg !29
  store i32 %15, i32* %5, align 4, !dbg !29
  br label %6, !dbg !30, !llvm.loop !31

16:                                               ; preds = %6
  %17 = load i32, i32* %3, align 4, !dbg !34
  ret i32 %17, !dbg !35
}

; Function Attrs: nofree nosync nounwind readnone speculatable willreturn
declare void @llvm.dbg.declare(metadata, metadata, metadata) #1

; Function Attrs: noinline nounwind optnone uwtable
define dso_local i32 @main() #0 !dbg !36 {
  %1 = alloca i32, align 4
  %2 = alloca i32, align 4
  %3 = alloca i32, align 4
  store i32 0, i32* %1, align 4
  call void @llvm.dbg.declare(metadata i32* %2, metadata !39, metadata !DIExpression()), !dbg !40
  call void @llvm.dbg.declare(metadata i32* %3, metadata !41, metadata !DIExpression()), !dbg !42
  %4 = bitcast i32* %2 to i8*, !dbg !43
  call void @klee_make_symbolic(i8* %4, i64 4, i8* getelementptr inbounds ([4 x i8], [4 x i8]* @.str, i64 0, i64 0)), !dbg !44
  %5 = load i32, i32* %2, align 4, !dbg !45
  %6 = icmp eq i32 %5, 0, !dbg !46
  %7 = zext i1 %6 to i32, !dbg !46
  %8 = sext i32 %7 to i64, !dbg !45
  call void @klee_assume(i64 %8), !dbg !47
  %9 = bitcast i32* %3 to i8*, !dbg !48
  call void @klee_make_symbolic(i8* %9, i64 4, i8* getelementptr inbounds ([7 x i8], [7 x i8]* @.str.1, i64 0, i64 0)), !dbg !49
  %10 = load i32, i32* %3, align 4, !dbg !50
  %11 = icmp sge i32 %10, 0, !dbg !51
  %12 = zext i1 %11 to i32, !dbg !51
  %13 = sext i32 %12 to i64, !dbg !50
  call void @klee_assume(i64 %13), !dbg !52
  %14 = load i32, i32* %3, align 4, !dbg !53
  %15 = icmp slt i32 %14, 64, !dbg !54
  %16 = zext i1 %15 to i32, !dbg !54
  %17 = sext i32 %16 to i64, !dbg !53
  call void @klee_assume(i64 %17), !dbg !55
  %18 = load i32, i32* %2, align 4, !dbg !56
  %19 = load i32, i32* %3, align 4, !dbg !57
  %20 = call i32 @test_branch(i32 %18, i32 %19), !dbg !58
  ret i32 0, !dbg !59
}

declare dso_local void @klee_make_symbolic(i8*, i64, i8*) #2

declare dso_local void @klee_assume(i64) #2

attributes #0 = { noinline nounwind optnone uwtable "frame-pointer"="all" "min-legal-vector-width"="0" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #1 = { nofree nosync nounwind readnone speculatable willreturn }
attributes #2 = { "frame-pointer"="all" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }

!llvm.dbg.cu = !{!0}
!llvm.module.flags = !{!3, !4, !5, !6, !7}
!llvm.ident = !{!8}

!0 = distinct !DICompileUnit(language: DW_LANG_C99, file: !1, producer: "Ubuntu clang version 13.0.1-2ubuntu2.2", isOptimized: false, runtimeVersion: 0, emissionKind: FullDebug, enums: !2, splitDebugInlining: false, nameTableKind: None)
!1 = !DIFile(filename: "constrained-cases/target_true_test000064.c", directory: "/home/james/klee-deps/testKLEE")
!2 = !{}
!3 = !{i32 7, !"Dwarf Version", i32 4}
!4 = !{i32 2, !"Debug Info Version", i32 3}
!5 = !{i32 1, !"wchar_size", i32 4}
!6 = !{i32 7, !"uwtable", i32 1}
!7 = !{i32 7, !"frame-pointer", i32 2}
!8 = !{!"Ubuntu clang version 13.0.1-2ubuntu2.2"}
!9 = distinct !DISubprogram(name: "test_branch", scope: !1, file: !1, line: 15, type: !10, scopeLine: 15, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !0, retainedNodes: !2)
!10 = !DISubroutineType(types: !11)
!11 = !{!12, !12, !12}
!12 = !DIBasicType(name: "int", size: 32, encoding: DW_ATE_signed)
!13 = !DILocalVariable(name: "pub", arg: 1, scope: !9, file: !1, line: 15, type: !12)
!14 = !DILocation(line: 15, column: 21, scope: !9)
!15 = !DILocalVariable(name: "secret", arg: 2, scope: !9, file: !1, line: 15, type: !12)
!16 = !DILocation(line: 15, column: 30, scope: !9)
!17 = !DILocalVariable(name: "i", scope: !18, file: !1, line: 16, type: !12)
!18 = distinct !DILexicalBlock(scope: !9, file: !1, line: 16, column: 5)
!19 = !DILocation(line: 16, column: 14, scope: !18)
!20 = !DILocation(line: 16, column: 10, scope: !18)
!21 = !DILocation(line: 16, column: 19, scope: !22)
!22 = distinct !DILexicalBlock(scope: !18, file: !1, line: 16, column: 5)
!23 = !DILocation(line: 16, column: 23, scope: !22)
!24 = !DILocation(line: 16, column: 21, scope: !22)
!25 = !DILocation(line: 16, column: 5, scope: !18)
!26 = !DILocation(line: 17, column: 12, scope: !27)
!27 = distinct !DILexicalBlock(scope: !22, file: !1, line: 16, column: 37)
!28 = !DILocation(line: 18, column: 5, scope: !27)
!29 = !DILocation(line: 16, column: 33, scope: !22)
!30 = !DILocation(line: 16, column: 5, scope: !22)
!31 = distinct !{!31, !25, !32, !33}
!32 = !DILocation(line: 18, column: 5, scope: !18)
!33 = !{!"llvm.loop.mustprogress"}
!34 = !DILocation(line: 19, column: 12, scope: !9)
!35 = !DILocation(line: 19, column: 5, scope: !9)
!36 = distinct !DISubprogram(name: "main", scope: !1, file: !1, line: 23, type: !37, scopeLine: 23, spFlags: DISPFlagDefinition, unit: !0, retainedNodes: !2)
!37 = !DISubroutineType(types: !38)
!38 = !{!12}
!39 = !DILocalVariable(name: "pub", scope: !36, file: !1, line: 24, type: !12)
!40 = !DILocation(line: 24, column: 9, scope: !36)
!41 = !DILocalVariable(name: "secret", scope: !36, file: !1, line: 24, type: !12)
!42 = !DILocation(line: 24, column: 14, scope: !36)
!43 = !DILocation(line: 26, column: 24, scope: !36)
!44 = !DILocation(line: 26, column: 5, scope: !36)
!45 = !DILocation(line: 27, column: 17, scope: !36)
!46 = !DILocation(line: 27, column: 21, scope: !36)
!47 = !DILocation(line: 27, column: 5, scope: !36)
!48 = !DILocation(line: 28, column: 24, scope: !36)
!49 = !DILocation(line: 28, column: 5, scope: !36)
!50 = !DILocation(line: 29, column: 17, scope: !36)
!51 = !DILocation(line: 29, column: 24, scope: !36)
!52 = !DILocation(line: 29, column: 5, scope: !36)
!53 = !DILocation(line: 30, column: 17, scope: !36)
!54 = !DILocation(line: 30, column: 24, scope: !36)
!55 = !DILocation(line: 30, column: 5, scope: !36)
!56 = !DILocation(line: 32, column: 17, scope: !36)
!57 = !DILocation(line: 32, column: 22, scope: !36)
!58 = !DILocation(line: 32, column: 5, scope: !36)
!59 = !DILocation(line: 33, column: 5, scope: !36)
