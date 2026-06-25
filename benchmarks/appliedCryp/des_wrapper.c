#include "runner_config.generated.h"
#include "original_stdin_runner.h"

#define main original_appliedcryp_des_main
#define read runner_io_read
#define write runner_io_write
#include "des.c"
#undef write
#undef read
#undef main

int driver_main(void) {
    unsigned char stdin_bytes[sizeof(key_buf) + sizeof(data_buf) + sizeof(data_buf)];
    const runner_input_segment runner_segments[] = {
        { stdin_bytes, sizeof(stdin_bytes) },
    };

    runner_copy_bytes(stdin_bytes, key_buf, sizeof(key_buf));
    runner_copy_bytes(stdin_bytes + sizeof(key_buf), data_buf, sizeof(data_buf));
    runner_copy_bytes(stdin_bytes + sizeof(key_buf) + sizeof(data_buf), data_buf, sizeof(data_buf));

    runner_io_reset(runner_segments, sizeof(runner_segments) / sizeof(runner_segments[0]));
    original_appliedcryp_des_main(0, (char **)0);
    return runner_io_status();
}
