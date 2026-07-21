# Caveat Stripping Calibration Record cs-010

id: cs-010

paper: Imagen

claim axis: new SOTA COCO FID 7.27

CLAIM: "new state-of-the-art COCO FID of 7.27"

SOURCE: https://imagen.research.google/

LIMITATION (verbatim): "Imagen exhibits serious limitations when generating images depicting people."

LIMIT SOURCE: https://imagen.research.google/  anchor: `serious limitations when generating images depicting people`

severity: minor

omitted: no

verification: dual

## Dataset Metadata

Collection: GPT.

Recheck: GPT full-text retrieval + human (Andy) real-search confirmation for cs-009 omitted.

Cross-check: Claude knowledge-supported review + sampled fetch.

Responsibility boundary: cs-001 / cs-005 / cs-009 verbatim limitations were not independently corroborated by Claude due to knowledge or fetch limits. They are marked `single`; if future review finds quotation drift, prioritize these three for traceback.

This record is Layer A' `grill-the-inference` caveat_stripping calibration only. It is not product runtime data, source evidence, claim support, Project Takeaway verification metadata, or a runtime gate output.
