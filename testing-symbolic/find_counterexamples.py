"""
Author: Jameson DiPalma
Works for functions with strictly integer inputs, such as test1.c in this directory
"""

import os
import subprocess
import shutil
import sys

KLEE_BIN = os.path.expanduser("~/klee-deps/klee-controlflow/build/bin/klee")
KTEST_TOOL = "ktest-tool"

MAX_TESTS = "1000"
MAX_DEPTH = "1000"
MAX_TIME = "60"
DEBUG = True


def build_with_make(c_filename):
    test_name = c_filename.replace(".c", "")
    klee_out_dir = os.path.abspath("klee-out-0")
    if os.path.exists(klee_out_dir):
        shutil.rmtree(klee_out_dir)

    print(f"Building with make TEST={test_name}...")
    result = subprocess.run(["make", f"TEST={test_name}"])
    if result.returncode != 0:
        print("Make failed.")
        sys.exit(1)

    bc_path = os.path.abspath(f"{test_name}.bc")
    if not os.path.exists(bc_path):
        print(f"Expected bitcode file {bc_path} not found after make.")
        sys.exit(1)

    return bc_path, klee_out_dir


def run_klee(bc_file_path, klee_out_dir):
    print(f"Running KLEE with output dir {klee_out_dir}...")
    klee_cmd = [
        KLEE_BIN,
        f"--output-dir={klee_out_dir}",
        f"--max-tests={MAX_TESTS}",
        f"--max-depth={MAX_DEPTH}",
        f"--max-time={MAX_TIME}",
        "--search=nurs:covnew",
        "--search=dfs",
        bc_file_path
    ]
    try:
        subprocess.run(klee_cmd, check=True)
    except subprocess.CalledProcessError as e:
        print("KLEE execution failed.")
        sys.exit(1)
    print("KLEE run complete")


def detect_assert_failures(klee_out_dir):
    for f in os.listdir(klee_out_dir):
        if f.endswith(".err") and "assert" in f:
            return True
    return False


def extract_ktest_inputs(ktest_file):
    result = subprocess.run([KTEST_TOOL, ktest_file], capture_output=True, text=True)
    inputs = {}
    current_name = None

    for line in result.stdout.splitlines():
        if "object" in line and "name:" in line:
            current_name = line.split("name:")[1].strip().strip("'\"")
        elif "data:" in line and current_name:
            try:
                data = line.split("data:")[1].strip()
                bytes_list = eval(data)
                val = int.from_bytes(bytes(bytes_list), byteorder='little', signed=True)
                inputs[current_name] = val
            except Exception:
                pass
            current_name = None

    return inputs


def show_first_counterexample(klee_out_dir):
    for f in sorted(os.listdir(klee_out_dir)):
        if f.endswith(".ktest"):
            print(f"\nCounterexample in {f}:")
            ktest_path = os.path.join(klee_out_dir, f)
            inputs = extract_ktest_inputs(ktest_path)
            for var, val in inputs.items():
                print(f"  {var} = {val}")
            print("-" * 40)
            return


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 find_counterexamples.py <testX.c>")
        return

    c_filename = sys.argv[1]
    if not c_filename.endswith(".c"):
        print("Please provide a .c file.")
        return

    bc_path, klee_out_dir = build_with_make(c_filename)
    run_klee(bc_path, klee_out_dir)

    if detect_assert_failures(klee_out_dir):
        print("\nControl-flow leak detected (assert failed).")
        show_first_counterexample(klee_out_dir)
    else:
        print("\nNo control-flow leak detected (assert passed).")


if __name__ == "__main__":
    main()
