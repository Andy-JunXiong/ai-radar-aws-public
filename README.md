# AI Radar

AI Radar is an AI-native intelligence system for tracking the AI ecosystem and turning external signals into structured, decision-relevant intelligence.

Core pipeline:

```text
Signal -> Insight -> Trend -> Strategic Intelligence
```

The product is extending that pipeline into a lightweight learning loop:

```text
Strategic Intelligence -> Decision -> Review -> Learning
```

AI Radar is not a generic news reader, generic knowledge-management tool, Obsidian replacement, or GitHub project-management system. It is an intelligence engine built to help a user detect meaningful AI ecosystem signals early, understand why they matter, map them to active projects, and keep weak evidence from becoming overconfident downstream action.

## Current Product Status

AI Radar is live and usable.

Production surfaces:

- Frontend: `https://app.ai-radar-lab.com`
- Backend API: `https://api.ai-radar-lab.com`

Working product paths include:

- Signals
- Radar / daily intelligence summaries
- Workspace
- Project Takeaways
- Final Takeaway confirmation artifacts
- Knowledge Synthesis
- Subscriptions
- Manual Upload / Manual Intelligence
- AI Agent Watch
- Friction Signals
- Reflections
- Project Trajectory / Review history
- Dev Inbox / coding-agent handoff drafts

## What AI Radar Does

### Signal Intelligence

AI Radar collects external AI ecosystem signals, normalizes them, classifies topics, scores importance, and preserves source metadata. Signals can come from RSS-style feeds, official announcements, GitHub/Hacker News/Product Hunt collectors, and manual uploads.

### Insight Generation

Signals are turned into structured interpretations that explain why a signal matters, how it maps to projects, and what kind of claim is being made. The system distinguishes direct observation, supported interpretation, inferred relevance, and speculative claims.

### Strategic Synthesis

AI Radar synthesizes signals across time so the product does not collapse into a feed of isolated items. Radar outputs and topic summaries help identify momentum, rising themes, and decision-relevant patterns.

### Project Relevance

Signals can be mapped to active projects such as AI Radar itself, GLAP, AI Cognitive OS, Trajectory Memory, and AI Property Intelligence. Project matching uses project descriptions, tags, stored context, GitHub context snapshots, manual project notes, and prior intelligence artifacts.

### Project Takeaways

Project Takeaways are the main review, watch, action, and learning surface. They convert intelligence into reviewable project-level judgment objects. Confirmed takeaways, watch states, action states, ReviewRecords, CalibrationEvents, and trajectory events form the action-learning loop.

### Final Takeaways

Signal Detail can turn a Completion Note into an Andy-confirmed Final Takeaway
artifact by freezing a Review Bundle snapshot first. This creates durable
confirmation provenance without automatically creating a Project Review
candidate or bypassing verification gates.

Review Bundle snapshots can include an External Synthesis Source from paste,
markdown, plaintext, or HTML upload. This material is stored as review context,
not verified external evidence, and confirmed artifacts restore the immutable
snapshot on reload.

After confirmation, the operator can explicitly send the Final Takeaway to
Project Review through the `confirmed_final_takeaway` provider. That handoff
creates a Review Inbox candidate only through the normal Project Takeaway
candidate policy/write path; low-risk Action and strong recommendation remain
blocked unless a separate reviewed path allows them.

### Verification and Evidence Boundaries

AI Radar does not automatically prove that signals are true. It classifies evidential status and uses that classification to control downstream action eligibility.

Important rules:

- Weak evidence can be useful for relevance, but it should not become an automatic action.
- Empty verification metadata must not be labeled as verified insight.
- `blocked_downstream_actions` are hard gates for automatic Project Takeaway and low-risk Action paths.
- Human override must be explicit, auditable, and exceptional.
- Reflection content is cognitive context, not external factual evidence unless an explicit evidence-conversion path exists.
- Rejected or dismissed review history can provide bounded caution context for future work, but it is not source evidence or claim support.

### Reflection

Reflection is a long-horizon cognitive layer. GitHub-backed reflections can be indexed and browsed, but AI Radar should not become the primary authoring source for deep reflection content.

Reflection polish review keeps assistant-polished reflection drafts behind a
human before/after checklist. Polished drafts are review context only until a
separate reflection save path is used; they are not evidence, Project
Takeaways, or Action eligibility signals.

### Manual Intelligence

Manual Upload supports PDF/image/text-style source analysis and recovers manual-session-derived signal context. This lets AI Radar ingest important user-provided material even when it did not originate in the automated collector pipeline.

### AI Agent Watch

AI Agent Watch monitors agent-related repositories and ecosystem signals through GitHub, Hacker News, Product Hunt, normalization, scoring, merge flow, and product surfaces. It is evolving from discovery-only monitoring toward lightweight repo tracking.

### Friction Signals

Friction Signals captures pain points, adoption barriers, workflow friction, and developer/user complaints from sources such as GitHub and Hacker News, then maps them into opportunity-oriented intelligence.

### Dev Inbox

Dev Inbox is a lightweight development intake surface for AI Radar itself. It captures scoped bugs, product ideas, and coding-agent handoff drafts, while keeping actual implementation in local Codex, VS Code, Codex Cloud, GitHub PRs, and CI rather than turning AI Radar into a browser IDE.

## Architecture At A Glance

Main layers:

1. Collection and ingestion
   - external signal collectors
   - manual uploads
   - source-specific normalization

2. Signal and intelligence processing
   - topic classification
   - scoring
   - insight generation
   - trend synthesis
   - project relevance mapping

3. Quality and control
   - model routing
   - execution policy
   - context strategy
   - output validation
   - verification and blocked-action gates
   - prompt / skill registry discipline

4. Product surfaces
   - Signals
   - Radar Summary
   - Workspace
   - Project Takeaways
   - Knowledge
   - Manual Upload
   - Agent Watch
   - Friction Signals
   - Reflections
   - Dev Inbox

5. Action and learning loop
   - decision candidates
   - review inbox
   - watch/action follow-up
   - ReviewRecords
   - CalibrationEvents
   - trajectory timeline
   - bounded caution context from rejected/dismissed review history

## Technical Shape

Major technologies and runtime patterns:

- Python
- FastAPI backend
- Next.js frontend
- JSON-backed local/state artifacts
- AWS ECS backend deployment
- S3 + CloudFront frontend deployment
- provider-routed LLM execution
- model routing and execution policy
- prompt registry and skill-style prompt contracts

Important entrypoints:

- Backend API: `backend/app/main.py`
- Backend routes: `backend/app/routes/`
- Backend services: `backend/app/services/`
- Frontend app: `frontend/app/`
- Daily ingestion / orchestration: `app/main_summary_v2.py`
- Source collectors: `signal_collectors/`
- Agent collaboration protocols: `agent-skills/`

## GitHub Project Context

AI Radar can read project GitHub repositories to build lightweight project context snapshots. A project repo snapshot may include:

- README and roadmap excerpts
- top-level repository tree
- recent commits
- manifest files such as `package.json`, `requirements.txt`, `pyproject.toml`, or `Dockerfile`
- lightweight architecture hints

These snapshots are project context, not verification evidence. They help AI Radar discuss project relevance more accurately when a model API cannot browse GitHub directly.

## Current Development Focus

Current active themes include:

- stronger Project Takeaway review, watch, action, and trajectory loops
- manual upload end-to-end hardening
- project GitHub context snapshots
- knowledge quality and project-match precision
- lightweight development intake through Dev Inbox without replacing local
  development workflows
- reflection sync and matching quality
- unified reasoning / verification boundaries
- governance and evaluation scaffolds for invariants, bounded edits, edit apply
  reports, metadata hardening audits, claim dependency audits, and held-out
  insight evaluation
- skills system hardening and prompt contract discipline
- UI guidance and operator-facing workflow clarity

See `ROADMAP.md` for the current product roadmap.

## Documentation Map

Useful docs:

- `ROADMAP.md` - current project roadmap and development direction
- `AI_RADAR_PRODUCT_SPEC.md` - product positioning and future-state product boundaries
- `DEVELOPMENT_PLAN.md` - public planning boundary and roadmap pointer
- `CURRENT_DEVELOPMENT_STATUS.md` - public status boundary and overview pointer
- `AGENTS.md` - public coding-agent operating rules
- `docs/README.md` - selected public documentation index
- `PUBLIC_RELEASE_NOTES.md` - sanitization scope and pre-publication checklist

For coding agents, `AGENTS.md` is the operating guide. This README is the public/project-level summary.

## License

This project is available under the [MIT License](LICENSE).
