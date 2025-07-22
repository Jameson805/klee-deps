#include <stdint.h>
#include <stdlib.h>

// Dummy replacements for estream-dependent or missing symbols

void _gpg_error_init_stub(void) {}
void _gpgrt_log_set_sink(const char *name, void *stream, int fd) {}
void *_gpgrt_log_get_stream(void) { return 0; }
void *_gpgrt_b64enc_start(void *stream, const char *title) { return 0; }
void *_gpgrt_make_pipe(int filedes[2], void **r_fp, void **r_fp2, int *pid) { return 0; }
int _gpgrt_ftruncate(void *stream, long long length) { return 0; }
int _gpgrt_argparse(void *fp, void *arg, void *opts) { return 0; }
int _gpgrt_spawn_process_fd(void *argv, void *r_infp, void *r_outfp, void *r_errfp) { return 0; }

int _gcry_private_is_secure(void *arg) {
    return 1; // Assume "secure" to keep flow smooth
}

void* _gcry_private_malloc(size_t size) {
    return malloc(size);
}

void* _gcry_private_malloc_secure(size_t size, int clear) {
    void* ptr = malloc(size);
    return ptr;
}
