/*
Author: Jameson DiPalma
*/

#ifndef BRANCH_TRACKER_H
#define BRANCH_TRACKER_H

// Maximum number of branch visits we are tracking
#define MAX_BRANCH_VISITS 8

// Global variable indicating current run (1 or 2)
extern int program_run;

// Resets both branch history arrays and indices
void reset_branch_history(void);

// Records a branch decision (0 or 1) during a given run
void record_branch_hit(int value);

// Compares both branch histories for equality (returns 1 if equal, 0 if different)
int branch_histories_equal(void);

#endif // BRANCH_TRACKER_H
