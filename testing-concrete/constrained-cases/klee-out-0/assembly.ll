; ModuleID = 'constrained-cases/target_true_test000003.bc'
source_filename = "constrained-cases/target_true_test000003.c"
target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-f80:128-n8:16:32:64-S128"
target triple = "x86_64-pc-linux-gnu"

@.str = private unnamed_addr constant [4 x i8] c"pub\00", align 1
@.str.1 = private unnamed_addr constant [7 x i8] c"secret\00", align 1

; Function Attrs: noinline nounwind optnone uwtable
define dso_local i32 @foo(i32 %0, i32 %1) #0 !dbg !9 {
  %3 = alloca i32, align 4
  %4 = alloca i32, align 4
  %5 = alloca i32, align 4
  store i32 %0, i32* %4, align 4
  call void @llvm.dbg.declare(metadata i32* %4, metadata !13, metadata !DIExpression()), !dbg !14
  store i32 %1, i32* %5, align 4
  call void @llvm.dbg.declare(metadata i32* %5, metadata !15, metadata !DIExpression()), !dbg !16
  %6 = load i32, i32* %4, align 4, !dbg !17
  %7 = icmp sgt i32 %6, 0, !dbg !19
  br i1 %7, label %8, label %10, !dbg !20

8:                                                ; preds = %2
  %9 = load i32, i32* %5, align 4, !dbg !21
  store i32 %9, i32* %3, align 4, !dbg !23
  br label %13, !dbg !23

10:                                               ; preds = %2
  %11 = load i32, i32* %5, align 4, !dbg !24
  %12 = sub nsw i32 0, %11, !dbg !26
  store i32 %12, i32* %3, align 4, !dbg !27
  br label %13, !dbg !27

13:                                               ; preds = %10, %8
  %14 = load i32, i32* %3, align 4, !dbg !28
  ret i32 %14, !dbg !28
}

; Function Attrs: nofree nosync nounwind readnone speculatable willreturn
declare void @llvm.dbg.declare(metadata, metadata, metadata) #1

; Function Attrs: noinline nounwind optnone uwtable
define dso_local i32 @test_branch(i32 %0, i32 %1) #0 !dbg !29 {
  %3 = alloca i32, align 4
  %4 = alloca i32, align 4
  %5 = alloca i32, align 4
  %6 = alloca i32, align 4
  store i32 %0, i32* %3, align 4
  call void @llvm.dbg.declare(metadata i32* %3, metadata !30, metadata !DIExpression()), !dbg !31
  store i32 %1, i32* %4, align 4
  call void @llvm.dbg.declare(metadata i32* %4, metadata !32, metadata !DIExpression()), !dbg !33
  call void @llvm.dbg.declare(metadata i32* %5, metadata !34, metadata !DIExpression()), !dbg !35
  %7 = load i32, i32* %3, align 4, !dbg !36
  %8 = load i32, i32* %4, align 4, !dbg !37
  %9 = call i32 @foo(i32 %7, i32 %8), !dbg !38
  store i32 %9, i32* %5, align 4, !dbg !35
  call void @llvm.dbg.declare(metadata i32* %6, metadata !39, metadata !DIExpression()), !dbg !40
  %10 = load i32, i32* %4, align 4, !dbg !41
  %11 = load i32, i32* %3, align 4, !dbg !42
  %12 = call i32 @foo(i32 %10, i32 %11), !dbg !43
  store i32 %12, i32* %6, align 4, !dbg !40
  %13 = load i32, i32* %5, align 4, !dbg !44
  %14 = load i32, i32* %6, align 4, !dbg !45
  %15 = add nsw i32 %13, %14, !dbg !46
  ret i32 %15, !dbg !47
}

; Function Attrs: noinline nounwind optnone uwtable
define dso_local i32 @main() #0 !dbg !48 {
  %1 = alloca i32, align 4
  %2 = alloca i32, align 4
  %3 = alloca i32, align 4
  store i32 0, i32* %1, align 4
  call void @llvm.dbg.declare(metadata i32* %2, metadata !51, metadata !DIExpression()), !dbg !52
  call void @llvm.dbg.declare(metadata i32* %3, metadata !53, metadata !DIExpression()), !dbg !54
  %4 = bitcast i32* %2 to i8*, !dbg !55
  call void @klee_make_symbolic(i8* %4, i64 4, i8* getelementptr inbounds ([4 x i8], [4 x i8]* @.str, i64 0, i64 0)), !dbg !56
  %5 = load i32, i32* %2, align 4, !dbg !57
  %6 = icmp eq i32 %5, 2147483647, !dbg !58
  %7 = zext i1 %6 to i32, !dbg !58
  %8 = sext i32 %7 to i64, !dbg !57
  call void @klee_assume(i64 %8), !dbg !59
  %9 = bitcast i32* %3 to i8*, !dbg !60
  call void @klee_make_symbolic(i8* %9, i64 4, i8* getelementptr inbounds ([7 x i8], [7 x i8]* @.str.1, i64 0, i64 0)), !dbg !61
  %10 = load i32, i32* %2, align 4, !dbg !62
  %11 = load i32, i32* %3, align 4, !dbg !63
  %12 = call i32 @test_branch(i32 %10, i32 %11), !dbg !64
  ret i32 0, !dbg !65
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
!9 = distinct !DISubprogram(name: "foo", scope: !1, file: !1, line: 15, type: !10, scopeLine: 15, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !0, retainedNodes: !2)
!10 = !DISubroutineType(types: !11)
!11 = !{!12, !12, !12}
!12 = !DIBasicType(name: "int", size: 32, encoding: DW_ATE_signed)
!13 = !DILocalVariable(name: "x", arg: 1, scope: !9, file: !1, line: 15, type: !12)
!14 = !DILocation(line: 15, column: 13, scope: !9)
!15 = !DILocalVariable(name: "y", arg: 2, scope: !9, file: !1, line: 15, type: !12)
!16 = !DILocation(line: 15, column: 20, scope: !9)
!17 = !DILocation(line: 16, column: 9, scope: !18)
!18 = distinct !DILexicalBlock(scope: !9, file: !1, line: 16, column: 9)
!19 = !DILocation(line: 16, column: 11, scope: !18)
!20 = !DILocation(line: 16, column: 9, scope: !9)
!21 = !DILocation(line: 17, column: 16, scope: !22)
!22 = distinct !DILexicalBlock(scope: !18, file: !1, line: 16, column: 16)
!23 = !DILocation(line: 17, column: 9, scope: !22)
!24 = !DILocation(line: 19, column: 17, scope: !25)
!25 = distinct !DILexicalBlock(scope: !18, file: !1, line: 18, column: 12)
!26 = !DILocation(line: 19, column: 16, scope: !25)
!27 = !DILocation(line: 19, column: 9, scope: !25)
!28 = !DILocation(line: 21, column: 1, scope: !9)
!29 = distinct !DISubprogram(name: "test_branch", scope: !1, file: !1, line: 25, type: !10, scopeLine: 25, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !0, retainedNodes: !2)
!30 = !DILocalVariable(name: "pub", arg: 1, scope: !29, file: !1, line: 25, type: !12)
!31 = !DILocation(line: 25, column: 21, scope: !29)
!32 = !DILocalVariable(name: "secret", arg: 2, scope: !29, file: !1, line: 25, type: !12)
!33 = !DILocation(line: 25, column: 30, scope: !29)
!34 = !DILocalVariable(name: "ret1", scope: !29, file: !1, line: 26, type: !12)
!35 = !DILocation(line: 26, column: 9, scope: !29)
!36 = !DILocation(line: 26, column: 20, scope: !29)
!37 = !DILocation(line: 26, column: 25, scope: !29)
!38 = !DILocation(line: 26, column: 16, scope: !29)
!39 = !DILocalVariable(name: "ret2", scope: !29, file: !1, line: 27, type: !12)
!40 = !DILocation(line: 27, column: 9, scope: !29)
!41 = !DILocation(line: 27, column: 20, scope: !29)
!42 = !DILocation(line: 27, column: 28, scope: !29)
!43 = !DILocation(line: 27, column: 16, scope: !29)
!44 = !DILocation(line: 28, column: 12, scope: !29)
!45 = !DILocation(line: 28, column: 19, scope: !29)
!46 = !DILocation(line: 28, column: 17, scope: !29)
!47 = !DILocation(line: 28, column: 5, scope: !29)
!48 = distinct !DISubprogram(name: "main", scope: !1, file: !1, line: 32, type: !49, scopeLine: 32, spFlags: DISPFlagDefinition, unit: !0, retainedNodes: !2)
!49 = !DISubroutineType(types: !50)
!50 = !{!12}
!51 = !DILocalVariable(name: "pub", scope: !48, file: !1, line: 33, type: !12)
!52 = !DILocation(line: 33, column: 9, scope: !48)
!53 = !DILocalVariable(name: "secret", scope: !48, file: !1, line: 33, type: !12)
!54 = !DILocation(line: 33, column: 14, scope: !48)
!55 = !DILocation(line: 35, column: 24, scope: !48)
!56 = !DILocation(line: 35, column: 5, scope: !48)
!57 = !DILocation(line: 36, column: 17, scope: !48)
!58 = !DILocation(line: 36, column: 21, scope: !48)
!59 = !DILocation(line: 36, column: 5, scope: !48)
!60 = !DILocation(line: 37, column: 24, scope: !48)
!61 = !DILocation(line: 37, column: 5, scope: !48)
!62 = !DILocation(line: 39, column: 17, scope: !48)
!63 = !DILocation(line: 39, column: 22, scope: !48)
!64 = !DILocation(line: 39, column: 5, scope: !48)
!65 = !DILocation(line: 40, column: 5, scope: !48)
