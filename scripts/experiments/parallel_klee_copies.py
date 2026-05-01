#!/usr/bin/env python3
"""Run an experiment command in isolated workspace copies.

The heavy experiment runners rewrite benchmark-local artifacts and produce large
result trees, so sharing one checkout across concurrent runs leads to races and
cross-talk. This wrapper copies the repository once per worker, streams each
worker's output live, and still collects partial logs when an interrupt stops
the batch midway through.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import os
from pathlib import Path
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from typing import TextIO

from scripts.experiments.common import REPO_ROOT


@dataclass
class Worker:
    index: int
    copy_dir: Path
    stdout_log: Path
    stderr_log: Path
    status_log: Path
    copy_process: subprocess.Popen[str] | None = None
    process: subprocess.Popen[bytes] | None = None
    stdout_handle: TextIO | None = None
    stderr_handle: TextIO | None = None
    copy_succeeded: bool = False
    return_code: int | None = None
    finalized: bool = False
    stream_buffers: dict[str, str] = field(
        default_factory=lambda: {"stdout": "", "stderr": ""}
    )
    open_streams: set[str] = field(default_factory=set)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(line_buffering=True)

    parser = argparse.ArgumentParser(
        description="Run one command in multiple temporary workspace copies and collect the per-copy outputs.",
    )
    parser.add_argument("-t", "--tmp-dir", default="/tmp", help="Parent directory for temporary workspace copies")
    parser.add_argument("--clean-destination", action="store_true", help="Remove the destination directory before collecting outputs")
    parser.add_argument("num_copies", type=int, help="Number of workspace copies to launch")
    parser.add_argument("output_subdir", help="Relative path inside each copy to collect after the command finishes")
    parser.add_argument("destination_dir", help="Folder where per-copy outputs are written as destination_dir/0, /1, ...")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Command to execute in each copy root")
    args = parser.parse_args(argv)

    if args.num_copies <= 0:
        raise SystemExit("error: num_copies must be a positive integer")

    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise SystemExit("error: missing command to run")

    tmp_dir = Path(args.tmp_dir).resolve()
    destination_abs = Path(args.destination_dir).resolve()
    if args.clean_destination and destination_abs.exists():
        shutil.rmtree(destination_abs, ignore_errors=True)
    destination_abs.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    run_root = Path(tempfile.mkdtemp(prefix="klee-deps-parallel.", dir=str(tmp_dir)))
    log_dir = run_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    output_subdir = args.output_subdir.lstrip("/")
    selector = selectors.DefaultSelector()
    interrupted = False
    worker_env = dict(os.environ)
    worker_env["PYTHONUNBUFFERED"] = "1"
    workers = [
        Worker(
            index=index,
            copy_dir=run_root / f"copy-{index}",
            stdout_log=log_dir / f"{index}.stdout.log",
            stderr_log=log_dir / f"{index}.stderr.log",
            status_log=log_dir / f"{index}.status",
        )
        for index in range(args.num_copies)
    ]

    def raise_keyboard_interrupt(signum: int, _frame: object) -> None:
        raise KeyboardInterrupt

    previous_int = signal.signal(signal.SIGINT, raise_keyboard_interrupt)
    previous_term = signal.signal(signal.SIGTERM, raise_keyboard_interrupt)
    try:
        for worker in workers:
            start_copy(worker)

        # Workers move through two phases: copy the repository, then run the
        # requested command once the copy is ready. The event loop keeps both
        # phases progressing without blocking on any single worker.
        while not all(worker.finalized for worker in workers):
            made_progress = poll_copy_processes(workers, command, worker_env, selector)
            made_progress = drain_worker_streams(selector) or made_progress
            made_progress = finalize_exited_workers(workers) or made_progress
            if not made_progress:
                sleep_briefly(selector)
    except KeyboardInterrupt:
        interrupted = True
        emit("interrupted, stopping workers", error=True)
        terminate_workers(workers)
    finally:
        signal.signal(signal.SIGINT, previous_int)
        signal.signal(signal.SIGTERM, previous_term)

        if interrupted:
            # Give already-terminated workers a short window to flush logs so we
            # can still collect actionable partial output instead of losing the
            # failure context to a hard stop.
            deadline = time.monotonic() + 5
            while not all(worker.finalized for worker in workers):
                made_progress = poll_copy_processes(workers, command, worker_env, selector)
                made_progress = drain_worker_streams(selector) or made_progress
                made_progress = finalize_exited_workers(workers) or made_progress
                if all(worker.finalized for worker in workers):
                    break
                if time.monotonic() >= deadline:
                    force_finalize_workers(workers, selector, return_code=130)
                    break
                if not made_progress:
                    sleep_briefly(selector)

        force_finalize_workers(
            workers,
            selector,
            return_code=130 if interrupted else 1,
            only_pending=True,
        )
        selector.close()
        overall_rc = collect_results(workers, destination_abs, output_subdir)
        if not interrupted:
            shutil.rmtree(run_root, ignore_errors=True)

    if interrupted:
        emit(f"collected partial outputs in: {destination_abs}", error=True)
        return 130
    if overall_rc != 0:
        emit("one or more parallel runs failed", error=True)
        return overall_rc

    emit("all runs completed successfully")
    emit(f"collected outputs in: {destination_abs}")
    return 0


def emit(message: str, *, error: bool = False) -> None:
    print(message, file=sys.stderr if error else sys.stdout, flush=True)


def sleep_briefly(selector: selectors.BaseSelector) -> None:
    if selector.get_map():
        selector.select(timeout=0.1)
    else:
        time.sleep(0.1)


def worker_prefix(worker: Worker) -> str:
    return f"[worker {worker.index}]"


def start_copy(worker: Worker) -> None:
    emit(f"{worker_prefix(worker)} preparing workspace in: {worker.copy_dir}")
    worker.copy_dir.mkdir(parents=True, exist_ok=True)
    try:
        # Use a full copy instead of shared state because benchmark builds and
        # result collection both mutate the checkout heavily.
        worker.copy_process = subprocess.Popen(
            ["cp", "-a", f"{REPO_ROOT}/.", str(worker.copy_dir)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
    except OSError as error:
        worker.stderr_log.write_text(f"failed to start workspace copy: {error}\n", encoding="utf-8")
        worker.return_code = 1
        emit(f"{worker_prefix(worker)} failed to start workspace copy: {error}", error=True)
        finalize_worker(worker)


def poll_copy_processes(
    workers: list[Worker],
    command: list[str],
    worker_env: dict[str, str],
    selector: selectors.BaseSelector,
) -> bool:
    made_progress = False
    for worker in workers:
        if worker.finalized or worker.copy_process is None or worker.copy_succeeded:
            continue
        if worker.copy_process.poll() is None:
            continue

        copy_stdout, copy_stderr = worker.copy_process.communicate()
        if copy_stdout:
            worker.stdout_log.write_text(copy_stdout, encoding="utf-8")
        if copy_stderr:
            worker.stderr_log.write_text(copy_stderr, encoding="utf-8")

        if worker.copy_process.returncode != 0:
            worker.return_code = worker.copy_process.returncode
            emit(
                f"{worker_prefix(worker)} workspace copy failed with exit code {worker.return_code}",
                error=True,
            )
            if copy_stderr:
                for line in copy_stderr.splitlines():
                    emit(f"{worker_prefix(worker)} {line}", error=True)
            finalize_worker(worker)
        else:
            worker.copy_succeeded = True
            start_worker_process(worker, command, worker_env, selector)
        made_progress = True
    return made_progress


def start_worker_process(
    worker: Worker,
    command: list[str],
    worker_env: dict[str, str],
    selector: selectors.BaseSelector,
) -> None:
    emit(f"{worker_prefix(worker)} starting in: {worker.copy_dir}")
    worker.stdout_handle = worker.stdout_log.open("w", encoding="utf-8")
    worker.stderr_handle = worker.stderr_log.open("w", encoding="utf-8")
    try:
        worker.process = subprocess.Popen(
            command,
            cwd=worker.copy_dir,
            env=worker_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            bufsize=0,
            start_new_session=True,
        )
    except OSError as error:
        assert worker.stderr_handle is not None
        worker.stderr_handle.write(f"failed to start worker command: {error}\n")
        worker.stderr_handle.flush()
        worker.return_code = 1
        emit(f"{worker_prefix(worker)} failed to start worker command: {error}", error=True)
        finalize_worker(worker)
        return

    assert worker.process.stdout is not None
    assert worker.process.stderr is not None
    selector.register(worker.process.stdout, selectors.EVENT_READ, (worker, "stdout"))
    selector.register(worker.process.stderr, selectors.EVENT_READ, (worker, "stderr"))
    worker.open_streams.update({"stdout", "stderr"})
    emit(f"{worker_prefix(worker)} started with pid {worker.process.pid}")


def drain_worker_streams(selector: selectors.BaseSelector) -> bool:
    made_progress = False
    for key, _mask in selector.select(timeout=0):
        worker, stream_name = key.data
        chunk = os.read(key.fileobj.fileno(), 4096)
        if chunk:
            write_worker_output(worker, stream_name, chunk)
        else:
            close_worker_stream(selector, worker, stream_name, key.fileobj)
        made_progress = True
    return made_progress


def write_worker_output(worker: Worker, stream_name: str, chunk: bytes) -> None:
    decoded = chunk.decode("utf-8", errors="replace")
    handle = worker.stdout_handle if stream_name == "stdout" else worker.stderr_handle
    assert handle is not None
    handle.write(decoded)
    handle.flush()

    buffer = worker.stream_buffers[stream_name] + decoded
    lines = buffer.split("\n")
    worker.stream_buffers[stream_name] = lines.pop()
    for line in lines:
        emit(f"{worker_prefix(worker)} {line}", error=stream_name == "stderr")


def close_worker_stream(
    selector: selectors.BaseSelector,
    worker: Worker,
    stream_name: str,
    fileobj: object,
) -> None:
    try:
        selector.unregister(fileobj)
    except KeyError:
        pass
    if hasattr(fileobj, "close"):
        fileobj.close()

    remainder = worker.stream_buffers[stream_name]
    if remainder:
        emit(f"{worker_prefix(worker)} {remainder}", error=stream_name == "stderr")
        worker.stream_buffers[stream_name] = ""
    worker.open_streams.discard(stream_name)


def finalize_exited_workers(workers: list[Worker]) -> bool:
    made_progress = False
    for worker in workers:
        if worker.finalized or worker.process is None:
            continue
        if worker.process.poll() is None or worker.open_streams:
            continue
        finalize_worker(worker)
        made_progress = True
    return made_progress


def finalize_worker(worker: Worker) -> None:
    if worker.finalized:
        return
    if worker.stdout_handle is not None:
        worker.stdout_handle.close()
        worker.stdout_handle = None
    if worker.stderr_handle is not None:
        worker.stderr_handle.close()
        worker.stderr_handle = None

    if worker.return_code is None:
        if worker.process is not None and worker.process.returncode is not None:
            worker.return_code = worker.process.returncode
        elif worker.copy_process is not None and worker.copy_process.returncode is not None:
            worker.return_code = worker.copy_process.returncode
        else:
            worker.return_code = 1

    worker.status_log.write_text(f"{worker.return_code}\n", encoding="utf-8")
    worker.finalized = True


def terminate_workers(workers: list[Worker]) -> None:
    for worker in workers:
        terminate_process_group(worker.process)
        terminate_process_group(worker.copy_process)
    for worker in workers:
        wait_or_kill(worker.process)
        wait_or_kill(worker.copy_process)


def terminate_process_group(process: subprocess.Popen[object] | None) -> None:
    if process is None or process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return


def wait_or_kill(process: subprocess.Popen[object] | None) -> None:
    if process is None or process.poll() is not None:
        return
    try:
        process.wait(timeout=2)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    process.wait()


def force_finalize_workers(
    workers: list[Worker],
    selector: selectors.BaseSelector,
    *,
    return_code: int,
    only_pending: bool = False,
) -> None:
    for key in list(selector.get_map().values()):
        worker, stream_name = key.data
        close_worker_stream(selector, worker, stream_name, key.fileobj)

    for worker in workers:
        if only_pending and worker.finalized:
            continue
        if worker.finalized:
            continue
        if worker.return_code is None:
            if worker.process is not None and worker.process.returncode is not None:
                worker.return_code = worker.process.returncode
            elif worker.copy_process is not None and worker.copy_process.returncode is not None:
                worker.return_code = worker.copy_process.returncode
            else:
                worker.return_code = return_code
        finalize_worker(worker)


def collect_results(workers: list[Worker], destination_abs: Path, output_subdir: str) -> int:
    overall_rc = 0
    for worker in workers:
        destination = destination_abs / str(worker.index)
        logs_destination = destination / "_logs"
        destination.mkdir(parents=True, exist_ok=True)
        logs_destination.mkdir(parents=True, exist_ok=True)

        if worker.stdout_log.is_file():
            shutil.copy2(worker.stdout_log, logs_destination / "stdout.log")
        if worker.stderr_log.is_file():
            shutil.copy2(worker.stderr_log, logs_destination / "stderr.log")
        if worker.status_log.is_file():
            shutil.copy2(worker.status_log, logs_destination / "status")

        # Copy logs even for failed workers so post-mortem debugging never
        # depends on preserving the temporary workspace tree.
        source = worker.copy_dir / output_subdir
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True, symlinks=True)
        elif worker.copy_succeeded:
            print(
                f"warning: output path not found for copy {worker.index}: {output_subdir}",
                file=sys.stderr,
                flush=True,
            )

        return_code = worker.return_code if worker.return_code is not None else 1
        if return_code != 0:
            overall_rc = 1
            print(f"copy {worker.index} failed with exit code {return_code}", file=sys.stderr, flush=True)
            print(f"  stdout: {logs_destination / 'stdout.log'}", file=sys.stderr, flush=True)
            print(f"  stderr: {logs_destination / 'stderr.log'}", file=sys.stderr, flush=True)
            print(f"  status: {logs_destination / 'status'}", file=sys.stderr, flush=True)
    return overall_rc


if __name__ == "__main__":
    raise SystemExit(main())