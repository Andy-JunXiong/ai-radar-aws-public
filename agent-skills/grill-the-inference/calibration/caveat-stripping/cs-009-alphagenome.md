# Caveat Stripping Calibration Record cs-009

id: cs-009

paper: AlphaGenome

claim axis: SOTA across genomic prediction benchmarks

CLAIM: "state-of-the-art performance across a wide range of genomic prediction benchmarks"

SOURCE: https://deepmind.google/blog/alphagenome-ai-for-better-understanding-the-genome/

LIMITATION (verbatim): "We have not yet benchmarked the model on personal genome prediction, which is a known weakness of models in this space"

LIMIT SOURCE: https://www.nature.com/articles/s41586-025-10014-0  anchor: `personal genome prediction`

severity: minor

omitted: no

verification: single

NOTE: omitted=no 经 Andy 实搜确认博客 Current limitations 段含此限制

## Dataset Metadata

Collection: GPT.

Recheck: GPT full-text retrieval + human (Andy) real-search confirmation for cs-009 omitted.

Cross-check: Claude knowledge-supported review + sampled fetch.

Responsibility boundary: cs-001 / cs-005 / cs-009 verbatim limitations were not independently corroborated by Claude due to knowledge or fetch limits. They are marked `single`; if future review finds quotation drift, prioritize these three for traceback.

This record is Layer A' `grill-the-inference` caveat_stripping calibration only. It is not product runtime data, source evidence, claim support, Project Takeaway verification metadata, or a runtime gate output.
