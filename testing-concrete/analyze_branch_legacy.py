"""
Author: Jameson DiPalma
Note: Everything here was a first try for this idea. find_counterexamples.py
is currently a much better implementation of a better approach, but I'm keeping
this around just in case
"""

from z3 import *
import os
import re


def find_file(klee_out_dir):
    smt2_files = [f for f in os.listdir(klee_out_dir) if f.endswith(".smt2")]
    if not smt2_files:
        print("No .smt2 files found in", klee_out_dir)
        exit()

    smt2_path = os.path.join(klee_out_dir, smt2_files[0])
    print(f"Using SMT2 file: {smt2_path}")
    with open(smt2_path, "r") as f:
        full_smt2_text_raw = f.read()
    return clean_smt2_commands(full_smt2_text_raw)


def clean_smt2_commands(smt2_text):
    """Removes (set-logic), (check-sat), (exit), and (get-model) from SMT2 text."""
    lines = smt2_text.splitlines()
    filtered_lines = []
    for line in lines:
        stripped_line = line.strip()
        if not (stripped_line.startswith("(set-logic") or
                stripped_line.startswith("(check-sat)") or
                stripped_line.startswith("(exit)") or
                stripped_line.startswith("(get-model)")):
            filtered_lines.append(line)
    return "\n".join(filtered_lines)


def get_declared_vars(smt2_text):
    """Extracts variable names declared with (declare-fun ...)."""
    declared_vars = set()
    matches = re.findall(r"\(declare-fun\s+([^ ]+)\s+\(\)\s+([^)]+)\)", smt2_text)
    for var_name, var_type in matches:
        declared_vars.add(var_name)
        #not declared yet, but will be in world2_constraints
        declared_vars.add(f"{var_name}_2")
    return declared_vars


def find_and_split_smt2(full_smt2_text, target_branch, vars_to_analyze):
    """
    Finds the target branch condition within SMT2 and splits into pre-branch
    constraints and the identified branch assertion.
    """
    full_smt2_lines = full_smt2_text.splitlines()
    
    pre_branch_lines = []
    condition_idx = -1
    identified_branch_assertion = ""
    
    # Adjust target_branch for searching KLEE's raw output
    search_condition = target_branch
    for var_name in vars_to_analyze:
        if f"{var_name}_val" in search_condition:
            search_condition = re.sub(rf"\b{re.escape(var_name)}_val\b", var_name, search_condition)

    for i, line in enumerate(full_smt2_lines):
        stripped_line = line.strip()
        if stripped_line.startswith("(assert ") and search_condition in stripped_line:
            identified_branch_assertion = stripped_line
            condition_idx = i
            break 
        pre_branch_lines.append(line)

    if condition_idx == -1:
        print("Target branch condition '{target_branch}' (searched as '{search_condition}') not found")
        exit()
    
    #reordering in case Z3 solver causes problems
    declarations_in_pre = []
    assertions_in_pre = []

    for line in pre_branch_lines:
        if line.strip().startswith("(declare-fun"):
            declarations_in_pre.append(line)
        elif line.strip().startswith("(assert"):
            assertions_in_pre.append(line)
            
    pre_branch_text = "\n".join(declarations_in_pre + assertions_in_pre)
    return pre_branch_text, identified_branch_assertion


def extract_assertion_body(assertion_line):
    """
    Extracts the boolean expression from within an (assert ...) statement.
    e.g., "(assert (> x 0))" -> "> x 0"
    """
    assertion_line = assertion_line.strip()
    if assertion_line.startswith("(assert ") and assertion_line.endswith(")"):
        return assertion_line[len("(assert "):-1].strip()
    return assertion_line


def check_control_flow_leak(klee_out_dir, target_branch, debug):
    """
    Checks for a secret-dependent control flow leak by taking a single KLEE output,
    isolating constraints up to a user-specified branch condition, and then
    forcing divergent paths for the branch.
    """
    full_smt2_text = find_file(klee_out_dir)
    declared_vars = get_declared_vars(full_smt2_text)

    vars_to_analyze = ["secret", "pub"] 
    pre_branch_constraints_text, identified_branch_assertion = \
        find_and_split_smt2(full_smt2_text, target_branch, vars_to_analyze)

    needed_symbol_declarations = set()
    for var in vars_to_analyze:
        needed_symbol_declarations.add(var)
        needed_symbol_declarations.add(f"{var}_2")
    
    declarations_needed = ""
    for var_name in needed_symbol_declarations:
        if var_name not in declared_vars: # Only declare if not already declared by KLEE
            declarations_needed += f"(declare-fun {var_name} () (Array (_ BitVec 32) (_ BitVec 8) ) )\n"
    
    world1_constraints = pre_branch_constraints_text
    world2_constraints = pre_branch_constraints_text
    for var in vars_to_analyze:
        world2_constraints = re.sub(
            rf"\b{re.escape(var)}\b",
            f"{var}_2",
            world2_constraints
        )

    world1_branch_condition = extract_assertion_body(target_branch)
    world2_branch_condition = world1_branch_condition
    for var in vars_to_analyze:
        world2_branch_condition = re.sub(
            rf"\b{re.escape(var)}_val\b",
            f"{var}_2_val",
            world2_branch_condition
        )
    
    combined_smt2 = f"""
{declarations_needed}
{world1_constraints} 
{world2_constraints}

(define-fun secret_val () (_ BitVec 32)
(concat (select secret (_ bv3 32))
            (concat (select secret (_ bv2 32))
                    (concat (select secret (_ bv1 32))
                            (select secret (_ bv0 32))))))

(define-fun secret_2_val () (_ BitVec 32)
(concat (select secret_2 (_ bv3 32))
            (concat (select secret_2 (_ bv2 32))
                    (concat (select secret_2 (_ bv1 32))
                            (select secret_2 (_ bv0 32))))))

(define-fun pub_val () (_ BitVec 32)
(concat (select pub (_ bv3 32))
            (concat (select pub (_ bv2 32))
                    (concat (select pub (_ bv1 32))
                            (select pub (_ bv0 32))))))

(define-fun pub_2_val () (_ BitVec 32)
(concat (select pub_2 (_ bv3 32))
            (concat (select pub_2 (_ bv2 32))
                    (concat (select pub_2 (_ bv1 32))
                            (select pub_2 (_ bv0 32))))))

(assert (= pub_val pub_2_val))
(assert (not (= secret_val secret_2_val)))

; secret_val <= 0
(assert (= false (bvslt (_ bv0 32) secret_val)))

; secret_2_val > 0
(assert (not (= false (bvslt (_ bv0 32) secret_2_val))))

(check-sat)
(get-model)
    """

    if debug:
        print("===== Combined SMT2 Sent to Z3 =====")
        print(combined_smt2)
        print("====================================")

    s = Solver()
    try:
        s.from_string(combined_smt2)
        result = s.check()

        if result == sat:
            print("Leak detected")
            model = s.model()

            def array_to_int(array_name):
                val = 0
                for i in range(4):
                    byte_expr = Select(Const(array_name, ArraySort(BitVecSort(32), BitVecSort(8))), BitVecVal(i, 32))
                    byte_val = model.evaluate(byte_expr, model_completion=True)
                    if isinstance(byte_val, BitVecNumRef):
                        val = (val << 8) | byte_val.as_long()
                    else:
                        print(f"Unexpected byte value for {array_name}[{i}]:", byte_val)
                        return None
                # Convert from two's complement if sign bit is set
                if val & (1 << 31):
                    val -= 1 << 32
                return val

            for base_var in vars_to_analyze:
                for suffix in ["", "_2"]:
                    var_name = f"{base_var}{suffix}"
                    int_val = array_to_int(var_name)
                    if int_val is not None:
                        print(f"{var_name}: {int_val} (0x{int_val & 0xffffffff:08x})")
        elif result == unsat:
            print("No leak detected")
        else:
            print("Unknown solver result:", result)
    except Z3Exception as e:
        print(f"Z3 Error: {e}")


if __name__ == "__main__":
    klee_out_dir = "klee-out-0"
    target_branch = "(assert (=  false (bvslt  (_ bv0 32) (concat  (select  secret (_ bv3 32) ) (concat  (select  secret (_ bv2 32) ) (concat  (select  secret (_ bv1 32) ) (select  secret (_ bv0 32) ) ) ) ) ) ) )"
    #debug = True
    debug = False
    check_control_flow_leak(klee_out_dir, target_branch, debug)
