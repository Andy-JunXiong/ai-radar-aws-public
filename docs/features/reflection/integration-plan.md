# Reflection and AI Radar Integration Plan

This plan turns the reflection architecture into a read-only integration. It
describes boundaries and implementation stages without including private
repository details or credentials.

## 1. Goal and non-goals

Goal: index manually curated deep reflections and connect them to relevant AI
Radar signals without turning reflection content into factual evidence.

Non-goals:

- AI-generated deep-reflection authoring
- editing or committing to the private reflection repository
- storing access tokens in source or runtime output
- treating reflection text as proof of an external claim
- semantic-vector infrastructure before tag-based matching is evaluated

## 2. Module boundaries

The public implementation is divided into:

```text
backend/app/reflection/
├── github_client.py
├── frontmatter_parser.py
├── index_builder.py
├── schemas.py
└── settings_store.py

backend/app/services/
├── reflection_service.py
└── reflection_relationship_index_service.py

backend/app/routes/
└── reflection.py

frontend/app/reflections/
├── page.tsx
└── detail/
```

The GitHub client owns read-only transport. The parser owns Markdown metadata
validation. The index builder owns incremental index state. Services own query
and relationship behavior. Routes expose stable API shapes. Frontend pages are
read-only views over those APIs.

## 3. Storage model

The source repository remains authoritative. AI Radar stores only the minimum
derived index needed for query and matching:

- stable reflection ID
- title, timestamp, source, depth, and tags
- source repository path and immutable source URL when available
- related reflection IDs
- synchronization metadata and content fingerprint

Private reflection bodies should be fetched only when an authorized detail
view needs them. They must not be copied into public fixtures, logs, debug
payloads, or this repository.

## 4. Core schema

```python
class ReflectionIndexEntry(BaseModel):
    id: str
    timestamp: datetime
    source: str
    title: str
    tags: list[str]
    depth: str | None = None
    related: list[str] = []
    source_path: str
    source_url: str | None = None
    content_fingerprint: str
    synced_at: datetime
```

Validation rules:

- IDs are stable and unique.
- Timestamps include timezone information.
- Source paths stay inside the configured reflection root.
- Missing required frontmatter is reported, not silently invented.
- Unknown optional fields are preserved only when explicitly supported.

## 5. GitHub client

Configuration is supplied through environment variables or the runtime secret
boundary. Public examples contain placeholders only.

The client may:

- read repository metadata
- list files below the configured reflection directory
- read a Markdown file
- compare object identifiers or fingerprints for incremental sync

The client must not create commits, branches, issues, or pull requests. The
credential must be a fine-grained read-only token limited to the single private
reflection repository. Tokens must never be returned by APIs or written to
logs.

## 6. Frontmatter parsing

The parser separates YAML frontmatter from Markdown content, validates required
fields, normalizes timestamps and tags, and returns structured validation
errors. A malformed file is skipped with a bounded diagnostic; it does not
stop the entire synchronization batch.

The parser does not rewrite source files or invent missing author judgments.

## 7. Index synchronization

The synchronization loop is incremental:

1. List candidate Markdown paths.
2. Compare each source object identifier or fingerprint with the current index.
3. Fetch and parse only new or changed files.
4. Replace the index atomically after validation.
5. Record counts for added, updated, unchanged, skipped, and failed items.

Deleted source files should be marked unavailable or removed from the derived
index according to an explicit retention policy. A transient API failure must
not erase the last valid index.

## 8. Tag-based matching

Version 1 uses transparent tag and entity matching. Normalize case, separators,
and a small reviewed synonym map. Score overlap conservatively and return the
matched terms with every result.

Matching output is contextual recall, not evidence. It may say that a signal is
related to a previous reflection; it must not claim that the reflection proves
the signal true.

Semantic matching is deferred until real usage demonstrates that tag matching
misses valuable relationships.

## 9. API surface

The reflection API should provide read-only endpoints for:

- index status and synchronization health
- paginated reflection summaries
- a reflection detail lookup
- tags and filters
- signal-to-reflection relationship results

Responses exclude credentials, raw repository errors, and unrelated private
repository metadata. Authorization follows the existing protected backend
boundary.

## 10. Frontend surfaces

The reflection timeline supports date and tag filters. The detail page shows
validated metadata, source attribution, related reflections, and authorized
content. Signal and Radar surfaces may show a small related-reflections panel.

Every surface must explain that reflection content is cognitive context rather
than external claim evidence.

## 11. Delivery sequence

### Phase 0: connectivity

- verify read-only repository access
- list the configured directory
- read one synthetic Markdown fixture
- verify rate-limit visibility without logging the token

### Phase 1: ingestion

- implement schemas and frontmatter validation
- implement the read-only client
- build an incremental, failure-safe index
- add focused unit tests

### Phase 2: read-only UI

- add timeline, filters, and detail view
- expose synchronization health
- verify no edit or write controls exist

### Phase 3: matching

- implement tag-based matching
- show matched terms and source links
- verify reflection matches cannot satisfy evidence gates

### Later phases

Consider semantic matching and longitudinal relationship tracking only after
the simpler system has enough real data to justify them.

## 12. Acceptance criteria

- Read-only access is enforced in code and credential scope.
- Required frontmatter is validated with actionable errors.
- Incremental sync preserves the last valid index on failure.
- API responses contain no credentials or private debug payloads.
- Reflection content cannot become factual claim support automatically.
- Tag matching reports why a match occurred.
- Automated tests cover parsing, synchronization, query, and evidence-boundary
  behavior.

## 13. Operations

Monitor synchronization outcome, duration, files changed, validation failures,
GitHub rate-limit headroom, and stale-index age. Log paths and error categories,
not tokens or private reflection bodies.

If the source repository is unavailable, continue serving the last valid index
with a visible freshness warning. Never replace good state with an empty index
caused by a transient failure.

---

Public English edition, 2026-07-21.
