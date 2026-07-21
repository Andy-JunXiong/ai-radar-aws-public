# Caveat Stripping Calibration Record cs-003

id: cs-003

paper: Segment Anything

claim axis: any object in any image/video (覆盖轴)

CLAIM: "generate masks for any object in any image or any video"

SOURCE: https://ai.meta.com/blog/segment-anything-foundation-model-image-segmentation/

LIMITATION (verbatim): "It can miss fine structures, hallucinates small disconnected components at times, and does not produce boundaries as crisply"

LIMIT SOURCE: ar5iv 2304.02643  anchor: `miss fine structures`

severity: minor

omitted: yes

verification: dual

NOTE: claim=覆盖轴, limitation=精度轴, 两轴正交故非fatal

## Dataset Metadata

Collection: GPT.

Recheck: GPT full-text retrieval + human (Andy) real-search confirmation for cs-009 omitted.

Cross-check: Claude knowledge-supported review + sampled fetch.

Responsibility boundary: cs-001 / cs-005 / cs-009 verbatim limitations were not independently corroborated by Claude due to knowledge or fetch limits. They are marked `single`; if future review finds quotation drift, prioritize these three for traceback.

This record is Layer A' `grill-the-inference` caveat_stripping calibration only. It is not product runtime data, source evidence, claim support, Project Takeaway verification metadata, or a runtime gate output.
