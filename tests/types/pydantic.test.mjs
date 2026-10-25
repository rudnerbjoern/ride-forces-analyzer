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
    name: "typed export aspect accepts enum members",
    source: "from ride_forces_analyzer.rendering.model import ExportSettings, VideoAspect\nsettings = AppSettings()\nvideo = ExportSettings(aspect=VideoAspect.PORTRAIT)\n",
    rule: null,
  },
  {
    name: "typed export aspect rejects unconverted strings",
    source: "from ride_forces_analyzer.rendering.model import ExportSettings\nsettings = AppSettings()\nvideo = ExportSettings(aspect='portrait')\n",
    rule: "reportArgumentType",
  },
  {
    name: "typed language accepts enum members",
    source: "from ride_forces_analyzer.i18n import Language\nsettings = AppSettings(language=Language.GERMAN)\n",
    rule: null,
  },
  {
    name: "typed language rejects unconverted string codes",
    source: "settings = AppSettings(language='de')\n",
    rule: "reportArgumentType",
  },
  {
    name: "typed Pydantic constructor accepts valid settings",
    source: "settings = AppSettings(window_width=800, window_title='Custom window')\n",
    rule: null,
  },
  {
    name: "typed Pydantic constructor rejects a string width",
    source: "settings = AppSettings(window_width='800')\n",
    rule: "reportArgumentType",
  },
  {
    name: "frozen Pydantic settings reject static assignment",
    source: "settings = AppSettings()\nsettings.window_width = 800\n",
    rule: "reportAttributeAccessIssue",
  },
];

for (const { name, source, rule } of cases) {
  test(name, async () => {
    await mkdir(path.join(root, ".tmp"), { recursive: true });
    const temporary = await mkdtemp(path.join(root, ".tmp/typecheck-"));
    try {
      const filename = path.join(temporary, "contract.py");
      await writeFile(filename, "from ride_forces_analyzer.config import AppSettings\n\n" + source);
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
