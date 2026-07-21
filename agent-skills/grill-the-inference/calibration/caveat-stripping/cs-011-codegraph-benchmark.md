# Caveat Stripping Calibration Record cs-011

id: cs-011

case: CodeGraph and codebase-memory-mcp benchmark framing

claim axis: agent efficiency benchmark generalized into tool fact

CLAIM: "Code graph tools produce dramatically fewer tool calls / faster answers / lower token cost."

SOURCE: secondary four-tool comparison brief + project README benchmark sections

PRIMARY-SOURCE CHECK:
- CodeGraph current README reports an author-run benchmark across 7 open-source repos, one architecture question per repo, 4 runs per arm, median reported.
- Current CodeGraph headline is 58% fewer tool calls and 22% faster, with large per-repo variance; the checked README did not support the brief's 92% fewer tool calls / 71% faster numbers.
- CodeGraph itself caveats that token and cost savings are scale-dependent and noisy per query.
- codebase-memory-mcp benchmark framing also required baseline and provenance caveats; the arXiv/preprint numbers did not support treating "99% / 120x" as a general tool fact.

LIMITATION:
Benchmark results are scoped by model, repo set, question type, baseline, run count, and whether the evaluator is independent or author-reported. Removing those conditions turns a narrow measurement into a general capability claim.

LIMIT SOURCE:
- https://github.com/colbymchenry/codegraph
- https://arxiv.org/abs/2603.27277

severity: high

omitted: yes

verification: primary-source README + source-linked paper check

VERDICT: caveat_stripping

recommended rewrite:
"CodeGraph reports author-run benchmark improvements on 7 repos for one architecture question per repo; current headline is 58% fewer tool calls and 22% faster. Treat this as scoped design evidence, not a general efficiency law."

AI Radar boundary:
This record is Layer A' `grill-the-inference` caveat_stripping calibration only. It is not product runtime data, source evidence, claim support, Project Takeaway verification metadata, or a runtime gate output.
