"""Stage 1: immutable API contracts and capability restrictions, not scientific math."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from hashlib import sha256
import json
import subprocess
import sys
from typing import cast

import numpy as np
import pytest

from ride_forces_analyzer.analysis import (
    AnalysisChannel,
    AnalysisDiagnostic,
    AnalysisProfile,
    AnalysisProvenance,
    AnalysisResult,
    CapabilityState,
    EvidenceState,
    FrameLabel,
    ParameterValue,
    ProcessingKind,
    ProfileName,
    QuantityKind,
    ResultValidity,
    SampleValues,
    SourceSequence,
    TimeBasis,
    TimeBasisKind,
    UnitAssignment,
    UnitLabel,
)
from ride_forces_analyzer.domain import SampleRate, SourceNumber, SourceProvenance, ValueOrigin
from ride_forces_analyzer.importers import (
    ImportSuccess,
    Severity,
    decode_forces_bytes,
    import_forces,
    import_forces_bytes,
)
from tests.support.recordings import REAL_FIXTURE_DIRECTORY, REAL_FIXTURES


def _source() -> ImportSuccess:
    raw = json.dumps(
        {
            "schemaVersion": "2.2.0",
            "device": "Apple Watch",
            "accelerationSequence": [{"x": "0.000", "y": "0", "z": "1.00"}] * 3,
            "startIndex": 0,
            "endIndex": 2,
            "locationSequence": [{"latitude": 0, "longitude": 0}] * 2,
        },
    ).encode()
    result = import_forces_bytes(raw)
    assert isinstance(result, ImportSuccess)
    return result


def _channel() -> AnalysisChannel:
    return AnalysisChannel(
        "raw-x",
        QuantityKind.SOURCE_VALUES,
        CapabilityState.VERIFIED,
        SourceSequence.ACCELERATION,
        samples=SampleValues(np.array([0.0], dtype=np.float64)),
        source_indices=(0,),
        columns=("x",),
        frame=FrameLabel.DEVICE,
    )


def _result(
    *,
    source: ImportSuccess | None = None,
    channels: tuple[AnalysisChannel, ...] | None = None,
    profile: AnalysisProfile = AnalysisProfile(),
    diagnostics: tuple[AnalysisDiagnostic, ...] = (),
) -> AnalysisResult:
    imported = source if source is not None else _source()
    return AnalysisResult(
        imported,
        profile,
        AnalysisProvenance(
            imported.recording.source.provenance,
            "test-engine",
            "raw-copy",
            datetime(2026, 10, 14, tzinfo=UTC),
        ),
        channels if channels is not None else (_channel(),),
        diagnostics,
    )


def test_sample_bytes_own_input_and_cannot_be_made_writeable() -> None:
    original = np.array([[0.0, 1.0, 2.0]], dtype=np.float64)
    samples = SampleValues(original)
    original[0, 0] = 999
    view = samples.values
    assert view[0, 0] == 0 and not view.flags.writeable
    with pytest.raises(ValueError):
        view.setflags(write=True)
    with pytest.raises(ValueError):
        view[0, 0] = 123
    with pytest.raises(TypeError):
        memoryview(view)[0, 0] = 123
    # Deliberate hostile metadata edit, not a recommended NumPy consumer operation.
    with pytest.warns(DeprecationWarning, match="Setting the dtype"):
        setattr(view, "dtype", np.uint8)
    assert samples.shape == samples.values.shape == (1, 3)
    assert samples.values.dtype == np.dtype("<f8")
    independent = samples.values.copy()
    independent[0, 0] = 888
    assert samples.values[0, 0] == 0
    with pytest.raises(FrozenInstanceError):
        setattr(samples, "shape", (3,))


def test_missing_rows_remain_distinct_from_valid_zero() -> None:
    samples = SampleValues(np.array([0.0, np.nan]), valid_rows=[True, False])
    assert samples.valid_rows == (True, False)
    assert samples.values[0] == 0 and np.isnan(samples.values[1])
    for values, validity in [([0.0], [False]), ([np.nan], [True]), ([np.inf], [False])]:
        with pytest.raises(ValueError):
            SampleValues(np.array(values), valid_rows=validity)


@pytest.mark.parametrize(
    "values",
    [np.array([True]), np.array(["1"]), np.array([1j]), np.array([object()])],
)
def test_non_real_source_arrays_are_not_silently_coerced(
    values: np.ndarray[tuple[int, ...], np.dtype[np.generic]],
) -> None:
    with pytest.raises(TypeError):
        SampleValues(values)


@pytest.mark.parametrize(
    "values",
    [np.array(1.0), np.array([]), np.empty((1, 0)), np.zeros((1, 1, 1))],
)
def test_sample_shape_requires_nonempty_rows_and_columns(
    values: np.ndarray[tuple[int, ...], np.dtype[np.generic]],
) -> None:
    with pytest.raises(ValueError):
        SampleValues(values)


def test_profile_configuration_and_nested_contracts_resist_mutation() -> None:
    configuration: dict[str, ParameterValue] = {"cutoff": 0, "unset": None}
    profile = AnalysisProfile(
        ProfileName.GPS_STRICT,
        configuration=configuration,
        policy_references=("synthetic-policy",),
    )
    configuration["cutoff"] = 100
    assert profile.configuration["cutoff"] == 0 and profile.configuration["unset"] is None
    with pytest.raises(TypeError):
        cast(dict[str, ParameterValue], profile.configuration)["cutoff"] = 100
    with pytest.raises(FrozenInstanceError):
        setattr(profile, "allow_provisional", True)
    with pytest.raises(TypeError):
        AnalysisProfile(
            ProfileName.GPS_STRICT,
            configuration={"nested": cast(ParameterValue, [])},
            policy_references=("policy",),
        )
    with pytest.raises(ValueError):
        AnalysisProfile(
            ProfileName.GPS_STRICT,
            configuration={"number": float("nan")},
            policy_references=("policy",),
        )


def test_default_profile_cannot_silently_enable_assumptions_or_filtering() -> None:
    assert AnalysisProfile().name is ProfileName.RAW_DEVICE_ONLY
    with pytest.raises(ValueError):
        AnalysisProfile(allow_provisional=True, assumptions=("guess",))
    with pytest.raises(ValueError):
        AnalysisProfile(configuration={"filter": "butterworth"})
    with pytest.raises(ValueError):
        AnalysisProfile(ProfileName.RIDER_CALIBRATED)
    with pytest.raises(ValueError):
        _result(channels=(replace(_channel(), processing=ProcessingKind.FILTERED),))


def test_unit_and_epoch_assignments_require_explicit_evidence() -> None:
    with pytest.raises(ValueError):
        UnitAssignment(UnitLabel.ACCELERATION_SI)
    with pytest.raises(ValueError):
        UnitAssignment(UnitLabel.ACCELERATION_SI, EvidenceState.VERIFIED)
    with pytest.raises(ValueError):
        TimeBasis(TimeBasisKind.SOURCE_UNVERIFIED, epoch="apple-reference")
    with pytest.raises(ValueError):
        TimeBasis(TimeBasisKind.VERIFIED_SECONDS)
    with pytest.raises(ValueError):
        TimeBasis(TimeBasisKind.INFERRED_UNIFORM)
    basis = TimeBasis(TimeBasisKind.INFERRED_UNIFORM, sample_rate=SampleRate())
    assert basis.sample_rate is not None and basis.sample_rate.origin is ValueOrigin.DEFAULT
    assert basis.epoch is None


@pytest.mark.parametrize(
    "quantity",
    [
        QuantityKind.SPECIFIC_FORCE,
        QuantityKind.GRAVITY,
        QuantityKind.SPEED,
        QuantityKind.LOAD_FACTOR,
    ],
)
def test_physical_values_cannot_claim_unknown_units(quantity: QuantityKind) -> None:
    with pytest.raises(ValueError):
        replace(_channel(), quantity=quantity)
    with pytest.raises(ValueError):
        replace(
            _channel(),
            unit=UnitAssignment(UnitLabel.METERS, EvidenceState.VERIFIED, ("test",)),
        )


def test_assumed_units_cannot_be_promoted_to_verified_physical_values() -> None:
    assumed = UnitAssignment(
        UnitLabel.ACCELERATION_SI,
        EvidenceState.ASSUMED,
        ("synthetic-assumption",),
    )
    with pytest.raises(ValueError):
        replace(_channel(), quantity=QuantityKind.SPECIFIC_FORCE, unit=assumed)
    provisional = replace(
        _channel(),
        quantity=QuantityKind.SPECIFIC_FORCE,
        unit=assumed,
        state=CapabilityState.PROVISIONAL,
    )
    with pytest.raises(ValueError):
        _result(channels=(provisional,))
    profile = AnalysisProfile(
        ProfileName.RIDER_CALIBRATED,
        policy_references=("synthetic-policy",),
        assumptions=("synthetic-unit",),
        allow_provisional=True,
    )
    assert _result(channels=(provisional,), profile=profile).validity is ResultValidity.RESTRICTED


def test_frame_evidence_and_compatible_units_are_independent_contract_gates() -> None:
    unit = UnitAssignment(UnitLabel.ACCELERATION_SI, EvidenceState.VERIFIED, ("synthetic-units",))
    with pytest.raises(ValueError):
        replace(_channel(), quantity=QuantityKind.SPECIFIC_FORCE, unit=unit, frame=FrameLabel.RIDER)
    physical = replace(
        _channel(),
        quantity=QuantityKind.SPECIFIC_FORCE,
        unit=unit,
        frame=FrameLabel.RIDER,
        frame_evidence=("synthetic-frame",),
    )
    with pytest.raises(ValueError):
        _result(channels=(physical,))
    profile = AnalysisProfile(ProfileName.RIDER_CALIBRATED, policy_references=("synthetic-policy",))
    result = _result(channels=(physical,), profile=profile)
    assert result.validity is ResultValidity.VALID
    assert result.channels[0].frame_evidence == ("synthetic-frame",)
    with pytest.raises(ValueError):
        replace(physical, unit=UnitAssignment(UnitLabel.METERS, EvidenceState.VERIFIED, ("test",)))


def test_result_owns_caller_collections_and_missingness_mask() -> None:
    channels = [_channel()]
    diagnostics = [AnalysisDiagnostic("NOTE", Severity.INFO, "Information")]
    result = _result(
        channels=cast(tuple[AnalysisChannel, ...], channels),
        diagnostics=cast(tuple[AnalysisDiagnostic, ...], diagnostics),
    )
    channels.clear()
    diagnostics.clear()
    assert len(result.channels) == len(result.diagnostics) == 1
    validity = [True, False]
    samples = SampleValues(np.array([0.0, np.nan]), valid_rows=validity)
    validity[0] = False
    assert samples.valid_rows == (True, False)


def test_unavailable_and_invalid_channels_never_fabricate_zero_samples() -> None:
    for state in (CapabilityState.UNAVAILABLE, CapabilityState.INVALID):
        with pytest.raises(ValueError):
            replace(_channel(), state=state, reason="missing")
        excluded = replace(
            _channel(),
            state=state,
            samples=None,
            source_indices=(),
            reason="missing",
        )
        result = _result(channels=(excluded,))
        assert result.channels[0].samples is None
        assert result.validity is (
            ResultValidity.INVALID
            if state is CapabilityState.INVALID
            else ResultValidity.RESTRICTED
        )


def test_source_sequence_and_diagnostic_indices_are_bounded_independently() -> None:
    channel = replace(_channel(), source_sequence=SourceSequence.GPS, source_indices=(2,))
    with pytest.raises(ValueError):
        _result(channels=(channel,))  # GPS has two slots; motion has three.
    with pytest.raises(ValueError):
        _result(channels=(replace(_channel(), source_sequence=SourceSequence.GRAVITY),))
    for index in (-1, True):
        with pytest.raises(ValueError):
            replace(_channel(), source_indices=(index,))
    with pytest.raises(ValueError):
        _result(
            diagnostics=(AnalysisDiagnostic("BAD_INDEX", Severity.ERROR, "Rejected", "raw-x", 3),),
        )
    with pytest.raises(ValueError):
        _result(
            diagnostics=(AnalysisDiagnostic("BAD_CHANNEL", Severity.ERROR, "Rejected", "unknown"),),
        )


def test_diagnostics_order_is_deterministic_and_exact_ties_keep_emission_order() -> None:
    first = AnalysisDiagnostic("SAME", Severity.WARNING, "First", "raw-x", 0)
    second = replace(first, message="Second")
    error = AnalysisDiagnostic("ERROR", Severity.ERROR, "Error")
    info = AnalysisDiagnostic("INFO", Severity.INFO, "Information")
    result = _result(diagnostics=(info, first, error, second))
    assert result.diagnostics == (error, first, second, info)
    assert result.validity is ResultValidity.INVALID
    assert _result(diagnostics=(info, first, error, second)) == result
    with pytest.raises(FrozenInstanceError):
        setattr(first, "severity", Severity.INFO)


def test_result_rejects_incomplete_m2_input_and_mismatched_provenance() -> None:
    result = _result()
    subset = decode_forces_bytes(result.source.recording.source.original_bytes)
    failure = import_forces_bytes(b"{}")
    for wrong in (subset, failure):
        with pytest.raises(TypeError):
            replace(result, source=cast(ImportSuccess, wrong))
    with pytest.raises(ValueError):
        replace(result, provenance=replace(result.provenance, source=SourceProvenance(1, "0" * 64)))
    with pytest.raises(ValueError):
        replace(result.provenance, calculation_time=datetime(2026, 10, 14))
    with pytest.raises(ValueError):
        replace(result, channels=(result.channels[0], result.channels[0]))
    with pytest.raises(FrozenInstanceError):
        setattr(result, "schema_version", "changed")


def test_model_construction_is_offline_write_free_and_qt_independent() -> None:
    script = """
import builtins
import os
import socket
import sys
import ride_forces_analyzer.analysis as public
assert "numpy" not in sys.modules
assert "ride_forces_analyzer.analysis.models" not in sys.modules
for name in public.__all__:
    value = getattr(public, name)
    assert value is getattr(public.models, name)
    assert vars(public)[name] is value
try:
    public.unknown_model
except AttributeError:
    pass
else:
    raise AssertionError("Unknown model must raise AttributeError")
from tests.analysis.test_models import _result
assert not any(name.startswith(("PySide6", "scipy", "pint", "geographiclib")) for name in sys.modules)
def deny(*args, **kwargs):
    raise AssertionError("Unexpected file or network access")
builtins.open = deny
os.open = deny
socket.socket = deny
result = _result()
assert result.channels[0].samples.values[0] == 0
assert result.source.recording.source.original_bytes
print("Offline model construction passed without Qt or proposed libraries.")
"""
    completed = subprocess.run(
        [sys.executable, "-B", "-c", script],
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr.decode()
    assert b"Offline model construction passed" in completed.stdout


@pytest.mark.parametrize("filename", REAL_FIXTURES, ids=lambda name: name.split("-", 1)[0])
def test_all_five_m2_sources_keep_exact_bytes_and_explicit_raw_capabilities(filename: str) -> None:
    path = REAL_FIXTURE_DIRECTORY / filename
    before = path.read_bytes()
    modified = path.stat().st_mtime_ns
    imported = import_forces(path)
    assert isinstance(imported, ImportSuccess)
    recording = imported.recording
    values = np.array(
        [(v.x, v.y, v.z) for v in recording.motion.acceleration[:2]],
        dtype=np.float64,
    )
    channel = AnalysisChannel(
        "raw-motion",
        QuantityKind.SOURCE_VALUES,
        CapabilityState.VERIFIED,
        SourceSequence.ACCELERATION,
        frame=FrameLabel.DEVICE,
        samples=SampleValues(values),
        source_indices=(0, 1),
        columns=("x", "y", "z"),
        time_basis=TimeBasis(
            TimeBasisKind.INFERRED_UNIFORM,
            sample_rate=recording.motion.sample_rate,
        ),
    )
    result = _result(source=imported, channels=(channel,))
    assert result.source is imported and result.channels[0].unit.label is UnitLabel.UNKNOWN
    assert result.source.recording.source.original_bytes == before
    assert (len(before), sha256(before).hexdigest()) == REAL_FIXTURES[filename]
    assert path.read_bytes() == before and path.stat().st_mtime_ns == modified
    root = recording.source.root
    assert root is not None and isinstance(root["minForce"], SourceNumber)
    if filename.startswith("IronGwazi"):
        assert recording.gps is None and recording.motion.gravity is None
        with pytest.raises(ValueError):
            _result(
                source=imported,
                channels=(replace(channel, source_sequence=SourceSequence.GRAVITY),),
            )


def test_models_reject_incompatible_runtime_assignments_and_missing_evidence() -> None:
    from typing import Any

    for changes, error in (
        ({"allow_provisional": 1}, TypeError),
        ({"configuration": ()}, TypeError),
        (
            {
                "name": ProfileName.RIDER_CALIBRATED,
                "policy_references": ("policy",),
                "allow_provisional": True,
            },
            ValueError,
        ),
    ):
        with pytest.raises(error):
            replace(AnalysisProfile(), **cast(dict[str, Any], changes))
    with pytest.raises(ValueError, match="explicit boolean"):
        SampleValues(np.array([1.0]), valid_rows=cast(Any, (1,)))
    with pytest.raises(TypeError, match="M2 value and origin"):
        TimeBasis(TimeBasisKind.INFERRED_UNIFORM, sample_rate=cast(Any, 50))
    time = TimeBasis(TimeBasisKind.VERIFIED_SECONDS, evidence=("independent clock",), epoch="UTC")
    assert time.epoch == "UTC"
    channel = _channel()
    for changes, error in (
        ({"unit": "unknown"}, TypeError),
        ({"samples": SampleValues(np.array([1.0, 2.0]))}, ValueError),
        ({"columns": ("x", "y")}, ValueError),
    ):
        with pytest.raises(error):
            replace(channel, **cast(dict[str, Any], changes))
    for changes in ({"source_index": -1}, {"source_index": 0, "channel_id": None}):
        with pytest.raises(ValueError):
            AnalysisDiagnostic("NOTE", Severity.INFO, "Message", **cast(dict[str, Any], changes))
    result = _result()
    with pytest.raises(TypeError, match="retained M2"):
        replace(result.provenance, source=cast(Any, None))
    for changes, error in (
        ({"profile": None}, TypeError),
        ({"channels": ()}, ValueError),
        ({"diagnostics": ("NOTE",)}, TypeError),
    ):
        with pytest.raises(error):
            replace(result, **cast(dict[str, Any], changes))
    provisional = replace(channel, state=CapabilityState.PROVISIONAL)
    profile = AnalysisProfile(ProfileName.RIDER_CALIBRATED, policy_references=("policy",))
    with pytest.raises(ValueError, match="Provisional channels require"):
        replace(result, profile=profile, channels=(provisional,))
