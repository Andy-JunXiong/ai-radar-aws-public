# Caveat Stripping Calibration Record cs-006

id: cs-006

paper: GPT-4

claim axis: 40% more likely factual than GPT-3.5

CLAIM: "40% more likely to produce factual responses than GPT-3.5"

SOURCE: https://openai.com/index/gpt-4/

LIMITATION (verbatim): "it still is not fully reliable"

LIMIT SOURCE: https://openai.com/index/gpt-4-research/  anchor: `not fully reliable`

severity: fatal

omitted: no

verification: dual

## Dataset Metadata

Collection: GPT.

Recheck: GPT full-text retrieval + human (Andy) real-search confirmation for cs-009 omitted.

Cross-check: Claude knowledge-supported review + sampled fetch.

Responsibility boundary: cs-001 / cs-005 / cs-009 verbatim limitations were not independently corroborated by Claude due to knowledge or fetch limits. They are marked `single`; if future review finds quotation drift, prioritize these three for traceback.

This record is Layer A' `grill-the-inference` caveat_stripping calibration only. It is not product runtime data, source evidence, claim support, Project Takeaway verification metadata, or a runtime gate output.
