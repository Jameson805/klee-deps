"""
Author: Jameson DiPalma
"""

import os
import subprocess
import shutil
import json
import sys

KLEE_BIN = os.path.expanduser("~/klee-deps/klee-controlflow/build/bin/klee")
INCLUDE_PATH = os.path.expanduser("~/klee-deps/klee-controlflow/include")
KTEST_TOOL = "ktest-tool"

BASE_DIR = "/home/james/klee-deps/testKLEE"
OUTPUT_DIR = "constrained-cases"
ORIGINAL_KLEE_DIR = "klee-out-0"
CONSTRAINED_KLEE_DIR = os.path.join(OUTPUT_DIR, "klee-out-0")

MAX_TESTS = "1000"
DEBUG = False


def parse_metadata(c_file_path):
    variables = []
    public_vars = []
    target_branch = None

    with open(c_file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith("// VARS:"):
                variables = [v.strip() for v in line.split(":")[1].split(",")]
            elif line.startswith("// PUBLIC:"):
                public_vars = [v.strip() for v in line.split(":")[1].split(",")]
            elif line.startswith("// KLEE_TARGET_BRANCH_LINE:"):
                target_branch = int(line.split(":")[1].strip())
            if variables and public_vars and target_branch is not None:
                break

    if not variables or target_branch is None:
        raise ValueError("Missing metadata in test file.")

    return variables, public_vars, target_branch


def compile_and_run_klee(c_file_path, output_dir, write_paths=False):
    bc_file_path = c_file_path.replace(".c", ".bc")

    if os.path.exists(bc_file_path):
        os.remove(bc_file_path)
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)

    clang_cmd = [
        "clang-13", "-I", INCLUDE_PATH,
        "-emit-llvm", "-c", "-g",
        c_file_path,
        "-o", bc_file_path
    ]
    print(f"\nCompiling {os.path.relpath(c_file_path, BASE_DIR)} to {os.path.relpath(bc_file_path, BASE_DIR)}...")
    subprocess.run(clang_cmd, check=True)

    print(f"Running KLEE with output dir {os.path.relpath(output_dir, BASE_DIR)}...")
    klee_cmd = [KLEE_BIN, "--output-dir=" + output_dir, "--max-tests=" + MAX_TESTS]
    
    if write_paths:
        klee_cmd.append("--write-paths")
    klee_cmd.append(bc_file_path)

    if DEBUG:
        subprocess.run(klee_cmd, check=True)
    else:
        subprocess.run(klee_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    
    print("KLEE run complete")
    if os.path.exists(bc_file_path):
        os.remove(bc_file_path)


def extract_ktest_inputs(test_id, klee_dir):
    ktest_path = os.path.join(klee_dir, test_id + ".ktest")
    if not os.path.exists(ktest_path):
        return None

    result = subprocess.run([KTEST_TOOL, ktest_path], capture_output=True, text=True)
    inputs = {}
    current_name = None
    for line in result.stdout.splitlines():
        if "object" in line and "name:" in line:
            current_name = line.split("name:")[1].strip().strip('\'"')
        elif "data:" in line and current_name:
            data = line.split("data:")[1].strip()
            try:
                bytes_list = eval(data)
                if len(bytes_list) == 4:
                    val = int.from_bytes(bytes(bytes_list), byteorder='little', signed=True)
                    inputs[current_name] = val
            except Exception:
                pass
            current_name = None
    return inputs


def find_branch_tests(klee_dir, expected_file, target_branch):
    true_tests = []
    false_tests = []

    ktest_files = sorted([f for f in os.listdir(klee_dir) if f.endswith(".ktest")])
    for fname in ktest_files:
        test_id = fname.replace(".ktest", "")
        json_path = os.path.join(klee_dir, test_id + ".json")

        if not os.path.exists(json_path):
            continue

        try:
            with open(json_path, "r") as f:
                trace = json.load(f).get("controlFlowTrace", [])
        except:
            continue

        for entry in trace:
            if entry.get("line") == target_branch and os.path.basename(entry.get("filename", "")) == os.path.basename(expected_file):
                if entry.get("taken") is True:
                    true_tests.append(test_id)
                elif entry.get("taken") is False:
                    false_tests.append(test_id)
                break

    if DEBUG:
        print(f"\nTrue Branch Paths ({len(true_tests)}):")
        for tid in true_tests:
            print(f"  {tid}: {extract_ktest_inputs(tid, klee_dir)}")
        print(f"\nFalse Branch Paths ({len(false_tests)}):")
        for tid in false_tests:
            print(f"  {tid}: {extract_ktest_inputs(tid, klee_dir)}")
    else:
        print(f"\nNumber of True Branch Paths: {len(true_tests)}")
        print(f"\nNumber of False Branch Paths: {len(false_tests)}")

    return true_tests, false_tests


def create_constrained_file(test_id, label, var_list, public_vars, target_c_path):
    inputs = extract_ktest_inputs(test_id, ORIGINAL_KLEE_DIR)
    if not inputs:
        print(f"Skipping {test_id}: no inputs found.")
        return None

    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(target_c_path, 'r') as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        new_lines.append(line)
        if "klee_make_symbolic" in line:
            for var in public_vars:
                if var in line and var in inputs:
                    new_lines.append(f"    klee_assume({var} == {inputs[var]});\n")

    out_filename = f"target_{label}_{test_id}.c"
    out_path = os.path.join(OUTPUT_DIR, out_filename)
    with open(out_path, 'w') as out_f:
        out_f.writelines(new_lines)

    print(f"Wrote constrained test: {out_filename}")
    return out_path


def detect_control_flow_leak_for_tests(test_ids, label, vars_list, public_vars, target_branch, original_c_path):
    for test_id in test_ids:
        constrained_file = create_constrained_file(test_id, label, vars_list, public_vars, original_c_path)
        if constrained_file is None:
            continue

        print(f"\nTesting {os.path.relpath(constrained_file, BASE_DIR)}...")
        compile_and_run_klee(constrained_file, output_dir=CONSTRAINED_KLEE_DIR, write_paths=True)

        path_files = sorted([
            os.path.join(CONSTRAINED_KLEE_DIR, f)
            for f in os.listdir(CONSTRAINED_KLEE_DIR)
            if f.endswith(".path")
        ])

        if len(path_files) < 2:
            print("Only one path generated — no leak detected.")
            continue

        with open(path_files[0], 'rb') as f:
            ref = f.read()

        for pf in path_files[1:]:
            with open(pf, 'rb') as f:
                if f.read() != ref:
                    base1 = os.path.splitext(os.path.basename(path_files[0]))[0]
                    base2 = os.path.splitext(os.path.basename(pf))[0]

                    i1 = extract_ktest_inputs(base1, CONSTRAINED_KLEE_DIR)
                    i2 = extract_ktest_inputs(base2, CONSTRAINED_KLEE_DIR)

                    print("\nCONTROL-FLOW LEAK DETECTED!")
                    for var in public_vars:
                        print(f"  Public input ({var}) = {i1.get(var)}")
                    for var in vars_list:
                        if var not in public_vars:
                            print(f"  Secret values: {var} -> {i1.get(var)} vs {i2.get(var)}")
                    return True

        print("All path files identical — no leak detected.")
    return False


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 find_counterexamples.py <C_FILE>")
        sys.exit(1)

    c_file = sys.argv[1]
    c_file_path = os.path.join(BASE_DIR, c_file)

    vars_list, public_vars, target_branch = parse_metadata(c_file_path)
    compile_and_run_klee(c_file_path, output_dir=ORIGINAL_KLEE_DIR)

    true_tests, false_tests = find_branch_tests(ORIGINAL_KLEE_DIR, c_file, target_branch)

    print("\n==============================")
    print("Checking for control-flow leaks...")
    print("==============================")

    if detect_control_flow_leak_for_tests(true_tests, "true", vars_list, public_vars, target_branch, c_file_path):
        return
    if detect_control_flow_leak_for_tests(false_tests, "false", vars_list, public_vars, target_branch, c_file_path):
        return

    print("\nNo control-flow leak detected after checking all constrained inputs.")


if __name__ == "__main__":
    main()
