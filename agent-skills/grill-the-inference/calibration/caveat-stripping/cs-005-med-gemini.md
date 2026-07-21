# Caveat Stripping Calibration Record cs-005

id: cs-005

paper: Med-Gemini

claim axis: SOTA on 10/14 medical benchmarks

CLAIM: "state-of-the-art performance on 10 out of 14 medical benchmarks"

SOURCE: https://research.google/blog/advancing-medical-ai-with-med-gemini/

LIMITATION (verbatim): "further rigorous evaluation will be crucial before real-world deployment"

LIMIT SOURCE: arxiv 2404.18416  anchor: `before real-world deployment`

severity: minor

omitted: no

verification: single

## Dataset Metadata

Collection: GPT.

Recheck: GPT full-text retrieval + human (Andy) real-search confirmation for cs-009 omitted.

Cross-check: Claude knowledge-supported review + sampled fetch.

Responsibility boundary: cs-001 / cs-005 / cs-009 verbatim limitations were not independently corroborated by Claude due to knowledge or fetch limits. They are marked `single`; if future review finds quotation drift, prioritize these three for traceback.

This record is Layer A' `grill-the-inference` caveat_stripping calibration only. It is not product runtime data, source evidence, claim support, Project Takeaway verification metadata, or a runtime gate output.
