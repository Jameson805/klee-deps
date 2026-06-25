#include "runner_config.generated.h"
#include "original_stdin_runner.h"

static const runner_input_segment runner_segments[] = {
    { data_buf, sizeof(data_buf) },
};

#define main original_ghostrider_findmax_main
#define read runner_io_read
#define write runner_io_write
#include "findmax.c"
#undef write
#undef read
#undef main

int driver_main(void) {
    runner_io_reset(runner_segments, sizeof(runner_segments) / sizeof(runner_segments[0]));
    original_ghostrider_findmax_main(0, (char **)0);
    return runner_io_status();
}
