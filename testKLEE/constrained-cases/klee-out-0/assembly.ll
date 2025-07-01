; ModuleID = 'constrained-cases/target_true_test000003.bc'
source_filename = "constrained-cases/target_true_test000003.c"
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
  call void @llvm.dbg.declare(metadata i32* %5, metadata !17, metadata !DIExpression()), !dbg !18
  store i32 0, i32* %5, align 4, !dbg !18
  %6 = load i32, i32* %3, align 4, !dbg !19
  %7 = icmp sgt i32 %6, 0, !dbg !21
  br i1 %7, label %8, label %11, !dbg !22

8:                                                ; preds = %2
  %9 = load i32, i32* %5, align 4, !dbg !23
  %10 = add nsw i32 %9, 1, !dbg !23
  store i32 %10, i32* %5, align 4, !dbg !23
  br label %14, !dbg !25

11:                                               ; preds = %2
  %12 = load i32, i32* %5, align 4, !dbg !26
  %13 = add nsw i32 %12, -1, !dbg !26
  store i32 %13, i32* %5, align 4, !dbg !26
  br label %14

14:                                               ; preds = %11, %8
  %15 = load i32, i32* %4, align 4, !dbg !28
  %16 = icmp sgt i32 %15, 0, !dbg !30
  br i1 %16, label %17, label %20, !dbg !31

17:                                               ; preds = %14
  %18 = load i32, i32* %5, align 4, !dbg !32
  %19 = add nsw i32 %18, 1, !dbg !32
  store i32 %19, i32* %5, align 4, !dbg !32
  br label %23, !dbg !34

20:                                               ; preds = %14
  %21 = load i32, i32* %5, align 4, !dbg !35
  %22 = add nsw i32 %21, -1, !dbg !35
  store i32 %22, i32* %5, align 4, !dbg !35
  br label %23

23:                                               ; preds = %20, %17
  %24 = load i32, i32* %5, align 4, !dbg !37
  ret i32 %24, !dbg !38
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
  ret i32 0, !dbg !56
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
!1 = !DIFile(filename: "constrained-cases/target_true_test000003.c", directory: "/home/james/klee-deps/testKLEE")
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
!17 = !DILocalVariable(name: "ret", scope: !9, file: !1, line: 16, type: !12)
!18 = !DILocation(line: 16, column: 9, scope: !9)
!19 = !DILocation(line: 18, column: 9, scope: !20)
!20 = distinct !DILexicalBlock(scope: !9, file: !1, line: 18, column: 9)
!21 = !DILocation(line: 18, column: 13, scope: !20)
!22 = !DILocation(line: 18, column: 9, scope: !9)
!23 = !DILocation(line: 19, column: 12, scope: !24)
!24 = distinct !DILexicalBlock(scope: !20, file: !1, line: 18, column: 18)
!25 = !DILocation(line: 20, column: 5, scope: !24)
!26 = !DILocation(line: 21, column: 12, scope: !27)
!27 = distinct !DILexicalBlock(scope: !20, file: !1, line: 20, column: 12)
!28 = !DILocation(line: 23, column: 9, scope: !29)
!29 = distinct !DILexicalBlock(scope: !9, file: !1, line: 23, column: 9)
!30 = !DILocation(line: 23, column: 16, scope: !29)
!31 = !DILocation(line: 23, column: 9, scope: !9)
!32 = !DILocation(line: 24, column: 12, scope: !33)
!33 = distinct !DILexicalBlock(scope: !29, file: !1, line: 23, column: 21)
!34 = !DILocation(line: 25, column: 5, scope: !33)
!35 = !DILocation(line: 26, column: 12, scope: !36)
!36 = distinct !DILexicalBlock(scope: !29, file: !1, line: 25, column: 12)
!37 = !DILocation(line: 29, column: 12, scope: !9)
!38 = !DILocation(line: 29, column: 5, scope: !9)
!39 = distinct !DISubprogram(name: "main", scope: !1, file: !1, line: 33, type: !40, scopeLine: 33, spFlags: DISPFlagDefinition, unit: !0, retainedNodes: !2)
!40 = !DISubroutineType(types: !41)
!41 = !{!12}
!42 = !DILocalVariable(name: "pub", scope: !39, file: !1, line: 34, type: !12)
!43 = !DILocation(line: 34, column: 9, scope: !39)
!44 = !DILocalVariable(name: "secret", scope: !39, file: !1, line: 34, type: !12)
!45 = !DILocation(line: 34, column: 14, scope: !39)
!46 = !DILocation(line: 36, column: 24, scope: !39)
!47 = !DILocation(line: 36, column: 5, scope: !39)
!48 = !DILocation(line: 37, column: 17, scope: !39)
!49 = !DILocation(line: 37, column: 21, scope: !39)
!50 = !DILocation(line: 37, column: 5, scope: !39)
!51 = !DILocation(line: 38, column: 24, scope: !39)
!52 = !DILocation(line: 38, column: 5, scope: !39)
!53 = !DILocation(line: 40, column: 17, scope: !39)
!54 = !DILocation(line: 40, column: 22, scope: !39)
!55 = !DILocation(line: 40, column: 5, scope: !39)
!56 = !DILocation(line: 41, column: 5, scope: !39)
