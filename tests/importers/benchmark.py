"""FR-029: reproducible native Windows timings and traced Python allocation peaks."""

import argparse
from collections.abc import Callable
import gc
import json
from pathlib import Path
import platform
from statistics import median
from time import perf_counter_ns
import tracemalloc

from ride_forces_analyzer.importers import (
    ImportResult,
    ImportSuccess,
    import_forces,
    import_forces_bytes,
)
from tests.support.recordings import REAL_FIXTURE_DIRECTORY, REAL_FIXTURES


def _successful(call: Callable[[], ImportResult], expected: tuple[int, str]) -> ImportSuccess:
    result = call()
    if (
        not isinstance(result, ImportSuccess)
        or (result.byte_count, result.source_sha256) != expected
    ):
        raise RuntimeError("Benchmark import/integrity failure")
    return result


def _measure(
    call: Callable[[], ImportResult],
    expected: tuple[int, str],
    repetitions: int,
) -> dict[str, object]:
    # Warm up outside timings; release each recording before the next invocation.
    _successful(call, expected)
    milliseconds: list[float] = []
    for _ in range(repetitions):
        gc.collect()
        start = perf_counter_ns()
        result = call()
        elapsed = (perf_counter_ns() - start) / 1_000_000
        if (
            not isinstance(result, ImportSuccess)
            or (result.byte_count, result.source_sha256) != expected
        ):
            raise RuntimeError("Timed import/integrity failure")
        milliseconds.append(elapsed)
        del result
    # Allocation tracing has overhead: do not mix this run into elapsed-time samples.
    gc.collect()
    tracemalloc.start()
    try:
        retained = _successful(call, expected)
        current, peak = tracemalloc.get_traced_memory()
        result_counts = {
            "acceleration": len(retained.recording.motion.acceleration),
            "gravity": len(retained.recording.motion.gravity)
            if retained.recording.motion.gravity is not None
            else None,
            "gps": len(retained.recording.gps.entries)
            if retained.recording.gps is not None
            else None,
            "diagnostics": len(retained.diagnostics),
        }
    finally:
        tracemalloc.stop()
    return {
        "repetitions": repetitions,
        "milliseconds": [round(value, 3) for value in milliseconds],
        "median_ms": round(median(milliseconds), 3),
        "min_ms": round(min(milliseconds), 3),
        "max_ms": round(max(milliseconds), 3),
        "python_current_bytes": current,
        "python_peak_bytes": peak,
        "counts": result_counts,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions", type=int, default=5)
    arguments = parser.parse_args()
    if platform.system() != "Windows":
        parser.error("This benchmark requires native Windows for project evidence")
    repetitions: int = arguments.repetitions
    if not 1 <= repetitions <= 100:
        parser.error("repetitions must be between 1 and 100")
    measurements: dict[str, object] = {}
    for filename, expected in REAL_FIXTURES.items():
        path: Path = REAL_FIXTURE_DIRECTORY / filename
        modified = path.stat().st_mtime_ns
        raw = path.read_bytes()
        path_call = lambda: import_forces(path)
        bytes_call = lambda: import_forces_bytes(raw)
        measurements[filename.split("-", 1)[0]] = {
            "path": _measure(path_call, expected, repetitions),
            "bytes": _measure(bytes_call, expected, repetitions),
        }
        if path.read_bytes() != raw or path.stat().st_mtime_ns != modified:
            raise RuntimeError("Original fixture changed during measurement")
    print(
        json.dumps(
            {
                "platform": platform.platform(),
                "python": platform.python_version(),
                "architecture": platform.machine(),
                "method": "One warmup, GC outside each timed call, then one separate tracemalloc import; warm filesystem cache. Bytes input is preloaded. Traced allocations exclude preexisting bytes and native/process RAM.",
                "measurements": measurements,
            },
            indent=2,
        ),
    )


if __name__ == "__main__":
    main()
