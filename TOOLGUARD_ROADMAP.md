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

- [ ] convert order-agent audit events into ToolGuard traces
- [ ] evaluate the existing locked order-support benchmark through ToolGuard
- [ ] persist a machine-readable accepted baseline
- [ ] generate failure-taxonomy summaries

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
