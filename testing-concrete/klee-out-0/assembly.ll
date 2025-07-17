; ModuleID = '/home/james/klee-deps/testKLEE/target-branch-log/test3.bc'
source_filename = "/home/james/klee-deps/testKLEE/target-branch-log/test3.c"
target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-f80:128-n8:16:32:64-S128"
target triple = "x86_64-pc-linux-gnu"

@branch_index_1 = dso_local global i32 0, align 4, !dbg !0
@branch_index_2 = dso_local global i32 0, align 4, !dbg !6
@branch_history_1 = dso_local global [64 x i32] zeroinitializer, align 16, !dbg !10
@branch_history_2 = dso_local global [64 x i32] zeroinitializer, align 16, !dbg !15
@.str = private unnamed_addr constant [8 x i8] c"secret1\00", align 1
@.str.1 = private unnamed_addr constant [8 x i8] c"secret2\00", align 1
@.str.2 = private unnamed_addr constant [43 x i8] c"branch_history_1[i] == branch_history_2[i]\00", align 1
@.str.3 = private unnamed_addr constant [57 x i8] c"/home/james/klee-deps/testKLEE/target-branch-log/test3.c\00", align 1
@__PRETTY_FUNCTION__.main = private unnamed_addr constant [11 x i8] c"int main()\00", align 1
@.str.4 = private unnamed_addr constant [8 x i8] c"IGNORED\00", align 1
@.str.1.5 = private unnamed_addr constant [16 x i8] c"overshift error\00", align 1
@.str.2.6 = private unnamed_addr constant [14 x i8] c"overshift.err\00", align 1

; Function Attrs: noinline nounwind optnone uwtable
define dso_local void @reset_globals() #0 !dbg !25 {
  %1 = alloca i32, align 4
  call void @llvm.dbg.declare(metadata i32* %1, metadata !28, metadata !DIExpression()), !dbg !30
  store i32 0, i32* %1, align 4, !dbg !30
  br label %2, !dbg !31

2:                                                ; preds = %12, %0
  %3 = load i32, i32* %1, align 4, !dbg !32
  %4 = icmp slt i32 %3, 64, !dbg !34
  br i1 %4, label %5, label %15, !dbg !35

5:                                                ; preds = %2
  %6 = load i32, i32* %1, align 4, !dbg !36
  %7 = sext i32 %6 to i64, !dbg !38
  %8 = getelementptr inbounds [64 x i32], [64 x i32]* @branch_history_1, i64 0, i64 %7, !dbg !38
  store i32 -1, i32* %8, align 4, !dbg !39
  %9 = load i32, i32* %1, align 4, !dbg !40
  %10 = sext i32 %9 to i64, !dbg !41
  %11 = getelementptr inbounds [64 x i32], [64 x i32]* @branch_history_2, i64 0, i64 %10, !dbg !41
  store i32 -1, i32* %11, align 4, !dbg !42
  br label %12, !dbg !43

12:                                               ; preds = %5
  %13 = load i32, i32* %1, align 4, !dbg !44
  %14 = add nsw i32 %13, 1, !dbg !44
  store i32 %14, i32* %1, align 4, !dbg !44
  br label %2, !dbg !45, !llvm.loop !46

15:                                               ; preds = %2
  store i32 0, i32* @branch_index_1, align 4, !dbg !49
  store i32 0, i32* @branch_index_2, align 4, !dbg !50
  ret void, !dbg !51
}

; Function Attrs: nofree nosync nounwind readnone speculatable willreturn
declare void @llvm.dbg.declare(metadata, metadata, metadata) #1

; Function Attrs: noinline nounwind optnone uwtable
define dso_local i32 @hamming_weight(i32 %0, i32 %1) #0 !dbg !52 {
  %3 = alloca i32, align 4
  %4 = alloca i32, align 4
  %5 = alloca i32, align 4
  %6 = alloca i32, align 4
  %7 = alloca i32, align 4
  store i32 %0, i32* %4, align 4
  call void @llvm.dbg.declare(metadata i32* %4, metadata !55, metadata !DIExpression()), !dbg !56
  store i32 %1, i32* %5, align 4
  call void @llvm.dbg.declare(metadata i32* %5, metadata !57, metadata !DIExpression()), !dbg !58
  call void @llvm.dbg.declare(metadata i32* %6, metadata !59, metadata !DIExpression()), !dbg !60
  store i32 0, i32* %6, align 4, !dbg !60
  call void @llvm.dbg.declare(metadata i32* %7, metadata !61, metadata !DIExpression()), !dbg !63
  store i32 0, i32* %7, align 4, !dbg !63
  br label %8, !dbg !64

8:                                                ; preds = %21, %2
  %9 = load i32, i32* %7, align 4, !dbg !65
  %10 = icmp slt i32 %9, 32, !dbg !67
  br i1 %10, label %11, label %24, !dbg !68

11:                                               ; preds = %8
  %12 = load i32, i32* %4, align 4, !dbg !69
  %13 = load i32, i32* %7, align 4, !dbg !72
  %int_cast_to_i64 = zext i32 %13 to i64, !dbg !73
  call void @klee_overshift_check(i64 32, i64 %int_cast_to_i64), !dbg !73
  %14 = ashr i32 %12, %13, !dbg !73, !klee.check.shift !74
  %15 = and i32 %14, 1, !dbg !75
  %16 = icmp ne i32 %15, 0, !dbg !75
  br i1 %16, label %17, label %20, !dbg !76

17:                                               ; preds = %11
  %18 = load i32, i32* %6, align 4, !dbg !77
  %19 = add nsw i32 %18, 1, !dbg !77
  store i32 %19, i32* %6, align 4, !dbg !77
  br label %20, !dbg !79

20:                                               ; preds = %17, %11
  br label %21, !dbg !80

21:                                               ; preds = %20
  %22 = load i32, i32* %7, align 4, !dbg !81
  %23 = add nsw i32 %22, 1, !dbg !81
  store i32 %23, i32* %7, align 4, !dbg !81
  br label %8, !dbg !82, !llvm.loop !83

24:                                               ; preds = %8
  %25 = load i32, i32* %6, align 4, !dbg !85
  %26 = icmp sgt i32 %25, 16, !dbg !87
  br i1 %26, label %27, label %53, !dbg !88

27:                                               ; preds = %24
  %28 = load i32, i32* %5, align 4, !dbg !89
  %29 = icmp eq i32 %28, 1, !dbg !92
  br i1 %29, label %30, label %39, !dbg !93

30:                                               ; preds = %27
  %31 = load i32, i32* @branch_index_1, align 4, !dbg !94
  %32 = icmp slt i32 %31, 64, !dbg !95
  br i1 %32, label %33, label %39, !dbg !96

33:                                               ; preds = %30
  %34 = load i32, i32* @branch_index_1, align 4, !dbg !97
  %35 = sext i32 %34 to i64, !dbg !99
  %36 = getelementptr inbounds [64 x i32], [64 x i32]* @branch_history_1, i64 0, i64 %35, !dbg !99
  store i32 1, i32* %36, align 4, !dbg !100
  %37 = load i32, i32* @branch_index_1, align 4, !dbg !101
  %38 = add nsw i32 %37, 1, !dbg !101
  store i32 %38, i32* @branch_index_1, align 4, !dbg !101
  br label %52, !dbg !102

39:                                               ; preds = %30, %27
  %40 = load i32, i32* %5, align 4, !dbg !103
  %41 = icmp eq i32 %40, 2, !dbg !105
  br i1 %41, label %42, label %51, !dbg !106

42:                                               ; preds = %39
  %43 = load i32, i32* @branch_index_2, align 4, !dbg !107
  %44 = icmp slt i32 %43, 64, !dbg !108
  br i1 %44, label %45, label %51, !dbg !109

45:                                               ; preds = %42
  %46 = load i32, i32* @branch_index_2, align 4, !dbg !110
  %47 = sext i32 %46 to i64, !dbg !112
  %48 = getelementptr inbounds [64 x i32], [64 x i32]* @branch_history_2, i64 0, i64 %47, !dbg !112
  store i32 1, i32* %48, align 4, !dbg !113
  %49 = load i32, i32* @branch_index_2, align 4, !dbg !114
  %50 = add nsw i32 %49, 1, !dbg !114
  store i32 %50, i32* @branch_index_2, align 4, !dbg !114
  br label %51, !dbg !115

51:                                               ; preds = %45, %42, %39
  br label %52

52:                                               ; preds = %51, %33
  store i32 1, i32* %3, align 4, !dbg !116
  br label %79, !dbg !116

53:                                               ; preds = %24
  %54 = load i32, i32* %5, align 4, !dbg !117
  %55 = icmp eq i32 %54, 1, !dbg !120
  br i1 %55, label %56, label %65, !dbg !121

56:                                               ; preds = %53
  %57 = load i32, i32* @branch_index_1, align 4, !dbg !122
  %58 = icmp slt i32 %57, 64, !dbg !123
  br i1 %58, label %59, label %65, !dbg !124

59:                                               ; preds = %56
  %60 = load i32, i32* @branch_index_1, align 4, !dbg !125
  %61 = sext i32 %60 to i64, !dbg !127
  %62 = getelementptr inbounds [64 x i32], [64 x i32]* @branch_history_1, i64 0, i64 %61, !dbg !127
  store i32 0, i32* %62, align 4, !dbg !128
  %63 = load i32, i32* @branch_index_1, align 4, !dbg !129
  %64 = add nsw i32 %63, 1, !dbg !129
  store i32 %64, i32* @branch_index_1, align 4, !dbg !129
  br label %78, !dbg !130

65:                                               ; preds = %56, %53
  %66 = load i32, i32* %5, align 4, !dbg !131
  %67 = icmp eq i32 %66, 2, !dbg !133
  br i1 %67, label %68, label %77, !dbg !134

68:                                               ; preds = %65
  %69 = load i32, i32* @branch_index_2, align 4, !dbg !135
  %70 = icmp slt i32 %69, 64, !dbg !136
  br i1 %70, label %71, label %77, !dbg !137

71:                                               ; preds = %68
  %72 = load i32, i32* @branch_index_2, align 4, !dbg !138
  %73 = sext i32 %72 to i64, !dbg !140
  %74 = getelementptr inbounds [64 x i32], [64 x i32]* @branch_history_2, i64 0, i64 %73, !dbg !140
  store i32 0, i32* %74, align 4, !dbg !141
  %75 = load i32, i32* @branch_index_2, align 4, !dbg !142
  %76 = add nsw i32 %75, 1, !dbg !142
  store i32 %76, i32* @branch_index_2, align 4, !dbg !142
  br label %77, !dbg !143

77:                                               ; preds = %71, %68, %65
  br label %78

78:                                               ; preds = %77, %59
  store i32 0, i32* %3, align 4, !dbg !144
  br label %79, !dbg !144

79:                                               ; preds = %78, %52
  %80 = load i32, i32* %3, align 4, !dbg !145
  ret i32 %80, !dbg !145
}

; Function Attrs: noinline nounwind optnone uwtable
define dso_local i32 @main() #0 !dbg !146 {
  %1 = alloca i32, align 4
  %2 = alloca i32, align 4
  %3 = alloca i32, align 4
  %4 = alloca i32, align 4
  store i32 0, i32* %1, align 4
  call void @llvm.dbg.declare(metadata i32* %2, metadata !149, metadata !DIExpression()), !dbg !150
  call void @llvm.dbg.declare(metadata i32* %3, metadata !151, metadata !DIExpression()), !dbg !152
  %5 = bitcast i32* %2 to i8*, !dbg !153
  call void @klee_make_symbolic(i8* %5, i64 4, i8* getelementptr inbounds ([8 x i8], [8 x i8]* @.str, i64 0, i64 0)), !dbg !154
  %6 = load i32, i32* %2, align 4, !dbg !155
  %7 = icmp sge i32 %6, 0, !dbg !156
  %8 = zext i1 %7 to i32, !dbg !156
  %9 = sext i32 %8 to i64, !dbg !155
  call void @klee_assume(i64 %9), !dbg !157
  %10 = load i32, i32* %2, align 4, !dbg !158
  %11 = icmp slt i32 %10, 256, !dbg !159
  %12 = zext i1 %11 to i32, !dbg !159
  %13 = sext i32 %12 to i64, !dbg !158
  call void @klee_assume(i64 %13), !dbg !160
  %14 = bitcast i32* %3 to i8*, !dbg !161
  call void @klee_make_symbolic(i8* %14, i64 4, i8* getelementptr inbounds ([8 x i8], [8 x i8]* @.str.1, i64 0, i64 0)), !dbg !162
  %15 = load i32, i32* %3, align 4, !dbg !163
  %16 = icmp sge i32 %15, 0, !dbg !164
  %17 = zext i1 %16 to i32, !dbg !164
  %18 = sext i32 %17 to i64, !dbg !163
  call void @klee_assume(i64 %18), !dbg !165
  %19 = load i32, i32* %3, align 4, !dbg !166
  %20 = icmp slt i32 %19, 256, !dbg !167
  %21 = zext i1 %20 to i32, !dbg !167
  %22 = sext i32 %21 to i64, !dbg !166
  call void @klee_assume(i64 %22), !dbg !168
  %23 = load i32, i32* %2, align 4, !dbg !169
  %24 = load i32, i32* %3, align 4, !dbg !170
  %25 = icmp ne i32 %23, %24, !dbg !171
  %26 = zext i1 %25 to i32, !dbg !171
  %27 = sext i32 %26 to i64, !dbg !169
  call void @klee_assume(i64 %27), !dbg !172
  call void @reset_globals(), !dbg !173
  %28 = load i32, i32* %2, align 4, !dbg !174
  %29 = call i32 @hamming_weight(i32 %28, i32 1), !dbg !175
  %30 = load i32, i32* %3, align 4, !dbg !176
  %31 = call i32 @hamming_weight(i32 %30, i32 2), !dbg !177
  call void @llvm.dbg.declare(metadata i32* %4, metadata !178, metadata !DIExpression()), !dbg !180
  store i32 0, i32* %4, align 4, !dbg !180
  br label %32, !dbg !181

32:                                               ; preds = %48, %0
  %33 = load i32, i32* %4, align 4, !dbg !182
  %34 = icmp slt i32 %33, 64, !dbg !184
  br i1 %34, label %35, label %51, !dbg !185

35:                                               ; preds = %32
  %36 = load i32, i32* %4, align 4, !dbg !186
  %37 = sext i32 %36 to i64, !dbg !186
  %38 = getelementptr inbounds [64 x i32], [64 x i32]* @branch_history_1, i64 0, i64 %37, !dbg !186
  %39 = load i32, i32* %38, align 4, !dbg !186
  %40 = load i32, i32* %4, align 4, !dbg !186
  %41 = sext i32 %40 to i64, !dbg !186
  %42 = getelementptr inbounds [64 x i32], [64 x i32]* @branch_history_2, i64 0, i64 %41, !dbg !186
  %43 = load i32, i32* %42, align 4, !dbg !186
  %44 = icmp eq i32 %39, %43, !dbg !186
  br i1 %44, label %45, label %46, !dbg !190

45:                                               ; preds = %35
  br label %47, !dbg !190

46:                                               ; preds = %35
  call void @__assert_fail(i8* getelementptr inbounds ([43 x i8], [43 x i8]* @.str.2, i64 0, i64 0), i8* getelementptr inbounds ([57 x i8], [57 x i8]* @.str.3, i64 0, i64 0), i32 73, i8* getelementptr inbounds ([11 x i8], [11 x i8]* @__PRETTY_FUNCTION__.main, i64 0, i64 0)) #6, !dbg !186
  unreachable, !dbg !186

47:                                               ; preds = %45
  br label %48, !dbg !191

48:                                               ; preds = %47
  %49 = load i32, i32* %4, align 4, !dbg !192
  %50 = add nsw i32 %49, 1, !dbg !192
  store i32 %50, i32* %4, align 4, !dbg !192
  br label %32, !dbg !193, !llvm.loop !194

51:                                               ; preds = %32
  ret i32 0, !dbg !196
}

declare dso_local void @klee_make_symbolic(i8*, i64, i8*) #2

declare dso_local void @klee_assume(i64) #2

; Function Attrs: noreturn nounwind
declare dso_local void @__assert_fail(i8*, i8*, i32, i8*) #3

; Function Attrs: noinline nounwind uwtable
define dso_local void @klee_overshift_check(i64 %0, i64 %1) #4 !dbg !197 {
  %3 = alloca i64, align 8
  %4 = alloca i64, align 8
  store i64 %0, i64* %3, align 8
  call void @llvm.dbg.declare(metadata i64* %3, metadata !202, metadata !DIExpression()), !dbg !203
  store i64 %1, i64* %4, align 8
  call void @llvm.dbg.declare(metadata i64* %4, metadata !204, metadata !DIExpression()), !dbg !205
  %5 = load i64, i64* %4, align 8, !dbg !206
  %6 = load i64, i64* %3, align 8, !dbg !208
  %7 = icmp uge i64 %5, %6, !dbg !209
  br i1 %7, label %8, label %9, !dbg !210

8:                                                ; preds = %2
  call void @klee_report_error(i8* getelementptr inbounds ([8 x i8], [8 x i8]* @.str.4, i64 0, i64 0), i32 0, i8* getelementptr inbounds ([16 x i8], [16 x i8]* @.str.1.5, i64 0, i64 0), i8* getelementptr inbounds ([14 x i8], [14 x i8]* @.str.2.6, i64 0, i64 0)) #7, !dbg !211
  unreachable, !dbg !211

9:                                                ; preds = %2
  ret void, !dbg !213
}

; Function Attrs: noreturn
declare dso_local void @klee_report_error(i8*, i32, i8*, i8*) #5

attributes #0 = { noinline nounwind optnone uwtable "frame-pointer"="all" "min-legal-vector-width"="0" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #1 = { nofree nosync nounwind readnone speculatable willreturn }
attributes #2 = { "frame-pointer"="all" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #3 = { noreturn nounwind "frame-pointer"="all" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #4 = { noinline nounwind uwtable "frame-pointer"="all" "min-legal-vector-width"="0" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #5 = { noreturn "frame-pointer"="all" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #6 = { noreturn nounwind }
attributes #7 = { noreturn }

!llvm.dbg.cu = !{!2, !17}
!llvm.module.flags = !{!19, !20, !21, !22, !23}
!llvm.ident = !{!24, !24}

!0 = !DIGlobalVariableExpression(var: !1, expr: !DIExpression())
!1 = distinct !DIGlobalVariable(name: "branch_index_1", scope: !2, file: !8, line: 14, type: !9, isLocal: false, isDefinition: true)
!2 = distinct !DICompileUnit(language: DW_LANG_C99, file: !3, producer: "Ubuntu clang version 13.0.1-2ubuntu2.2", isOptimized: false, runtimeVersion: 0, emissionKind: FullDebug, enums: !4, globals: !5, splitDebugInlining: false, nameTableKind: None)
!3 = !DIFile(filename: "/home/james/klee-deps/testKLEE/target-branch-log/test3.c", directory: "/home/james/klee-deps/testKLEE")
!4 = !{}
!5 = !{!0, !6, !10, !15}
!6 = !DIGlobalVariableExpression(var: !7, expr: !DIExpression())
!7 = distinct !DIGlobalVariable(name: "branch_index_2", scope: !2, file: !8, line: 15, type: !9, isLocal: false, isDefinition: true)
!8 = !DIFile(filename: "target-branch-log/test3.c", directory: "/home/james/klee-deps/testKLEE")
!9 = !DIBasicType(name: "int", size: 32, encoding: DW_ATE_signed)
!10 = !DIGlobalVariableExpression(var: !11, expr: !DIExpression())
!11 = distinct !DIGlobalVariable(name: "branch_history_1", scope: !2, file: !8, line: 12, type: !12, isLocal: false, isDefinition: true)
!12 = !DICompositeType(tag: DW_TAG_array_type, baseType: !9, size: 2048, elements: !13)
!13 = !{!14}
!14 = !DISubrange(count: 64)
!15 = !DIGlobalVariableExpression(var: !16, expr: !DIExpression())
!16 = distinct !DIGlobalVariable(name: "branch_history_2", scope: !2, file: !8, line: 13, type: !12, isLocal: false, isDefinition: true)
!17 = distinct !DICompileUnit(language: DW_LANG_C89, file: !18, producer: "Ubuntu clang version 13.0.1-2ubuntu2.2", isOptimized: false, runtimeVersion: 0, emissionKind: FullDebug, enums: !4, splitDebugInlining: false, nameTableKind: None)
!18 = !DIFile(filename: "/home/james/klee-deps/klee-controlflow/runtime/Intrinsic/klee_overshift_check.c", directory: "/home/james/klee-deps/klee-controlflow/build/runtime/Intrinsic")
!19 = !{i32 7, !"Dwarf Version", i32 4}
!20 = !{i32 2, !"Debug Info Version", i32 3}
!21 = !{i32 1, !"wchar_size", i32 4}
!22 = !{i32 7, !"uwtable", i32 1}
!23 = !{i32 7, !"frame-pointer", i32 2}
!24 = !{!"Ubuntu clang version 13.0.1-2ubuntu2.2"}
!25 = distinct !DISubprogram(name: "reset_globals", scope: !8, file: !8, line: 18, type: !26, scopeLine: 18, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !4)
!26 = !DISubroutineType(types: !27)
!27 = !{null}
!28 = !DILocalVariable(name: "i", scope: !29, file: !8, line: 19, type: !9)
!29 = distinct !DILexicalBlock(scope: !25, file: !8, line: 19, column: 5)
!30 = !DILocation(line: 19, column: 14, scope: !29)
!31 = !DILocation(line: 19, column: 10, scope: !29)
!32 = !DILocation(line: 19, column: 21, scope: !33)
!33 = distinct !DILexicalBlock(scope: !29, file: !8, line: 19, column: 5)
!34 = !DILocation(line: 19, column: 23, scope: !33)
!35 = !DILocation(line: 19, column: 5, scope: !29)
!36 = !DILocation(line: 20, column: 26, scope: !37)
!37 = distinct !DILexicalBlock(scope: !33, file: !8, line: 19, column: 49)
!38 = !DILocation(line: 20, column: 9, scope: !37)
!39 = !DILocation(line: 20, column: 29, scope: !37)
!40 = !DILocation(line: 21, column: 26, scope: !37)
!41 = !DILocation(line: 21, column: 9, scope: !37)
!42 = !DILocation(line: 21, column: 29, scope: !37)
!43 = !DILocation(line: 22, column: 5, scope: !37)
!44 = !DILocation(line: 19, column: 45, scope: !33)
!45 = !DILocation(line: 19, column: 5, scope: !33)
!46 = distinct !{!46, !35, !47, !48}
!47 = !DILocation(line: 22, column: 5, scope: !29)
!48 = !{!"llvm.loop.mustprogress"}
!49 = !DILocation(line: 23, column: 20, scope: !25)
!50 = !DILocation(line: 24, column: 20, scope: !25)
!51 = !DILocation(line: 25, column: 1, scope: !25)
!52 = distinct !DISubprogram(name: "hamming_weight", scope: !8, file: !8, line: 28, type: !53, scopeLine: 28, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !4)
!53 = !DISubroutineType(types: !54)
!54 = !{!9, !9, !9}
!55 = !DILocalVariable(name: "secret", arg: 1, scope: !52, file: !8, line: 28, type: !9)
!56 = !DILocation(line: 28, column: 24, scope: !52)
!57 = !DILocalVariable(name: "run", arg: 2, scope: !52, file: !8, line: 28, type: !9)
!58 = !DILocation(line: 28, column: 36, scope: !52)
!59 = !DILocalVariable(name: "weight", scope: !52, file: !8, line: 29, type: !9)
!60 = !DILocation(line: 29, column: 9, scope: !52)
!61 = !DILocalVariable(name: "i", scope: !62, file: !8, line: 30, type: !9)
!62 = distinct !DILexicalBlock(scope: !52, file: !8, line: 30, column: 5)
!63 = !DILocation(line: 30, column: 14, scope: !62)
!64 = !DILocation(line: 30, column: 10, scope: !62)
!65 = !DILocation(line: 30, column: 21, scope: !66)
!66 = distinct !DILexicalBlock(scope: !62, file: !8, line: 30, column: 5)
!67 = !DILocation(line: 30, column: 23, scope: !66)
!68 = !DILocation(line: 30, column: 5, scope: !62)
!69 = !DILocation(line: 31, column: 14, scope: !70)
!70 = distinct !DILexicalBlock(scope: !71, file: !8, line: 31, column: 13)
!71 = distinct !DILexicalBlock(scope: !66, file: !8, line: 30, column: 34)
!72 = !DILocation(line: 31, column: 24, scope: !70)
!73 = !DILocation(line: 31, column: 21, scope: !70)
!74 = !{!"True"}
!75 = !DILocation(line: 31, column: 27, scope: !70)
!76 = !DILocation(line: 31, column: 13, scope: !71)
!77 = !DILocation(line: 32, column: 19, scope: !78)
!78 = distinct !DILexicalBlock(scope: !70, file: !8, line: 31, column: 32)
!79 = !DILocation(line: 33, column: 9, scope: !78)
!80 = !DILocation(line: 34, column: 5, scope: !71)
!81 = !DILocation(line: 30, column: 30, scope: !66)
!82 = !DILocation(line: 30, column: 5, scope: !66)
!83 = distinct !{!83, !68, !84, !48}
!84 = !DILocation(line: 34, column: 5, scope: !62)
!85 = !DILocation(line: 35, column: 9, scope: !86)
!86 = distinct !DILexicalBlock(scope: !52, file: !8, line: 35, column: 9)
!87 = !DILocation(line: 35, column: 16, scope: !86)
!88 = !DILocation(line: 35, column: 9, scope: !52)
!89 = !DILocation(line: 36, column: 13, scope: !90)
!90 = distinct !DILexicalBlock(scope: !91, file: !8, line: 36, column: 13)
!91 = distinct !DILexicalBlock(scope: !86, file: !8, line: 35, column: 22)
!92 = !DILocation(line: 36, column: 17, scope: !90)
!93 = !DILocation(line: 36, column: 22, scope: !90)
!94 = !DILocation(line: 36, column: 25, scope: !90)
!95 = !DILocation(line: 36, column: 40, scope: !90)
!96 = !DILocation(line: 36, column: 13, scope: !91)
!97 = !DILocation(line: 37, column: 30, scope: !98)
!98 = distinct !DILexicalBlock(scope: !90, file: !8, line: 36, column: 61)
!99 = !DILocation(line: 37, column: 13, scope: !98)
!100 = !DILocation(line: 37, column: 46, scope: !98)
!101 = !DILocation(line: 38, column: 27, scope: !98)
!102 = !DILocation(line: 39, column: 9, scope: !98)
!103 = !DILocation(line: 39, column: 20, scope: !104)
!104 = distinct !DILexicalBlock(scope: !90, file: !8, line: 39, column: 20)
!105 = !DILocation(line: 39, column: 24, scope: !104)
!106 = !DILocation(line: 39, column: 29, scope: !104)
!107 = !DILocation(line: 39, column: 32, scope: !104)
!108 = !DILocation(line: 39, column: 47, scope: !104)
!109 = !DILocation(line: 39, column: 20, scope: !90)
!110 = !DILocation(line: 40, column: 30, scope: !111)
!111 = distinct !DILexicalBlock(scope: !104, file: !8, line: 39, column: 68)
!112 = !DILocation(line: 40, column: 13, scope: !111)
!113 = !DILocation(line: 40, column: 46, scope: !111)
!114 = !DILocation(line: 41, column: 27, scope: !111)
!115 = !DILocation(line: 42, column: 9, scope: !111)
!116 = !DILocation(line: 43, column: 9, scope: !91)
!117 = !DILocation(line: 45, column: 13, scope: !118)
!118 = distinct !DILexicalBlock(scope: !119, file: !8, line: 45, column: 13)
!119 = distinct !DILexicalBlock(scope: !86, file: !8, line: 44, column: 12)
!120 = !DILocation(line: 45, column: 17, scope: !118)
!121 = !DILocation(line: 45, column: 22, scope: !118)
!122 = !DILocation(line: 45, column: 25, scope: !118)
!123 = !DILocation(line: 45, column: 40, scope: !118)
!124 = !DILocation(line: 45, column: 13, scope: !119)
!125 = !DILocation(line: 46, column: 30, scope: !126)
!126 = distinct !DILexicalBlock(scope: !118, file: !8, line: 45, column: 61)
!127 = !DILocation(line: 46, column: 13, scope: !126)
!128 = !DILocation(line: 46, column: 46, scope: !126)
!129 = !DILocation(line: 47, column: 27, scope: !126)
!130 = !DILocation(line: 48, column: 9, scope: !126)
!131 = !DILocation(line: 48, column: 20, scope: !132)
!132 = distinct !DILexicalBlock(scope: !118, file: !8, line: 48, column: 20)
!133 = !DILocation(line: 48, column: 24, scope: !132)
!134 = !DILocation(line: 48, column: 29, scope: !132)
!135 = !DILocation(line: 48, column: 32, scope: !132)
!136 = !DILocation(line: 48, column: 47, scope: !132)
!137 = !DILocation(line: 48, column: 20, scope: !118)
!138 = !DILocation(line: 49, column: 30, scope: !139)
!139 = distinct !DILexicalBlock(scope: !132, file: !8, line: 48, column: 68)
!140 = !DILocation(line: 49, column: 13, scope: !139)
!141 = !DILocation(line: 49, column: 46, scope: !139)
!142 = !DILocation(line: 50, column: 27, scope: !139)
!143 = !DILocation(line: 51, column: 9, scope: !139)
!144 = !DILocation(line: 52, column: 9, scope: !119)
!145 = !DILocation(line: 54, column: 1, scope: !52)
!146 = distinct !DISubprogram(name: "main", scope: !8, file: !8, line: 57, type: !147, scopeLine: 57, spFlags: DISPFlagDefinition, unit: !2, retainedNodes: !4)
!147 = !DISubroutineType(types: !148)
!148 = !{!9}
!149 = !DILocalVariable(name: "secret1", scope: !146, file: !8, line: 58, type: !9)
!150 = !DILocation(line: 58, column: 9, scope: !146)
!151 = !DILocalVariable(name: "secret2", scope: !146, file: !8, line: 58, type: !9)
!152 = !DILocation(line: 58, column: 18, scope: !146)
!153 = !DILocation(line: 60, column: 24, scope: !146)
!154 = !DILocation(line: 60, column: 5, scope: !146)
!155 = !DILocation(line: 61, column: 17, scope: !146)
!156 = !DILocation(line: 61, column: 25, scope: !146)
!157 = !DILocation(line: 61, column: 5, scope: !146)
!158 = !DILocation(line: 62, column: 17, scope: !146)
!159 = !DILocation(line: 62, column: 25, scope: !146)
!160 = !DILocation(line: 62, column: 5, scope: !146)
!161 = !DILocation(line: 63, column: 24, scope: !146)
!162 = !DILocation(line: 63, column: 5, scope: !146)
!163 = !DILocation(line: 64, column: 17, scope: !146)
!164 = !DILocation(line: 64, column: 25, scope: !146)
!165 = !DILocation(line: 64, column: 5, scope: !146)
!166 = !DILocation(line: 65, column: 17, scope: !146)
!167 = !DILocation(line: 65, column: 25, scope: !146)
!168 = !DILocation(line: 65, column: 5, scope: !146)
!169 = !DILocation(line: 66, column: 17, scope: !146)
!170 = !DILocation(line: 66, column: 28, scope: !146)
!171 = !DILocation(line: 66, column: 25, scope: !146)
!172 = !DILocation(line: 66, column: 5, scope: !146)
!173 = !DILocation(line: 68, column: 5, scope: !146)
!174 = !DILocation(line: 69, column: 20, scope: !146)
!175 = !DILocation(line: 69, column: 5, scope: !146)
!176 = !DILocation(line: 70, column: 20, scope: !146)
!177 = !DILocation(line: 70, column: 5, scope: !146)
!178 = !DILocalVariable(name: "i", scope: !179, file: !8, line: 72, type: !9)
!179 = distinct !DILexicalBlock(scope: !146, file: !8, line: 72, column: 5)
!180 = !DILocation(line: 72, column: 14, scope: !179)
!181 = !DILocation(line: 72, column: 10, scope: !179)
!182 = !DILocation(line: 72, column: 21, scope: !183)
!183 = distinct !DILexicalBlock(scope: !179, file: !8, line: 72, column: 5)
!184 = !DILocation(line: 72, column: 23, scope: !183)
!185 = !DILocation(line: 72, column: 5, scope: !179)
!186 = !DILocation(line: 73, column: 9, scope: !187)
!187 = distinct !DILexicalBlock(scope: !188, file: !8, line: 73, column: 9)
!188 = distinct !DILexicalBlock(scope: !189, file: !8, line: 73, column: 9)
!189 = distinct !DILexicalBlock(scope: !183, file: !8, line: 72, column: 49)
!190 = !DILocation(line: 73, column: 9, scope: !188)
!191 = !DILocation(line: 74, column: 5, scope: !189)
!192 = !DILocation(line: 72, column: 45, scope: !183)
!193 = !DILocation(line: 72, column: 5, scope: !183)
!194 = distinct !{!194, !185, !195, !48}
!195 = !DILocation(line: 74, column: 5, scope: !179)
!196 = !DILocation(line: 76, column: 5, scope: !146)
!197 = distinct !DISubprogram(name: "klee_overshift_check", scope: !198, file: !198, line: 20, type: !199, scopeLine: 20, flags: DIFlagPrototyped, spFlags: DISPFlagDefinition, unit: !17, retainedNodes: !4)
!198 = !DIFile(filename: "runtime/Intrinsic/klee_overshift_check.c", directory: "/home/james/klee-deps/klee-controlflow")
!199 = !DISubroutineType(types: !200)
!200 = !{null, !201, !201}
!201 = !DIBasicType(name: "long long unsigned int", size: 64, encoding: DW_ATE_unsigned)
!202 = !DILocalVariable(name: "bitWidth", arg: 1, scope: !197, file: !198, line: 20, type: !201)
!203 = !DILocation(line: 20, column: 46, scope: !197)
!204 = !DILocalVariable(name: "shift", arg: 2, scope: !197, file: !198, line: 20, type: !201)
!205 = !DILocation(line: 20, column: 75, scope: !197)
!206 = !DILocation(line: 21, column: 7, scope: !207)
!207 = distinct !DILexicalBlock(scope: !197, file: !198, line: 21, column: 7)
!208 = !DILocation(line: 21, column: 16, scope: !207)
!209 = !DILocation(line: 21, column: 13, scope: !207)
!210 = !DILocation(line: 21, column: 7, scope: !197)
!211 = !DILocation(line: 27, column: 5, scope: !212)
!212 = distinct !DILexicalBlock(scope: !207, file: !198, line: 21, column: 26)
!213 = !DILocation(line: 29, column: 1, scope: !197)
