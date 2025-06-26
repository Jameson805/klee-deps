"""
Author: Jameson DiPalma
"""

import os
import subprocess
import shutil
import json

KLEE_BIN = os.path.expanduser("~/klee-deps/klee-controlflow/build/bin/klee")
INCLUDE_PATH = os.path.expanduser("~/klee-deps/klee-controlflow/include")
KTEST_TOOL = "ktest-tool"

TARGET_C_FILE = "tests/test1.c"
TARGET_BRANCH = 17
BASE_DIR = "/mnt/c/Users/james/OneDrive/Documents/College Classes/CS+ Semester/TestKLEE"
PUBLIC_VARS = ["pub"]

OUTPUT_DIR = "constrained-cases"
ORIGINAL_KLEE_DIR = "klee-out-0"
CONSTRAINED_KLEE_DIR = os.path.join(OUTPUT_DIR, "klee-out-0")

DEBUG = False


def compile_and_run_klee(c_file_path, output_dir):
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
    print(f"Compiling {c_file_path} to {bc_file_path}...")
    subprocess.run(clang_cmd, check=True)

    print(f"Running KLEE on {bc_file_path} with output dir {output_dir}...")
    subprocess.run(
        [KLEE_BIN, "--output-dir=" + output_dir, bc_file_path],
        check=True
    )
    print("KLEE run complete")


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


def find_branch_tests(klee_dir):
    true_tests = []
    false_tests = []

    ktest_files = sorted([f for f in os.listdir(klee_dir) if f.endswith(".ktest")])

    for fname in ktest_files:
        test_id = fname.replace(".ktest", "")
        json_path = os.path.join(klee_dir, test_id + ".json")

        if not os.path.exists(json_path):
            print(f"Warning: Missing JSON for {test_id}")
            continue

        try:
            with open(json_path, "r") as f:
                trace = json.load(f).get("controlFlowTrace", [])
        except Exception as e:
            print(f"Error parsing {json_path}: {e}")
            continue

        found = False
        for entry in trace:
            if entry.get("filename") == TARGET_C_FILE and entry.get("line") == TARGET_BRANCH:
                taken = entry.get("taken")
                if taken is True:
                    true_tests.append(test_id)
                elif taken is False:
                    false_tests.append(test_id)
                found = True
                break

        if not found:
            print(f"Warning: No matching branch info for {test_id} at line {TARGET_BRANCH}")

    return true_tests, false_tests


def print_results(label, test_ids, klee_dir):
    print(f"\n{label} Branches ({len(test_ids)} paths):")
    for tid in test_ids:
        inputs = extract_ktest_inputs(tid, klee_dir)
        if inputs is not None:
            formatted_inputs = ", ".join(f"{k}: {v}" for k, v in inputs.items())
            print(f"{tid}.ktest: {formatted_inputs}")
        else:
            print(f"{tid}.ktest: (inputs not found)")


def create_constrained_file(test_id, label):
    inputs = extract_ktest_inputs(test_id, ORIGINAL_KLEE_DIR)
    if not inputs:
        print(f"Skipping {test_id}: no inputs found.")
        return None

    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(os.path.join(BASE_DIR, TARGET_C_FILE), 'r') as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        new_lines.append(line)
        if "klee_make_symbolic" in line:
            try:
                name = line.split(',')[-1].strip().strip('); \n"')
                if name in PUBLIC_VARS and name in inputs:
                    val = inputs[name]
                    new_lines.append(f"    klee_assume({name} == {val});\n")
            except Exception as e:
                print(f"Failed to parse line: {line.strip()} — {e}")

    out_filename = f"target_{label}_{test_id}.c"
    out_path = os.path.join(OUTPUT_DIR, out_filename)
    with open(out_path, 'w') as out_f:
        out_f.writelines(new_lines)

    print(f"Wrote {out_filename}")
    return out_path


def detect_control_flow_leak_for_tests(test_ids, label):
    for test_id in test_ids:
        constrained_file = create_constrained_file(test_id, label)
        if constrained_file is None:
            continue
        print(f"\nTesting {constrained_file}...")

        compile_and_run_klee(constrained_file, output_dir=CONSTRAINED_KLEE_DIR)
        new_true, new_false = find_branch_tests(CONSTRAINED_KLEE_DIR)

        if new_true and new_false:
            true_inputs = extract_ktest_inputs(new_true[0], CONSTRAINED_KLEE_DIR)
            false_inputs = extract_ktest_inputs(new_false[0], CONSTRAINED_KLEE_DIR)
            if true_inputs and false_inputs:
                pub_val_true = true_inputs.get("pub")
                pub_val_false = false_inputs.get("pub")
                if pub_val_true == pub_val_false:
                    print("\nCONTROL-FLOW LEAK DETECTED!")
                    print(f"Public input (fixed): pub = {pub_val_true}")
                    print(f"True branch secret:  secret = {true_inputs.get('secret')}")
                    print(f"False branch secret: secret = {false_inputs.get('secret')}")
                    return True
                else:
                    print("Branches differ but public inputs also differ")
            else:
                print("Missing input data to verify leak.")
        else:
            print("No leak detected for this input.")
    return False


def main():
    c_file_path = os.path.join(BASE_DIR, TARGET_C_FILE)
    compile_and_run_klee(c_file_path, output_dir=ORIGINAL_KLEE_DIR)

    true_tests, false_tests = find_branch_tests(ORIGINAL_KLEE_DIR)
    if DEBUG:
        print_results("True", true_tests, ORIGINAL_KLEE_DIR)
        print_results("False", false_tests, ORIGINAL_KLEE_DIR)
    else:
        print(f'\n"True" Branches ({len(true_tests)} paths):\n')
        print(f'\n"False" Branches ({len(false_tests)} paths):\n')

    print("\nChecking for control-flow leaks...")
    if detect_control_flow_leak_for_tests(true_tests, "true"):
        return
    if detect_control_flow_leak_for_tests(false_tests, "false"):
        return
    print("No leak detected after checking all constrained inputs.")


if __name__ == "__main__":
    main()
