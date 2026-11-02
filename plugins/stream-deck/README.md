# Stream Deck plugin stub

Private TypeScript workspace using the official SDK. One plugin serves Plus and
Neo; device-specific actions and profiles remain planned.

Use the repository's [Windows setup](../../docs/development/SETUP.md), which installs
workspace dependencies from the root npm lockfile. Run from the repository root:

```powershell
npm run test:stream-deck
npm run typecheck --workspace plugins/stream-deck
npm run build --workspace plugins/stream-deck
uv run --locked pytest tests/support/test_stream_deck.py tests/support/test_control_contract.py
```

Node tests build TypeScript and cover the SDK bootstrap and local client discovery,
state exchange and reconnects. Python tests additionally verify real Qt/Node
interoperability. Shared protocol examples validate the Python wire models and
TypeScript command/feedback types. Both run offline without a device or Stream Deck software.
Build output is ignored under
`plugins/stream-deck/dist/`; `src/index.ts` is the SDK connection entry point.

VS Code's Testing view discovers these tests through the recommended `node:test`
runner extension and builds TypeScript before each run. See [editor setup](../../docs/development/SETUP.md#vs-code-and-test-explorer).

The [CI selector](../../docs/development/CI.md#routing-and-required-gate) runs plugin
tests for affected PR changes and always for releases and full CI.

The [transport components](../../docs/architecture/06_runtime_view.md#stream-deck-transport)
are reusable; application/SDK action wiring, manifest, device assets and profiles
remain planned. The stub is not an installable plugin package.
The [control contract](../../docs/architecture/06_runtime_view.md#stream-deck-control-contract)
defines application messages separately from transport authentication.
See the [agreed requirements](../../docs/requirements/STREAM_DECK.md).
