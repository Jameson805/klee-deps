; ModuleID = '/home/james/klee-deps/testKLEE/tests/test2.bc'
source_filename = "/home/james/klee-deps/testKLEE/tests/test2.c"
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
  call void @llvm.dbg.declare(metadata i32* %5, metadata !18, metadata !DIExpression()), !dbg !19
  store i32 0, i32* %5, align 4, !dbg !19
  %6 = load i32, i32* %3, align 4, !dbg !20
  %7 = icmp sgt i32 %6, 0, !dbg !22
  br i1 %7, label %8, label %11, !dbg !23

8:                                                ; preds = %2
  %9 = load i32, i32* %5, align 4, !dbg !24
  %10 = add nsw i32 %9, 1, !dbg !24
  store i32 %10, i32* %5, align 4, !dbg !24
  br label %14, !dbg !26

11:                                               ; preds = %2
  %12 = load i32, i32* %5, align 4, !dbg !27
  %13 = add nsw i32 %12, -1, !dbg !27
  store i32 %13, i32* %5, align 4, !dbg !27
  br label %14

14:                                               ; preds = %11, %8
  %15 = load i32, i32* %4, align 4, !dbg !29
  %16 = icmp sgt i32 %15, 0, !dbg !31
  br i1 %16, label %17, label %20, !dbg !32

17:                                               ; preds = %14
  %18 = load i32, i32* %5, align 4, !dbg !33
  %19 = add nsw i32 %18, 1, !dbg !33
  store i32 %19, i32* %5, align 4, !dbg !33
  br label %23, !dbg !35

20:                                               ; preds = %14
  %21 = load i32, i32* %5, align 4, !dbg !36
  %22 = add nsw i32 %21, -1, !dbg !36
  store i32 %22, i32* %5, align 4, !dbg !36
  br label %23

23:                                               ; preds = %20, %17
  %24 = load i32, i32* %5, align 4, !dbg !38
  ret i32 %24, !dbg !39
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
  ret i32 0, !dbg !54
}

declare dso_local void @klee_make_symbolic(i8*, i64, i8*) #2

attributes #0 = { noinline nounwind optnone uwtable "frame-pointer"="all" "min-legal-vector-width"="0" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #1 = { nofree nosync nounwind readnone speculatable willreturn }
attributes #2 = { "frame-pointer"="all" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }

!llvm.dbg.cu = !{!0}
!llvm.module.flags = !{!3, !4, !5, !6, !7}
!llvm.ident = !{!8}

!0 = distinct !DICompileUnit(language: DW_LANG_C99, file: !1, producer: "Ubuntu clang version 13.0.1-2ubuntu2.2", isOptimized: false, runtimeVersion: 0, emissionKind: FullDebug, enums: !2, splitDebugInlining: false, nameTableKind: None)
!1 = !DIFile(filename: "/home/james/klee-deps/testKLEE/tests/test2.c", directory: "/home/james/klee-deps/testKLEE")
!2 = !{}
!3 = !{i32 7, !"Dwarf Version", i32 4}
!4 = !{i32 2, !"Debug Info Version", i32 3}
!5 = !{i32 1, !"wchar_size", i32 4}
!6 = !{i32 7, !"uwtable", i32 1}
!7 = !{i32 7, !"frame-pointer", i32 2}
!8 = !{!"Ubuntu clang version 13.0.1-2ubuntu2.2"}
!9 = distinct !DISubprogram(name: "test_branch", scope: !10, file: !10, line: 15, type: !11, scopeLine: 15, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !0, retainedNodes: !2)
!10 = !DIFile(filename: "tests/test2.c", directory: "/home/james/klee-deps/testKLEE")
!11 = !DISubroutineType(types: !12)
!12 = !{!13, !13, !13}
!13 = !DIBasicType(name: "int", size: 32, encoding: DW_ATE_signed)
!14 = !DILocalVariable(name: "pub", arg: 1, scope: !9, file: !10, line: 15, type: !13)
!15 = !DILocation(line: 15, column: 21, scope: !9)
!16 = !DILocalVariable(name: "secret", arg: 2, scope: !9, file: !10, line: 15, type: !13)
!17 = !DILocation(line: 15, column: 30, scope: !9)
!18 = !DILocalVariable(name: "ret", scope: !9, file: !10, line: 16, type: !13)
!19 = !DILocation(line: 16, column: 9, scope: !9)
!20 = !DILocation(line: 18, column: 9, scope: !21)
!21 = distinct !DILexicalBlock(scope: !9, file: !10, line: 18, column: 9)
!22 = !DILocation(line: 18, column: 13, scope: !21)
!23 = !DILocation(line: 18, column: 9, scope: !9)
!24 = !DILocation(line: 19, column: 12, scope: !25)
!25 = distinct !DILexicalBlock(scope: !21, file: !10, line: 18, column: 18)
!26 = !DILocation(line: 20, column: 5, scope: !25)
!27 = !DILocation(line: 21, column: 12, scope: !28)
!28 = distinct !DILexicalBlock(scope: !21, file: !10, line: 20, column: 12)
!29 = !DILocation(line: 23, column: 9, scope: !30)
!30 = distinct !DILexicalBlock(scope: !9, file: !10, line: 23, column: 9)
!31 = !DILocation(line: 23, column: 16, scope: !30)
!32 = !DILocation(line: 23, column: 9, scope: !9)
!33 = !DILocation(line: 24, column: 12, scope: !34)
!34 = distinct !DILexicalBlock(scope: !30, file: !10, line: 23, column: 21)
!35 = !DILocation(line: 25, column: 5, scope: !34)
!36 = !DILocation(line: 26, column: 12, scope: !37)
!37 = distinct !DILexicalBlock(scope: !30, file: !10, line: 25, column: 12)
!38 = !DILocation(line: 29, column: 12, scope: !9)
!39 = !DILocation(line: 29, column: 5, scope: !9)
!40 = distinct !DISubprogram(name: "main", scope: !10, file: !10, line: 33, type: !41, scopeLine: 33, spFlags: DISPFlagDefinition, unit: !0, retainedNodes: !2)
!41 = !DISubroutineType(types: !42)
!42 = !{!13}
!43 = !DILocalVariable(name: "pub", scope: !40, file: !10, line: 34, type: !13)
!44 = !DILocation(line: 34, column: 9, scope: !40)
!45 = !DILocalVariable(name: "secret", scope: !40, file: !10, line: 34, type: !13)
!46 = !DILocation(line: 34, column: 14, scope: !40)
!47 = !DILocation(line: 36, column: 24, scope: !40)
!48 = !DILocation(line: 36, column: 5, scope: !40)
!49 = !DILocation(line: 37, column: 24, scope: !40)
!50 = !DILocation(line: 37, column: 5, scope: !40)
!51 = !DILocation(line: 39, column: 17, scope: !40)
!52 = !DILocation(line: 39, column: 22, scope: !40)
!53 = !DILocation(line: 39, column: 5, scope: !40)
!54 = !DILocation(line: 40, column: 5, scope: !40)
