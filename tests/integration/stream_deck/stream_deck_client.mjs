import assert from "node:assert/strict";

import { AnalyzerTransport, endpointPath } from "../../../plugins/stream-deck/src/transport.ts";

const connections = [];
const deadline = setTimeout(() => {
  transport.stop();
  throw new Error("Qt/Node transport interoperability timed out");
}, 10000);

const transport = new AnalyzerTransport(endpointPath(), (message) => {
  const { phase } = JSON.parse(message);
  if (phase === "initial") {
    assert.equal(transport.send('{"command":"restart"}'), true);
  } else if (phase === "restarted") {
    assert.equal(transport.send('{"command":"complete"}'), true);
  } else {
    assert.equal(phase, "complete");
    clearTimeout(deadline);
    transport.stop();
    console.log(JSON.stringify({ connections }));
  }
}, connected => connections.push(connected));

assert.equal(transport.send('{"command":"not queued"}'), false);
transport.start();
