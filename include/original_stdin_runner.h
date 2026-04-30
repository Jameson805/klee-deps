#ifndef ORIGINAL_STDIN_RUNNER_H
#define ORIGINAL_STDIN_RUNNER_H

#include <stddef.h>
#include <string.h>
#include <sys/types.h>

typedef struct {
    const unsigned char *data;
    size_t size;
} runner_input_segment;

static const runner_input_segment *runner_io_segments = NULL;
static size_t runner_io_segment_count = 0;
static size_t runner_io_segment_index = 0;
static size_t runner_io_segment_offset = 0;
static int runner_io_failed = 0;

static void runner_io_reset(const runner_input_segment *segments, size_t count) {
    runner_io_segments = segments;
    runner_io_segment_count = count;
    runner_io_segment_index = 0;
    runner_io_segment_offset = 0;
    runner_io_failed = 0;
}

static int runner_io_status(void) {
    return runner_io_failed;
}

static ssize_t runner_io_read(int fd, void *buf, size_t count) {
    unsigned char *dst = (unsigned char *)buf;
    size_t remaining = count;

    if (fd != 0) {
        runner_io_failed = 1;
        return -1;
    }

    while (remaining > 0 && runner_io_segment_index < runner_io_segment_count) {
        const runner_input_segment *segment = &runner_io_segments[runner_io_segment_index];
        size_t available = segment->size - runner_io_segment_offset;
        size_t chunk = available < remaining ? available : remaining;

        memcpy(dst, segment->data + runner_io_segment_offset, chunk);
        dst += chunk;
        remaining -= chunk;
        runner_io_segment_offset += chunk;

        if (runner_io_segment_offset == segment->size) {
            runner_io_segment_index += 1;
            runner_io_segment_offset = 0;
        }
    }

    if (remaining != 0) {
        memset(dst, 0, remaining);
        runner_io_failed = 1;
    }

    return (ssize_t)count;
}

static ssize_t runner_io_write(int fd, const void *buf, size_t count) {
    (void)buf;
    if (fd != 1) {
        runner_io_failed = 1;
        return -1;
    }
    return (ssize_t)count;
}

#endif
