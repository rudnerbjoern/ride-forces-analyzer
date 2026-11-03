import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { nativeVersion, syncVersion, verifyVersion } from "../scripts/version.mjs";

const manifestPath = "plugins/stream-deck/io.github.rudnerbjoern.ride-forces-analyzer.sdPlugin/manifest.json";

test("plugin versions use independent numeric package and Elgato formats", () => {
  assert.equal(nativeVersion("1.10.2"), "1.10.2.0");
  for (const value of ["1.2", "1.2.3.4", "v1.2.3", "1.2.3-beta", "01.2.3", "1.65536.0"]) {
    assert.throws(() => nativeVersion(value), /three numeric components/);
  }
});

test("development commits share one version while release tags require an increase for changed plugin data", () => {
  const root = mkdtempSync(fileURLToPath(new URL("../../../.tmp/plugin-version-", import.meta.url)));
  const git = (...args) => execFileSync("git", ["-c", "user.name=Version Test", "-c", "user.email=version@example.invalid", ...args], {cwd:root, stdio:"pipe"});
  const write = (name, value) => { mkdirSync(path.dirname(path.join(root,name)), {recursive:true}); writeFileSync(path.join(root,name),value); };
  const metadata = version => {
    write("plugins/stream-deck/package.json", JSON.stringify({version}));
    write("package-lock.json", JSON.stringify({packages:{"plugins/stream-deck":{version}}}));
    syncVersion(root);
  };
  const commit = () => {git("add", ".");git("commit", "-qm", "fixture");};
  try {
    git("init", "-q", "-b", "version-test");
    write(manifestPath, JSON.stringify({Version:"0.1.0.0", Nodejs:{Version:"24"}}));
    metadata("0.1.0");
    write("plugins/stream-deck/src/example.ts", "original");commit();
    assert.equal(verifyVersion(root), "0.1.0.0");
    write("plugins/stream-deck/src/example.ts", "changed");
    assert.equal(verifyVersion(root), "0.1.0.0");commit();
    write("plugins/stream-deck/src/example.ts", "still developing");commit();
    assert.equal(verifyVersion(root), "0.1.0.0");
    git("tag", "v1.0.0");
    assert.equal(verifyVersion(root), "0.1.0.0");
    assert.deepEqual(JSON.parse(readFileSync(path.join(root,manifestPath))).Nodejs, {Version:"24"});
    write("plugins/stream-deck/src/example.ts", "changed again");commit();
    assert.throws(() => verifyVersion(root), /without a version increase/);
    git("tag", "v1.0.1"); // Release CI must not accept an unchanged version just because HEAD is tagged.
    assert.throws(() => verifyVersion(root), /without a version increase/);
    git("tag", "-d", "v1.0.1");
    write("plugins/stream-deck/README.md", "Documentation only");commit();
    assert.throws(() => verifyVersion(root), /without a version increase/);
    metadata("0.1.1");commit();
    assert.equal(verifyVersion(root), "0.1.1.0");
    write("plugins/stream-deck/src/example.ts", "more work for the same release");commit();
    assert.equal(verifyVersion(root), "0.1.1.0");
    git("tag", "v1.1.0rc1");
    assert.equal(verifyVersion(root), "0.1.1.0");
    write("plugins/stream-deck/README.md", "Updated documentation only");
    write("plugins/stream-deck/tests/example.mjs", "Test only");
    assert.equal(verifyVersion(root), "0.1.1.0");
    write("plugins/stream-deck/devices/new.json", "{}");
    assert.throws(() => verifyVersion(root), /without a version increase/);
    rmSync(path.join(root,"plugins/stream-deck/devices/new.json"));
    write("plugins/stream-deck/README.md", "Released documentation only");commit();
    assert.equal(verifyVersion(root), "0.1.1.0");
    metadata("0.1.0");
    assert.throws(() => verifyVersion(root), /without a version increase/);
    metadata("0.1.1");
    write(manifestPath, JSON.stringify({Version:"9.0.0.0"}));
    assert.throws(() => verifyVersion(root), /manifest version is out of sync/);
    syncVersion(root);
    write("package-lock.json", JSON.stringify({packages:{"plugins/stream-deck":{version:"0.1.0"}}}));
    assert.throws(() => verifyVersion(root), /package-lock version is out of sync/);
    metadata("0.1.2");commit();
    git("tag", "v1.1.0");
    assert.equal(verifyVersion(root), "0.1.2.0");
    write("plugins/stream-deck/src/example.ts", "changes after stable release");
    assert.throws(() => verifyVersion(root), /without a version increase/);
  } finally { rmSync(root,{recursive:true,force:true}); }
});
