; ModuleID = '/home/james/klee-deps/testKLEE/tests/test25.bc'
source_filename = "/home/james/klee-deps/testKLEE/tests/test25.c"
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
  call void @llvm.dbg.declare(metadata i32* %3, metadata !14, metadata !DIExpression()), !dbg !15
  store i32 %1, i32* %4, align 4
  call void @llvm.dbg.declare(metadata i32* %4, metadata !16, metadata !DIExpression()), !dbg !17
  call void @llvm.dbg.declare(metadata i32* %5, metadata !18, metadata !DIExpression()), !dbg !20
  store i32 0, i32* %5, align 4, !dbg !20
  br label %6, !dbg !21

6:                                                ; preds = %13, %2
  %7 = load i32, i32* %5, align 4, !dbg !22
  %8 = load i32, i32* %4, align 4, !dbg !24
  %9 = icmp slt i32 %7, %8, !dbg !25
  br i1 %9, label %10, label %16, !dbg !26

10:                                               ; preds = %6
  %11 = load i32, i32* %3, align 4, !dbg !27
  %12 = add nsw i32 %11, 1, !dbg !27
  store i32 %12, i32* %3, align 4, !dbg !27
  br label %13, !dbg !29

13:                                               ; preds = %10
  %14 = load i32, i32* %5, align 4, !dbg !30
  %15 = add nsw i32 %14, 1, !dbg !30
  store i32 %15, i32* %5, align 4, !dbg !30
  br label %6, !dbg !31, !llvm.loop !32

16:                                               ; preds = %6
  %17 = load i32, i32* %3, align 4, !dbg !35
  ret i32 %17, !dbg !36
}

; Function Attrs: nofree nosync nounwind readnone speculatable willreturn
declare void @llvm.dbg.declare(metadata, metadata, metadata) #1

; Function Attrs: noinline nounwind optnone uwtable
define dso_local i32 @main() #0 !dbg !37 {
  %1 = alloca i32, align 4
  %2 = alloca i32, align 4
  %3 = alloca i32, align 4
  store i32 0, i32* %1, align 4
  call void @llvm.dbg.declare(metadata i32* %2, metadata !40, metadata !DIExpression()), !dbg !41
  call void @llvm.dbg.declare(metadata i32* %3, metadata !42, metadata !DIExpression()), !dbg !43
  %4 = bitcast i32* %2 to i8*, !dbg !44
  call void @klee_make_symbolic(i8* %4, i64 4, i8* getelementptr inbounds ([4 x i8], [4 x i8]* @.str, i64 0, i64 0)), !dbg !45
  %5 = bitcast i32* %3 to i8*, !dbg !46
  call void @klee_make_symbolic(i8* %5, i64 4, i8* getelementptr inbounds ([7 x i8], [7 x i8]* @.str.1, i64 0, i64 0)), !dbg !47
  %6 = load i32, i32* %3, align 4, !dbg !48
  %7 = icmp sge i32 %6, 0, !dbg !49
  %8 = zext i1 %7 to i32, !dbg !49
  %9 = sext i32 %8 to i64, !dbg !48
  call void @klee_assume(i64 %9), !dbg !50
  %10 = load i32, i32* %3, align 4, !dbg !51
  %11 = icmp slt i32 %10, 64, !dbg !52
  %12 = zext i1 %11 to i32, !dbg !52
  %13 = sext i32 %12 to i64, !dbg !51
  call void @klee_assume(i64 %13), !dbg !53
  %14 = load i32, i32* %2, align 4, !dbg !54
  %15 = load i32, i32* %3, align 4, !dbg !55
  %16 = call i32 @test_branch(i32 %14, i32 %15), !dbg !56
  ret i32 0, !dbg !57
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
!1 = !DIFile(filename: "/home/james/klee-deps/testKLEE/tests/test25.c", directory: "/home/james/klee-deps/testKLEE")
!2 = !{}
!3 = !{i32 7, !"Dwarf Version", i32 4}
!4 = !{i32 2, !"Debug Info Version", i32 3}
!5 = !{i32 1, !"wchar_size", i32 4}
!6 = !{i32 7, !"uwtable", i32 1}
!7 = !{i32 7, !"frame-pointer", i32 2}
!8 = !{!"Ubuntu clang version 13.0.1-2ubuntu2.2"}
!9 = distinct !DISubprogram(name: "test_branch", scope: !10, file: !10, line: 15, type: !11, scopeLine: 15, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !0, retainedNodes: !2)
!10 = !DIFile(filename: "tests/test25.c", directory: "/home/james/klee-deps/testKLEE")
!11 = !DISubroutineType(types: !12)
!12 = !{!13, !13, !13}
!13 = !DIBasicType(name: "int", size: 32, encoding: DW_ATE_signed)
!14 = !DILocalVariable(name: "pub", arg: 1, scope: !9, file: !10, line: 15, type: !13)
!15 = !DILocation(line: 15, column: 21, scope: !9)
!16 = !DILocalVariable(name: "secret", arg: 2, scope: !9, file: !10, line: 15, type: !13)
!17 = !DILocation(line: 15, column: 30, scope: !9)
!18 = !DILocalVariable(name: "i", scope: !19, file: !10, line: 16, type: !13)
!19 = distinct !DILexicalBlock(scope: !9, file: !10, line: 16, column: 5)
!20 = !DILocation(line: 16, column: 14, scope: !19)
!21 = !DILocation(line: 16, column: 10, scope: !19)
!22 = !DILocation(line: 16, column: 19, scope: !23)
!23 = distinct !DILexicalBlock(scope: !19, file: !10, line: 16, column: 5)
!24 = !DILocation(line: 16, column: 23, scope: !23)
!25 = !DILocation(line: 16, column: 21, scope: !23)
!26 = !DILocation(line: 16, column: 5, scope: !19)
!27 = !DILocation(line: 17, column: 12, scope: !28)
!28 = distinct !DILexicalBlock(scope: !23, file: !10, line: 16, column: 37)
!29 = !DILocation(line: 18, column: 5, scope: !28)
!30 = !DILocation(line: 16, column: 33, scope: !23)
!31 = !DILocation(line: 16, column: 5, scope: !23)
!32 = distinct !{!32, !26, !33, !34}
!33 = !DILocation(line: 18, column: 5, scope: !19)
!34 = !{!"llvm.loop.mustprogress"}
!35 = !DILocation(line: 19, column: 12, scope: !9)
!36 = !DILocation(line: 19, column: 5, scope: !9)
!37 = distinct !DISubprogram(name: "main", scope: !10, file: !10, line: 23, type: !38, scopeLine: 23, spFlags: DISPFlagDefinition, unit: !0, retainedNodes: !2)
!38 = !DISubroutineType(types: !39)
!39 = !{!13}
!40 = !DILocalVariable(name: "pub", scope: !37, file: !10, line: 24, type: !13)
!41 = !DILocation(line: 24, column: 9, scope: !37)
!42 = !DILocalVariable(name: "secret", scope: !37, file: !10, line: 24, type: !13)
!43 = !DILocation(line: 24, column: 14, scope: !37)
!44 = !DILocation(line: 26, column: 24, scope: !37)
!45 = !DILocation(line: 26, column: 5, scope: !37)
!46 = !DILocation(line: 27, column: 24, scope: !37)
!47 = !DILocation(line: 27, column: 5, scope: !37)
!48 = !DILocation(line: 28, column: 17, scope: !37)
!49 = !DILocation(line: 28, column: 24, scope: !37)
!50 = !DILocation(line: 28, column: 5, scope: !37)
!51 = !DILocation(line: 29, column: 17, scope: !37)
!52 = !DILocation(line: 29, column: 24, scope: !37)
!53 = !DILocation(line: 29, column: 5, scope: !37)
!54 = !DILocation(line: 31, column: 17, scope: !37)
!55 = !DILocation(line: 31, column: 22, scope: !37)
!56 = !DILocation(line: 31, column: 5, scope: !37)
!57 = !DILocation(line: 32, column: 5, scope: !37)
