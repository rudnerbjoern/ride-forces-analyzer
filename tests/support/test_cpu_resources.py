"""CPU topology counts use native evidence rather than assuming two threads per core."""

# cspell:words sysctlbyname physicalcpu cpus

import ctypes
from pathlib import Path
import struct
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from ride_forces_analyzer.runtime import cpu_resources as cpu


def test_render_jobs_validate_and_follow_the_local_processor_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for count, expected in ((24, 24), (1, 1), (None, 1)):
        monkeypatch.setattr(cpu, "detect_cpu_resources", lambda: cpu.CpuResources(None, count))
        assert cpu.render_job_limit() == expected
        assert cpu.effective_render_jobs(100) == expected
        assert cpu.effective_render_jobs(1) == 1
    for invalid in (0, -1, True, 2.0, "2", None):
        with pytest.raises(ValueError, match="positive integer"):
            cpu.effective_render_jobs(invalid)  # type: ignore[arg-type]


def windows_topology(
    monkeypatch: pytest.MonkeyPatch,
    data: bytes,
    *,
    fail_read: bool = False,
) -> None:
    def query(relationship: int, buffer: Any, length: Any) -> bool:
        assert relationship == 0
        size = ctypes.cast(length, ctypes.POINTER(ctypes.c_uint32))
        if buffer is None:
            size.contents.value = len(data)
            return False
        if fail_read:
            return False
        ctypes.memmove(buffer, data, len(data))
        return True

    library = SimpleNamespace(GetLogicalProcessorInformationEx=Mock(side_effect=query))
    monkeypatch.setattr(cpu.sys, "platform", "win32")
    monkeypatch.setattr(cpu.ctypes, "WinDLL", Mock(return_value=library), raising=False)
    monkeypatch.setattr(cpu.ctypes, "get_last_error", lambda: 122, raising=False)


@pytest.mark.parametrize("physical,logical", [(1, 1), (4, 4), (12, 16), (12, 24), (48, 96)])
def test_windows_counts_variable_core_records_without_assuming_smt(
    monkeypatch: pytest.MonkeyPatch,
    physical: int,
    logical: int,
) -> None:
    data = b"".join(
        struct.pack("=II", 0, 48 + 16 * (index % 2)) + bytes(40 + 16 * (index % 2))
        for index in range(physical)
    )
    windows_topology(monkeypatch, data)
    monkeypatch.setattr(cpu.os, "cpu_count", lambda: logical)
    resources = cpu.detect_cpu_resources()
    assert resources == cpu.CpuResources(physical, logical)
    assert resources.diagnostic_fields() == {
        "Physical CPU cores": str(physical),
        "Logical processors": str(logical),
    }


def test_windows_unknown_topology_preserves_logical_count(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cpu.os, "cpu_count", lambda: 24)
    for data in (b"", bytes(3), struct.pack("=II", 0, 0), struct.pack("=II", 0, 48)):
        windows_topology(monkeypatch, data)
        resources = cpu.detect_cpu_resources()
        assert resources.physical_cores is None and resources.logical_processors == 24
        assert resources.diagnostic_fields()["Physical CPU cores"] == "Unknown"
    windows_topology(monkeypatch, struct.pack("=II", 0, 8), fail_read=True)
    assert cpu.detect_cpu_resources().physical_cores is None


def test_linux_counts_package_core_pairs_and_skips_offline_cpus(
    monkeypatch: pytest.MonkeyPatch,
    export_directory: Path,
) -> None:
    root = export_directory / "cpu"
    for index in range(8):
        topology = root / f"cpu{index}" / "topology"
        topology.mkdir(parents=True)
        (topology / "physical_package_id").write_text(str(index // 4), encoding="ascii")
        (topology / "core_id").write_text(str(index % 4 // 2), encoding="ascii")
    offline = root / "cpu8"
    offline.mkdir()
    (offline / "online").write_text("0", encoding="ascii")
    monkeypatch.setattr(cpu.sys, "platform", "linux")
    monkeypatch.setattr(cpu, "LINUX_CPU_PATH", root)
    monkeypatch.setattr(cpu.os, "cpu_count", lambda: 8)
    assert cpu.detect_cpu_resources() == cpu.CpuResources(4, 8)
    # Incomplete topology must not silently report only the readable cores.
    (root / "cpu0/topology/core_id").unlink()
    assert cpu.detect_cpu_resources() == cpu.CpuResources(None, 8)


def test_macos_reads_physical_cores_without_external_commands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def query(name: bytes, value: Any, length: Any, new: None, new_length: int) -> int:
        assert name == b"hw.physicalcpu" and new is None and new_length == 0
        assert ctypes.cast(length, ctypes.POINTER(ctypes.c_size_t)).contents.value == 4
        ctypes.cast(value, ctypes.POINTER(ctypes.c_int)).contents.value = 6
        return 0

    query_mock = Mock(side_effect=query)
    monkeypatch.setattr(cpu.sys, "platform", "darwin")
    monkeypatch.setattr(
        cpu.ctypes,
        "CDLL",
        Mock(return_value=SimpleNamespace(sysctlbyname=query_mock)),
    )
    monkeypatch.setattr(cpu.os, "cpu_count", lambda: 12)
    assert cpu.detect_cpu_resources() == cpu.CpuResources(6, 12)
    query_mock.side_effect = None
    query_mock.return_value = -1
    assert cpu.detect_cpu_resources() == cpu.CpuResources(None, 12)


def test_unavailable_cpu_information_is_reported_as_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cpu.sys, "platform", "unsupported")
    monkeypatch.setattr(cpu.os, "cpu_count", lambda: None)
    assert cpu.detect_cpu_resources().diagnostic_fields() == {
        "Physical CPU cores": "Unknown",
        "Logical processors": "Unknown",
    }
    monkeypatch.setattr(cpu.sys, "platform", "win32")
    monkeypatch.setattr(
        cpu.ctypes,
        "WinDLL",
        Mock(side_effect=OSError("API unavailable")),
        raising=False,
    )
    assert cpu.detect_cpu_resources() == cpu.CpuResources(None, None)
