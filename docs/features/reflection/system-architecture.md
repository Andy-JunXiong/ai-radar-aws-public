# Reflection System Architecture

This document defines the division of responsibility between deep reflections
and high-frequency reflection signals. Deep reflections are curated manually
in a private Markdown repository. High-frequency signals remain inside AI
Radar. Matching connects the two without collapsing their different rhythms.

## 1. Two reflection rhythms

| Dimension | High-frequency reflection | Deep reflection |
|---|---|---|
| Frequency | Several times per day | Roughly every few days |
| Trigger | Signals, Agent Watch, routine intake | Deep discussion, changed judgment, rebuilt framework |
| Density | Low | High |
| Automation tolerance | High | Low; manual curation is part of learning |
| Selection | Scoring and filtering are useful | Only the author can judge long-term value |
| System of record | AI Radar | Private Markdown repository |
| Retention | May expire | Long-lived |

A single workflow cannot serve both rhythms well. Automating deep reflection
flattens disagreement and weakens cognitive ownership. Applying deep-reflection
standards to every signal creates an unsustainable workload.

Manual compression is therefore a learning operation, not clerical work:

```text
Raw discussion -> deliberate compression -> structured reflection ->
ability to explain and defend the judgment
```

If the author cannot produce the reflection, the idea probably has not been
understood deeply enough.

## 2. Architecture

```text
Private thinking and source material
          |
Manual curation
          v
Private reflection repository (source of truth)
          |
Read-only incremental sync
          v
AI Radar reflection index (metadata and links)
          |
Matching against signals, topics, and projects
          v
Reflection views and contextual cross-references
```

Data flows from the reflection repository into AI Radar. AI Radar does not
write reflection content back to the source repository.

## 3. Non-negotiable principles

### The private repository is the source of truth

- Deep reflection content lives in the private repository.
- AI Radar is an index, query, and matching layer.
- A failure or replacement of AI Radar must not destroy reflection history.

### AI Radar is read-only for deep reflections

- AI Radar never edits or commits reflection content.
- Changes are made with the author's normal editor and repository workflow.
- The next sync detects additions and updates.

### Markdown remains the durable format

- Use Markdown plus YAML frontmatter.
- Avoid a proprietary-only representation.
- Keep the archive readable without AI Radar or a specific database.

## 4. Repository convention

```text
reflections/
├── README.md
├── 2026/
│   ├── 04/
│   │   ├── 2026-04-12-ai-radar-evaluation.md
│   │   └── 2026-04-15-agent-memory.md
│   └── 05/
└── archives/
```

Use `YYYY-MM-DD-kebab-slug.md`. The date represents when the reflection
occurred, not when the file was edited.

### Required frontmatter

```yaml
---
id: refl_2026-04-12_ai-radar-evaluation
timestamp: 2026-04-12T19:30:00+10:00
source: claude_chat
title: AI Radar positioning and business-model review
tags:
  - ai-radar
  - business-model
  - cognitive-tools
duration_minutes: 160
depth: deep
self_correction_count: 3
related:
  - refl_2026-04-08_agent-memory
raw_archive: archives/2026-04-12-claude-chat.html
---
```

Required fields are `id`, `timestamp`, `source`, `title`, and `tags`. Tags stay
free-form initially so real usage can reveal the right vocabulary before a
taxonomy is imposed.

### Recommended content structure

```markdown
# Title

## Compressed Core
- Judgment worth retaining

## Cognitive Skeleton
Stage 1 -> Stage 2 -> Stage 3

## Stance Evolution
- Previous judgment -> updated judgment; trigger: ...

## Corrections and Retained Judgments
### Corrections
- Topic: previous view -> revised view

### Retained
- Topic: judgment that survived challenge

## Key Insights
- Insight with attribution: user_origin | ai_prompted | co_created | rebuttal

## Unresolved Questions
- Open question

## Meta Observations
- Observation about the reasoning process
```

The minimum useful structure is Compressed Core plus Corrections and Retained
Judgments. Attribution preserves ownership and prevents the system from
confusing a model suggestion with the author's conclusion.

## 5. Admission standard

A reflection is a good candidate for the durable repository when it:

- comes from sustained, substantive thinking
- contains a meaningful change or defense of judgment
- can be compressed into several durable insights
- is worth deliberate manual editing
- may affect future decisions

Routine fact lookup, task execution, unprocessed emotion, generic summaries,
and material replaceable by an ordinary signal should stay out. When the
boundary is unclear, prefer not to add weak material to the durable archive.

## 6. AI Radar responsibilities

AI Radar may:

- pull new or changed reflection metadata
- maintain a lightweight index
- match signals and topics to related reflections
- provide timeline and tag views
- show contextual links in Radar and project surfaces

AI Radar must not:

- auto-author deep reflections
- edit the source files
- treat reflection content as external factual evidence
- impose a premature taxonomy
- write back to the private repository

## 7. Delivery phases

1. Validate read-only connectivity.
2. Build incremental ingestion and indexing.
3. Add reflection timeline and detail views.
4. Add tag-based matching.
5. Consider semantic matching only if tag matching is demonstrably inadequate.
6. Add longitudinal cross-referencing only after the archive is large enough.

Stop or reconsider when the archive remains unused, the reflection UI is not
opened after delivery, or matching quality is consistently poor. A stop signal
is product evidence, not project failure.

## 8. Privacy boundary

The public repository contains architecture and code only. It must not contain
the private reflection repository, raw conversations, personal reflection
content, access tokens, or synchronized runtime records.

---

Public English edition, 2026-07-21.
