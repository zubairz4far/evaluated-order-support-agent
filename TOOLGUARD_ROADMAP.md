# ToolGuard roadmap

## v0 — core reliability engine

- [x] typed trace schema
- [x] deterministic evaluators
- [x] regression comparison
- [x] CLI release gate
- [x] unit/CLI tests
- [x] dedicated GitHub Actions gate
- [x] passing and regressed example fixtures

## v0.1 — real-agent adapter

- [x] convert order-agent audit events into ToolGuard traces
- [x] evaluate the existing order-support benchmark through ToolGuard
- [x] persist a machine-readable accepted baseline
- [x] generate failure-taxonomy summaries

Verified replay baseline: **12/12 passed (100%)** with 1.0 route, tool-selection, exact-argument, KV-argument, confirmation, execution, and no-tool accuracy. The integration also exposed and fixed a refund parser bug where an order ID could be mistaken for the refund amount.

## v0.2 — observability

- [ ] OpenTelemetry spans
- [ ] PostgreSQL trace store
- [ ] latency/token/cost aggregation
- [ ] replay IDs and candidate comparison API

## v0.3 — platform

- [ ] FastAPI service
- [ ] benchmark registry
- [ ] web dashboard
- [ ] model/provider adapters
- [ ] CI release policy configuration
