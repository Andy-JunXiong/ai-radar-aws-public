# Caveat Stripping Calibration Record cs-008

id: cs-008

paper: DINOv2

claim axis: match or surpass standard approach

CLAIM: "match or surpass the standard approach used in the field"

SOURCE: https://ai.meta.com/blog/dino-v2-computer-vision-self-supervised-learning/

LIMITATION (verbatim): "This shows that our model is still biased toward Western countries."

LIMIT SOURCE: arxiv 2304.07193  anchor: `biased toward Western countries`

severity: minor

omitted: yes

verification: dual

## Dataset Metadata

Collection: GPT.

Recheck: GPT full-text retrieval + human (Andy) real-search confirmation for cs-009 omitted.

Cross-check: Claude knowledge-supported review + sampled fetch.

Responsibility boundary: cs-001 / cs-005 / cs-009 verbatim limitations were not independently corroborated by Claude due to knowledge or fetch limits. They are marked `single`; if future review finds quotation drift, prioritize these three for traceback.

This record is Layer A' `grill-the-inference` caveat_stripping calibration only. It is not product runtime data, source evidence, claim support, Project Takeaway verification metadata, or a runtime gate output.
