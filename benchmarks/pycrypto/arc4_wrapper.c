#include "runner_config.generated.h"
#include "original_stdin_runner.h"

static const runner_input_segment runner_segments[] = {
    { key_buf, sizeof(key_buf) },
};

#define main original_pycrypto_arc4_main
#define read runner_io_read
#define write runner_io_write
#include "src/ARC4.c"
#undef write
#undef read
#undef main

int driver_main(void) {
    int result;

    runner_io_reset(runner_segments, sizeof(runner_segments) / sizeof(runner_segments[0]));
    result = original_pycrypto_arc4_main(0, (char **)0);
    return result != 0 || runner_io_status();
}
