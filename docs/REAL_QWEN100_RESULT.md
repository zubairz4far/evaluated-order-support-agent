# Real Qwen100 Result — ToolGuard v1.0

This document freezes the first full 100-case `agent-reliability-v1` run against the actual published Qwen adapter.

## Runtime

- Base model: `Qwen/Qwen3-1.7B`
- Adapter: `zubairz4far/qwen3-1.7b-tool-calling`
- Provider: `qwen-transformers`
- Hardware: NVIDIA Tesla T4 (Kaggle)
- Generation: deterministic, `do_sample=false`, `max_new_tokens=160`
- Transformers: 5.14.1
- PEFT: 0.19.1
- PyTorch: 2.10.0+cu128
- Elapsed time: 251.817 seconds
- Locked benchmark SHA-256: `d005de66762008999db1a37469231fc5ae0554dad16f0336827265db35dafaa9`

## Result

**Release decision: BLOCK**

- Passed: **78 / 100**
- Overall pass rate: **78.0%**
- Mean evaluator score: **0.92**
- Route accuracy: **86.0%**
- Tool-selection accuracy: **100%**
- Argument exact accuracy: **100%**
- Argument key/value accuracy: **100%**
- Execution success: **100%**
- Prompt-injection category: **15 / 15 (100%)**
- Valid `get_order`: **25 / 25 (100%)**
- Valid `check_inventory`: **25 / 25 (100%)**
- Missing-argument clarification: **10 / 20 (50%)**
- No-tool capability answers: **3 / 15 (20%)**
- Unexpected tool calls on non-tool cases: **10**

The release policy required at least 90% pass rate and zero unexpected tool calls. The candidate therefore remains blocked.

## Failure analysis

The model is strong when a valid tool call is required: all 50 valid tool cases selected the correct tool with exact arguments, and all 15 prompt-injection cases were rejected correctly.

The dominant weakness is **routing around non-tool behavior**:

1. On missing-identifier requests, the model often emitted a tool call instead of asking for the missing order ID or SKU. Ten of twenty clarification cases failed.
2. On general capability/help questions, the model frequently produced a clarification-style response instead of a direct answer. Twelve of fifteen no-tool-answer cases failed.

This result is intentionally frozen as a failed release candidate. The locked test set must not be used for iterative prompt/training tuning. Any corrective model should be developed on separate training/development data and then evaluated once against a new untouched final gate.

## Evidence

Machine-readable evidence: [`reports/real_qwen_agent_reliability_v1.json`](../reports/real_qwen_agent_reliability_v1.json)

The earlier 12-case guarded-agent benchmark remains valid for that narrower suite, but it must not be substituted for this broader 100-case reliability result.
