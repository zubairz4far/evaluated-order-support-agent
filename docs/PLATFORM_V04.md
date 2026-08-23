# ToolGuard v0.4 platform hardening

ToolGuard v0.4 keeps the existing deterministic trace evaluation, replay, benchmark registry, release policies, observability, and guarded order-agent integration, then adds an explicit runtime security and deployment boundary.

## Security boundary

All routes under `/api/` require the `X-API-Key` header.

- The server key is configured through `TOOLGUARD_API_KEY`.
- Missing or incorrect client credentials return HTTP `401`.
- If the server has no API key configured, protected routes fail closed with HTTP `503` rather than silently becoming public.
- `/health`, `/`, and `/dashboard` remain reachable for liveness and the recruiter-facing UI.
- The dashboard requests the API key in the browser and stores it only in session storage for the current tab/session.
- Key comparison uses `secrets.compare_digest`.

This is intentionally a shared-key v0.4 boundary, not enterprise identity. Production deployments should normally terminate TLS before ToolGuard and replace or front the shared key with workload identity, OIDC, RBAC, secret rotation, and network policy.

## Container

`Dockerfile` builds a Python 3.12 image, installs the platform and observability extras, and runs as non-root UID `10001`.

```bash
docker build -t toolguard:0.4.0 .
docker run --rm \
  -e TOOLGUARD_API_KEY=change-me \
  -p 8000:8000 \
  toolguard:0.4.0
```

Check liveness:

```bash
curl http://localhost:8000/health
```

Protected API:

```bash
curl -H 'X-API-Key: change-me' http://localhost:8000/api/providers
```

## Docker Compose + PostgreSQL

Compose runs ToolGuard with PostgreSQL-backed trace persistence.

```bash
export TOOLGUARD_API_KEY='replace-with-a-secret'
docker compose up --build
```

Compose refuses to resolve the ToolGuard service when `TOOLGUARD_API_KEY` is missing.

The PostgreSQL volume persists trace records across container restarts. v0.4 still uses the existing startup schema initializer; replacing it with an explicit migration system remains a documented next hardening step.

## Kubernetes

`k8s/deployment.yaml` provides a conservative single-replica deployment with:

- non-root pod/container identity;
- CPU and memory requests/limits;
- readiness and liveness probes;
- API key and database DSN sourced from a Kubernetes Secret;
- `Recreate` deployment strategy.

Create the secret before applying the manifest:

```bash
kubectl create secret generic toolguard-secrets \
  --from-literal=api-key='replace-with-a-secret' \
  --from-literal=database-url='postgresql://USER:PASSWORD@HOST:5432/DB'

kubectl apply -f k8s/deployment.yaml
```

The checked-in image reference is a local/example image name, not a claim that a public registry image has been published. Replace it with the image produced by your registry pipeline.

The manifest intentionally uses one replica because benchmark definitions and some platform state are process-local in v0.4. Horizontal scaling should wait for persistent benchmark/release-policy state and concurrency controls.

## CI acceptance boundary

The ToolGuard Gate now verifies:

1. package compilation;
2. all ToolGuard unit/platform tests;
3. deterministic fixture evaluation;
4. telemetry summarization;
5. real guarded order-agent replay evaluation;
6. intentional candidate regression is blocked;
7. Docker Compose configuration validates with an API key;
8. the Docker image builds;
9. a real container reaches `/health`;
10. unauthenticated `/api/providers` returns `401`;
11. authenticated `/api/providers` succeeds and exposes the guarded agent provider.

This is CI/runtime integration evidence, not a claim of a live production deployment or production SLOs.

## Remaining hardening

- replace startup PostgreSQL schema creation with versioned migrations;
- persist benchmark definitions and release-policy history;
- use a worker queue for expensive real-model replay runs;
- add distributed concurrency/idempotency controls before horizontal scaling;
- add sustained load/soak testing;
- replace the shared API key with production identity/RBAC where required.
