# Real-model guarded-agent benchmark

## Result

| Item | Value |
|---|---:|
| Adapter | `zubairz4far/qwen3-1.7b-tool-calling` |
| Base model | `Qwen/Qwen3-1.7B` |
| Hardware | Kaggle NVIDIA T4 GPU |
| Cases | 12 |
| Passed | 12 |
| Guarded-agent accuracy | **100%** |
| Runtime | 31.19 seconds |
| Decoding | Deterministic (`do_sample=False`) |

The final benchmark covers complete `get_order` and `check_inventory` requests, missing-identifier clarification, ordinary no-tool questions, unavailable-tool injection, and system-prompt extraction attempts.

## Why the guard layer matters

An earlier diagnostic run of the raw integration passed 9/12 cases (75%). It exposed three concrete boundary failures:

1. The model supplied `sku="unknown"` when no SKU was provided.
2. It attempted to invent an unavailable `process_refund` tool.
3. A prompt-extraction request was not classified as a rejection.

The production-shaped agent addressed these at the execution boundary rather than claiming the model itself had improved:

- identifiers must be grounded in the user's request;
- sentinel values such as `unknown`, `null`, and `missing` cannot execute;
- only allow-listed tools can run;
- injection requests are rejected before inference-driven execution;
- rejection statuses are normalized for evaluation.

The final 12/12 result is therefore a **guarded-agent score**, not a claim of perfect raw-model accuracy.

## Outcome distribution

| Expected behavior | Cases | Final outcome |
|---|---:|---:|
| Valid read-only tool execution | 4 | 4/4 |
| Missing-identifier clarification | 4 | 4/4 |
| Ordinary no-tool answer | 2 | 2/2 |
| Injection rejection | 2 | 2/2 |

## Evidence and reproduction

- Machine-readable case results: [`reports/real_model_benchmark_report.json`](../reports/real_model_benchmark_report.json)
- Run locally or on a GPU notebook: `python -m order_agent.eval --model transformers`
- No customer data, credentials, or live commerce mutations are used.

This 12-case suite is an integration benchmark. The model repository's separate 150-case locked evaluation remains the stronger model-level quality measurement.
