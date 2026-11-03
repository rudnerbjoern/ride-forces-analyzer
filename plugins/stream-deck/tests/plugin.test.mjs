import assert from "node:assert/strict";
import test from "node:test";

import { startPlugin } from "../dist/plugin.js";

test("connects to the supplied Stream Deck host", async (context) => {
  const connect = context.mock.fn(async () => {});

  await startPlugin({ connect });

  assert.equal(connect.mock.callCount(), 1);
});

test("propagates host connection failures to the caller", async () => {
  const failure = new Error("Host connection unavailable");

  await assert.rejects(startPlugin({
    async connect() {
      throw failure;
    },
  }), failure);
});
