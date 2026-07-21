# Grill The Inference Calibration Notes

Use this reference only when `grill-the-inference` is being used to calibrate
future `composition_underdetermination_gate` samples.

Keep a small sample record outside the runtime evidence path. Capture:

- source packet or insight ID
- `packet_scope`: the exact material fed into the protocol for this run, such
  as "announcement text only", "announcement + full source paper", or
  "announcement + paper + secondary coverage"
- verdict
- whether the counter-conclusion was valid, invalid, or not attemptable
- likely false-positive or false-negative risk
- human reviewer note, when available

`packet_scope` distinguishes a genuine protocol miss from a `not_checkable`
caused by material simply not being in the packet, and makes each record
reproducible.

Calibration notes are process evidence about the protocol. They are not claim
support, source evidence, Project Takeaway verification metadata, product
runtime data, or runtime gate output.
