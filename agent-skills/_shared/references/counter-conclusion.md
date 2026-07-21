---
title: Counter-Conclusion Construction
status: experimental
intended_consumers:
  - agent-skills/grill-the-inference
  - agent-skills/action-loop-stagnation
---

# Counter-Conclusion Construction

This reference defines the shared counter-conclusion move and verdict
vocabulary used by Layer A' review protocols. It is a shared reference, not an
agent skill, product runtime prompt, source-evidence record, or gate.

## Boundary

Counter-conclusion construction tests whether a proposed conclusion or next
action is determined by the available packet. It does not prove that the
counter-conclusion is true.

Use it only as immediate review scratchpad unless a separate approved design
allows persistence. Do not store counter-conclusions as source evidence, claim
support, Project Takeaway metadata, or future risk records.

## Claim-Set Use

For claim-set reasoning, use the same load-bearing claims as the original
conclusion:

1. Preserve the original conclusion wording.
2. Identify the load-bearing claims.
3. Reconstruct the warrant that is supposed to connect those claims to the
   conclusion.
4. Attempt the strongest plausible contradictory or materially weaker
   conclusion using the same claims.
5. Discard any counter-conclusion that relies on external facts, ignores a
   decisive claim, or changes the packet.

The verdict remains about support sufficiency:

```text
This evidence set is or is not sufficient to determine this conclusion.
```

## Action-Loop Use

For action-loop stagnation, use the same failure packet instead of the same
claim set:

1. Name the current hypothesis class.
2. Explain why the latest attempts did not advance the task.
3. Construct at least two structurally different next hypotheses or approaches
   from the same failure packet.
4. Prefer hypotheses with an executable verification oracle when one exists.
5. If no executable oracle exists, record why and narrow the task or route to
   human judgment earlier.

The verdict remains about action sufficiency:

```text
The current failure packet is or is not sufficient to choose the next action.
```

## Verdict Vocabulary

- `pass`: the packet supports the current conclusion or next action well enough
  to proceed.
- `underdetermined`: the packet supports multiple materially different
  conclusions or next actions, and the warrant or failure analysis does not
  distinguish which one should be preferred.
- `needs_human_judgment`: the protocol cannot complete the support test because
  the warrant, claim anchors, source context, domain standard, policy boundary,
  executable oracle, or user intent is missing.

For `action-loop-stagnation`, `underdetermined` means the current evidence is
insufficient to choose the next action hypothesis. It does not mean an external
claim has insufficient evidence.

## Output Discipline

When a consuming skill uses this reference, it should report:

- original conclusion or current hypothesis class
- packet used for the test
- counter-conclusion or alternative action hypotheses
- reason invalid attempts were discarded
- verdict
- smallest safe next step

Keep the output small enough for a human reviewer to inspect the reasoning
without reading a long essay.
