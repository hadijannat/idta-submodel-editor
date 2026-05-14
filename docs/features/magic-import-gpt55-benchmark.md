# Magic Import GPT-5.5 Benchmark

PR #201 changes the default OpenAI model used by Magic Import from the previous GPT-4o-mini baseline to GPT-5.5. Before the draft is marked ready, reviewers should attach a small live comparison for latency, token usage, and extraction coverage.

The benchmark harness is:

```bash
cd backend
OPENAI_API_KEY=sk-... python scripts/benchmark_magic_import_openai_models.py \
  --models gpt-4o-mini gpt-5.5 \
  --repeats 3 \
  --output .benchmarks/magic-import-openai-models.json
```

For a no-network smoke check of the prompt shape:

```bash
cd backend
python scripts/benchmark_magic_import_openai_models.py --dry-run
```

Review the JSON report for these acceptance points:

- `gpt-5.5` returns candidate sets for the expected paths in the synthetic nameplate sample.
- Median latency and mean token usage are explicitly compared with `gpt-4o-mini`.
- Any latency or token increase is justified by extraction quality or noted as a release tradeoff.
- The report is attached to PR #201 before converting the draft to ready for review.

The OpenAI upgrade guidance used for this PR recommends measuring accuracy, token usage, and latency when moving workloads to GPT-5.5, while preserving the narrow API surface unless there is evidence to broaden it.
