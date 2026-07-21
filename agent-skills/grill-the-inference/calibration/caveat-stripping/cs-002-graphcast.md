# Caveat Stripping Calibration Record cs-002

id: cs-002

paper: GraphCast

claim axis: 10-day unprecedented accuracy

CLAIM: "10-day weather predictions at unprecedented accuracy in under one minute"

SOURCE: https://deepmind.google/blog/graphcast-ai-model-for-faster-and-more-accurate-global-weather-forecasting/

LIMITATION (verbatim): "One key limitation of our approach is in how uncertainty is handled."

LIMIT SOURCE: ar5iv 2212.12794  anchor: `uncertainty is handled`

severity: fatal

omitted: yes

verification: dual

## Dataset Metadata

Collection: GPT.

Recheck: GPT full-text retrieval + human (Andy) real-search confirmation for cs-009 omitted.

Cross-check: Claude knowledge-supported review + sampled fetch.

Responsibility boundary: cs-001 / cs-005 / cs-009 verbatim limitations were not independently corroborated by Claude due to knowledge or fetch limits. They are marked `single`; if future review finds quotation drift, prioritize these three for traceback.

This record is Layer A' `grill-the-inference` caveat_stripping calibration only. It is not product runtime data, source evidence, claim support, Project Takeaway verification metadata, or a runtime gate output.
