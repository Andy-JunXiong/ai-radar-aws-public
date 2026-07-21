# Caveat Stripping Calibration Record cs-001

id: cs-001

paper: AlphaFold 3

claim axis: all life's molecules / unprecedented accuracy

CLAIM: "predict the structure and interactions of all life's molecules with unprecedented accuracy"

SOURCE: https://blog.google/innovation-and-ai/products/google-deepmind-isomorphic-alphafold-3-ai-model/

LIMITATION (verbatim): "We note model limitations of AF3 with respect to stereochemistry, hallucinations, dynamics and accuracy for certain targets."

LIMIT SOURCE: https://www.nature.com/articles/s41586-024-07487-w  anchor: `We note model limitations of AF3`

severity: fatal

omitted: yes

verification: single

## Dataset Metadata

Collection: GPT.

Recheck: GPT full-text retrieval + human (Andy) real-search confirmation for cs-009 omitted.

Cross-check: Claude knowledge-supported review + sampled fetch.

Responsibility boundary: cs-001 / cs-005 / cs-009 verbatim limitations were not independently corroborated by Claude due to knowledge or fetch limits. They are marked `single`; if future review finds quotation drift, prioritize these three for traceback.

This record is Layer A' `grill-the-inference` caveat_stripping calibration only. It is not product runtime data, source evidence, claim support, Project Takeaway verification metadata, or a runtime gate output.
