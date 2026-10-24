"""Local CPU counts and hardware bounds for configurable render jobs.

Copyright (c) 2026 Björn Rudner.
SPDX-License-Identifier: GPL-3.0-or-later
"""

# cspell:words sysctlbyname physicalcpu

import ctypes
from dataclasses import dataclass
import os
from pathlib import Path
import struct
import sys

LINUX_CPU_PATH = Path("/sys/devices/system/cpu")


@dataclass(frozen=True, slots=True)
class CpuResources:
    physical_cores: int | None
    logical_processors: int | None

    def diagnostic_fields(self) -> dict[str, str]:
        return {
            "Physical CPU cores": str(self.physical_cores) if self.physical_cores else "Unknown",
            "Logical processors": (
                str(self.logical_processors) if self.logical_processors else "Unknown"
            ),
        }


def detect_cpu_resources() -> CpuResources:
    """Read physical cores and logical processors without guessing SMT.

    Logical counts respect Python's CPU-count override. Unknown physical topology
    never becomes logical/2.
    Native queries do not launch external programs or change thread settings.
    """
    physical = None
    try:
        if sys.platform == "win32":
            physical = _windows_physical_cores()
        elif sys.platform == "darwin":
            physical = _macos_physical_cores()
        elif sys.platform == "linux":
            physical = _linux_physical_cores()
    except AttributeError, OSError, ValueError, struct.error:
        pass
    return CpuResources(physical, os.cpu_count())


def render_job_limit() -> int:
    """Allow at least one render job, up to the reported logical processor count."""
    return max(1, detect_cpu_resources().logical_processors or 1)


def effective_render_jobs(requested: int) -> int:
    """Validate a requested count and fit it to this computer's available limit."""
    if type(requested) is not int or requested < 1:
        raise ValueError("Render jobs must be a positive integer")
    return min(requested, render_job_limit())


def _windows_physical_cores() -> int | None:
    query = ctypes.WinDLL("kernel32", use_last_error=True).GetLogicalProcessorInformationEx
    query.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
    query.restype = ctypes.c_int
    length = ctypes.c_uint32()
    query(0, None, ctypes.byref(length))  # RelationProcessorCore, across all processor groups.
    if ctypes.get_last_error() != 122 or not length.value:  # ERROR_INSUFFICIENT_BUFFER
        return None
    buffer = ctypes.create_string_buffer(length.value)
    if not query(0, buffer, ctypes.byref(length)):
        return None
    offset = cores = 0
    while offset + 8 <= length.value:
        relationship, size = struct.unpack_from("=II", buffer, offset)
        if relationship != 0 or size < 8 or offset + size > length.value:
            return None
        cores += 1
        offset += size
    return cores if cores and offset == length.value else None


def _macos_physical_cores() -> int | None:
    query = ctypes.CDLL(None).sysctlbyname
    query.argtypes = [
        ctypes.c_char_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_size_t),
        ctypes.c_void_p,
        ctypes.c_size_t,
    ]
    query.restype = ctypes.c_int
    cores = ctypes.c_int()
    length = ctypes.c_size_t(ctypes.sizeof(cores))
    if query(b"hw.physicalcpu", ctypes.byref(cores), ctypes.byref(length), None, 0) != 0:
        return None
    return cores.value if length.value == ctypes.sizeof(cores) and cores.value > 0 else None


def _linux_physical_cores() -> int | None:
    cores: set[tuple[int, int]] = set()
    for cpu in LINUX_CPU_PATH.glob("cpu[0-9]*"):
        online = cpu / "online"
        if online.is_file() and online.read_text(encoding="ascii").strip() == "0":
            continue
        topology = cpu / "topology"
        package = int((topology / "physical_package_id").read_text(encoding="ascii"))
        core = int((topology / "core_id").read_text(encoding="ascii"))
        if package < 0 or core < 0:
            return None
        cores.add((package, core))
    return len(cores) or None
