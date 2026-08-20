# ToolGuard

ToolGuard is the reusable reliability-evaluation layer extracted from the evaluated order-support agent project.

Core capabilities in v0:

- typed agent traces
- deterministic route/tool/argument/confirmation scoring
- execution-failure detection
- candidate-vs-baseline regression comparison
- CLI exit codes suitable for CI release gates
- provider-agnostic design

See [`docs/TOOLGUARD.md`](../docs/TOOLGUARD.md) for architecture and usage.
