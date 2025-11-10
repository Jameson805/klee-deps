#include <stdio.h>

int branchRecords[65536];
int branchRecordsLen = 0;

void f(int n) {
   if (n > 0) {
   }
   for (int i = 0; i < n; ++i) {
   }
}

void g(int n) {
    if (n > 0) {
    }
}

int main() {
    f(3);
    g(1);

    printf("branchRecords: ");
    for (int i = 0; i < branchRecordsLen; ++i) printf("%d ", branchRecords[i]);
    printf("\n");
    return 0;
}
