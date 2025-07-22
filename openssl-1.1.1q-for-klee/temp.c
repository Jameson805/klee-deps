int insecure_demo(int pub1, int* pub2, int secret) {
    if (pub1 > 0) {
        if (pub1 < 10 && secret > 0) {
            return pub2[secret];
        }
    }
    return -1;
}

// Symbolically run code below using KLEE
void self_composition() {
    symbolic int pub, sec1, sec2;

    //augmented to record branch history
    target_func(pub, sec1, run=1);
    target_func(pub, sec2, run=2); 

    assert(branch_histories_equal());
}

// inserted before each symbolic fork in KLEE's engine
void check_divergent_control_flow(cond_expr) {
    pc_true  = current_path_condition + cond_expr
    pc_false = current_path_condition + !cond_expr

    pub   = symbolic_vars(is_secret = false)
    sec1  = symbolic_vars(is_secret = true) 
    sec2  = symbolic_vars(is_secret = true) 

    pc_true_sub  = substitute(pc_true, pub, sec1)
    pc_false_sub = substitute(pc_false, pub, sec2)

    if (solver_is_sat(pc_true_sub && pc_false_sub))
        report_leak();
}