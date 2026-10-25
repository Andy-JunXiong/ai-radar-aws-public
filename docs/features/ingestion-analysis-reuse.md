# Automatic analysis selection and result reuse

## Origin and decision

This maintenance change follows a maintainer request to remove mandatory
analysis quotas and unnecessary regeneration of unchanged results. Its origin
is an observed usage gap in existing ingestion, not an external framework;
external-source admission is not applicable. The maintainer owns the decision
to replace quantity-based fallback selection with qualifying-signal selection.

The change extends the existing daily Radar artifact and existing model
executor. It does not introduce another executor, scheduler or verification
authority. Daily Radar and profile views remain the downstream consumers.
The immediate benefit is fewer unnecessary requests; the longer-term benefit
is explicit provenance for reused results. Product direction is unchanged.

## Behavior

- Automatic Insights select only qualifying signals, up to the existing upper
  limit. Zero qualifying signals is valid. Ordinary candidates and archived
  items are not promoted to fill a minimum.
- Insight, Repo and Friction analyses may reuse a successful prior result when
  the relevant input, personal context, prompt/policy and provider/model match.
- Current ranking still determines profile output slots. A reused top-ranked
  item does not cause an extra lower-ranked model call to fill a request quota.
- Reused output retains its original analysis time. Observation/ranking
  bookkeeping is refreshed separately. A cache hit never grants verification
  or downstream Action eligibility.
- Failed, empty, invalid, legacy or corrupt entries do not qualify for reuse.

For example, five unchanged profile candidates can remain visible on the next
day while making no new model requests. A materially changed candidate alone
requires fresh analysis. If no signal qualifies for automatic Insight generation,
the daily Insight count can be zero while collection continues.

## Storage and invalidation

The existing daily Radar document contains versioned `analysis_reuse` state.
Production reads the previous durable document before analysis; local-only mode
reads its local document. State contains fingerprints and analysis output,
not raw prompts, credentials or personal-context input. It retains at most
256 entries and 1 MB of serialized entries, with a 64 KB per-entry limit.

Collection timestamps and age/ranking bookkeeping do not alone invalidate an
Insight. The Repo prompt's current date is normalized for matching, while a
publication date moving from future to current invalidates reuse. Relevant
content, policy, prompt, model and personal-context changes invalidate entries.

Legacy output needs a successful initial analysis before reuse can be proven.
Eviction or failed persistence can cause subsequent reanalysis. This is
sequential-run reuse, not distributed locking for overlapping tasks.

## Implementation and validation

- `app/main_summary_v2.py`: selection, lookup, invalidation context and persistence.
- `app/intelligence/analysis_reuse.py`: pure bounded state and validity checks.
- `tests/test_pipeline_analysis_reuse.py`: selection, cross-day reuse, changed
  inputs, failures, storage boundaries and whole-pipeline regression scenarios.

Whole-pipeline tests serialize one day's output and reload it in the next run,
asserting zero provider calls for unchanged valid inputs. Existing metrics,
signal-history and tracking tests provide integration coverage. Test providers
and storage are mocked; code validation is not evidence of production rollout
or a measured financial saving. Deployment and natural-run acceptance remain
separate operational actions.
