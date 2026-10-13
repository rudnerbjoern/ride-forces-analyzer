import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../../", import.meta.url));
const checker = path.join(root, "node_modules/pyright/index.js");
const python = path.join(root, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const configuration = spawnSync(python, ["-c",
  "import json,tomllib; from pathlib import Path; "
  + "print(json.dumps(tomllib.loads(Path('pyproject.toml').read_text())['tool']['pyright']))"], {
  cwd: root,
  encoding: "utf8",
  timeout: 30000,
});
assert.ifError(configuration.error);
assert.equal(configuration.status, 0, configuration.stderr);
const shared = JSON.parse(configuration.stdout);

const cases = [
  {
    name: "result discriminator narrows the public canonical types",
    imports: "from ride_forces_analyzer.domain import Recording, Vector3",
    source: "from typing import assert_type\n"
      + "from ride_forces_analyzer.importers import ImportResult\n"
      + "def consume(result: ImportResult) -> None:\n"
      + "    if result.success is True:\n"
      + "        assert_type(result.recording, Recording)\n"
      + "        assert_type(result.byte_count, int)\n"
      + "    else:\n"
      + "        assert_type(result.recording, None)\n"
      + "vector = Vector3(0, 0, 1)\n",
    rule: null,
  },
  {
    name: "decoder source result narrows separately from canonical motion",
    imports: "from ride_forces_analyzer.domain import SourceEnvelope",
    source: "from typing import assert_type\n"
      + "from ride_forces_analyzer.importers import decode_forces_bytes\n"
      + "result = decode_forces_bytes(b'{}')\n"
      + "if result.success is True:\n"
      + "    assert_type(result.source, SourceEnvelope)\n"
      + "    assert_type(result.byte_count, int)\n"
      + "else:\n"
      + "    assert_type(result.recording, None)\n",
    rule: null,
  },
  {
    name: "motion subset result narrows independently of a full recording import",
    imports: "from ride_forces_analyzer.domain import MotionSequence, SourceEnvelope",
    source: "from typing import assert_type\n"
      + "from ride_forces_analyzer.importers import parse_motion\n"
      + "result = parse_motion(SourceEnvelope(b'{}', {}))\n"
      + "if result.success is True:\n"
      + "    assert_type(result.motion, MotionSequence)\n"
      + "else:\n"
      + "    assert_type(result.recording, None)\n",
    rule: null,
  },
  {
    name: "optional subset exposes metadata and independent GPS without claiming a recording",
    imports: "from ride_forces_analyzer.domain import GpsSequence, RecordingMetadata, SourceEnvelope",
    source: "from typing import assert_type\n"
      + "from ride_forces_analyzer.importers import parse_optional_data\n"
      + "result = parse_optional_data(SourceEnvelope(b'{}', {}))\n"
      + "if result.success is True:\n"
      + "    assert_type(result.metadata, RecordingMetadata)\n"
      + "    assert_type(result.gps, GpsSequence | None)\n"
      + "else:\n"
      + "    assert_type(result.recording, None)\n",
    rule: null,
  },
  {
    name: "public import service narrows full recordings and original provenance",
    imports: "from pathlib import Path\nfrom ride_forces_analyzer.domain import Recording",
    source: "from typing import assert_type\n"
      + "from ride_forces_analyzer.importers import import_forces, import_forces_bytes\n"
      + "for result in (import_forces(Path('recording.forces')), import_forces_bytes(b'{}')):\n"
      + "    if result.success is True:\n"
      + "        assert_type(result.recording, Recording)\n"
      + "        assert_type(result.byte_count, int)\n"
      + "        assert_type(result.source_sha256, str)\n"
      + "    else:\n"
      + "        assert_type(result.recording, None)\n"
      + "        assert_type(result.byte_count, int | None)\n",
    rule: null,
  },
  {
    name: "canonical vector constructor rejects a string component statically",
    imports: "from ride_forces_analyzer.domain import Vector3",
    source: "vector = Vector3('0', 0, 1)\n",
    rule: "reportArgumentType",
  },
  {
    name: "frozen vector fields reject static assignment",
    imports: "from ride_forces_analyzer.domain import Vector3",
    source: "vector = Vector3(0, 0, 1)\nvector.x = 2\n",
    rule: "reportAttributeAccessIssue",
  },
  {
    name: "source object mappings reject static item mutation",
    imports: "from ride_forces_analyzer.domain import SourceEnvelope",
    source: "source = SourceEnvelope(b'{}', {})\n"
      + "if source.root is not None:\n"
      + "    source.root['changed'] = 'value'\n",
    rule: "reportIndexIssue",
  },
];

for (const { name, imports, source, rule } of cases) {
  test(name, async () => {
    await mkdir(path.join(root, ".tmp"), { recursive: true });
    const temporary = await mkdtemp(path.join(root, ".tmp/typecheck-"));
    try {
      const filename = path.join(temporary, "contract.py");
      await writeFile(filename, imports + "\n\n" + source);
      // The normal workspace excludes .tmp; explicitly include each temporary contract.
      const project = path.join(temporary, "pyrightconfig.json");
      await writeFile(project, JSON.stringify({
        ...shared,
        include: ["contract.py"],
        exclude: [],
        extraPaths: shared.extraPaths.map(entry => path.resolve(root, entry)),
        venvPath: root,
      }));
      const result = spawnSync(process.execPath, [checker, "--outputjson", "--project", project], {
        cwd: root,
        encoding: "utf8",
        timeout: 60000,
      });
      assert.ifError(result.error);
      assert.equal(result.status, rule ? 1 : 0, result.stdout + result.stderr);
      const report = JSON.parse(result.stdout);
      assert.ok(report.summary.filesAnalyzed > 0, "Type checker did not analyze the contract");
      const errors = report.generalDiagnostics.filter(item => item.severity === "error");
      if (rule) {
        assert.equal(errors.length, 1, result.stdout);
        assert.equal(errors[0].rule, rule, result.stdout);
      } else {
        assert.equal(errors.length, 0, result.stdout);
      }
    } finally {
      await rm(temporary, { recursive: true, force: true });
    }
  });
}
