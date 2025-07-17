/*
Contains minimal function definitions for functions KLEE can/might slip up on
*/

#include <pthread.h>
#include <stdio.h>
#include <string.h>
#include <stdarg.h>
#include <stdint.h>

int pthread_once(pthread_once_t *once_control, void (*init_routine)(void)) {
    if (init_routine) init_routine();
    return 0;
}

int pthread_key_create(pthread_key_t *key, void (*destructor)(void*)) {
    *key = 0;
    return 0;
}

int pthread_key_delete(pthread_key_t key) {
    return 0;
}

int pthread_setspecific(pthread_key_t key, const void *value) {
    return 0;
}

void *pthread_getspecific(pthread_key_t key) {
    return NULL;
}

int pthread_atfork(void (*prepare)(void), void (*parent)(void), void (*child)(void)) {
    return 0;
}

int pthread_equal(pthread_t t1, pthread_t t2) {
    return t1 == t2;
}

pthread_t pthread_self(void) {
    return 0;
}

void OPENSSL_cleanse(void *ptr, size_t len) {
    memset(ptr, 0, len);
}

// Common libc stubs
size_t strlen(const char *s) {
    size_t len = 0;
    while (*s++) len++;
    return len;
}

char *strcpy(char *dest, const char *src) {
    char *ret = dest;
    while ((*dest++ = *src++));
    return ret;
}

int vfprintf(FILE *stream, const char *format, va_list ap) {
    return 0;
}
