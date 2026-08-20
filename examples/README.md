# ToolGuard examples

- `toolguard_traces.jsonl`: three passing traces for quick evaluation.
- `toolguard_baseline.jsonl`: accepted baseline behavior.
- `toolguard_candidate_regression.jsonl`: intentionally regressed candidate used to demonstrate a release block.

Try:

```bash
python -m toolguard.cli evaluate examples/toolguard_traces.jsonl
python -m toolguard.cli compare examples/toolguard_baseline.jsonl examples/toolguard_candidate_regression.jsonl
```

The second command should exit with status `1` because the candidate regresses routing behavior.
