/*
Author: Jameson DiPalma
*/

#include "branch_tracker.h"

// Global state
int program_run = 0;
int branch_history_1[MAX_BRANCH_VISITS];
int branch_history_2[MAX_BRANCH_VISITS];
int branch_index_1 = 0;
int branch_index_2 = 0;

// Reset the tracking arrays and indices
void reset_branch_history() {
    for (int i = 0; i < MAX_BRANCH_VISITS; i++) {
        branch_history_1[i] = -1;
        branch_history_2[i] = -1;
    }
    branch_index_1 = 0;
    branch_index_2 = 0;
}

// Record a branch hit (0 or 1) during run 1 or run 2
void record_branch_hit(int value) {
    if (program_run == 1 && branch_index_1 < MAX_BRANCH_VISITS) {
        branch_history_1[branch_index_1++] = value;
    } else if (program_run == 2 && branch_index_2 < MAX_BRANCH_VISITS) {
        branch_history_2[branch_index_2++] = value;
    }
}

// Check if the two branch histories are equal
int branch_histories_equal() {
    for (int i = 0; i < MAX_BRANCH_VISITS; i++) {
        if (branch_history_1[i] != branch_history_2[i]) {
            return 0;
        }
    }
    return 1;
}
