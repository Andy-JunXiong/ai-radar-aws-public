# Pseudo Precision Calibration Record pp-001

id: pp-001

case: CodeGraphContext backend list

claim axis: precise-looking tool capability table

CLAIM: "CodeGraphContext supports Neo4j / ArangoDB / Memgraph / SQLite backends."

SOURCE: secondary infographic / social post reviewed in the four-tools brief

PRIMARY-SOURCE CHECK:
- Current CodeGraphContext README lists FalkorDB Lite, KuzuDB, LadybugDB, FalkorDB Remote, Nornic DB, and Neo4j.
- `pyproject.toml` dependencies include `neo4j`, `falkordb`, `falkordblite`, `kuzu`, and `ladybug`.
- `src/codegraphcontext/core/__init__.py` selects FalkorDB Remote, FalkorDB Lite, KuzuDB, LadybugDB, Nornic DB, or Neo4j; ArangoDB, Memgraph, and SQLite were not present in the checked source path.

LIMITATION / CORRECTION:
The exact backend list in the secondary artifact was materially wrong. The precision of the table increased confidence while decreasing factual accuracy.

VERDICT: pseudo_precision

severity: high

verification: primary-source repo review

evidence:
- https://github.com/CodeGraphContext/CodeGraphContext
- https://raw.githubusercontent.com/CodeGraphContext/CodeGraphContext/main/README.md
- https://raw.githubusercontent.com/CodeGraphContext/CodeGraphContext/main/pyproject.toml
- https://raw.githubusercontent.com/CodeGraphContext/CodeGraphContext/main/src/codegraphcontext/core/__init__.py

taxonomy note:
If the secondary source explicitly attributed ArangoDB / Memgraph / SQLite support to CodeGraphContext, this may also be `fabricated_attribution`. If it merely used those databases as a comparison frame, keep the label at `pseudo_precision`.

AI Radar boundary:
This record is Layer A' `grill-the-inference` pseudo_precision calibration only. It is not product runtime data, source evidence, claim support, Project Takeaway verification metadata, or a runtime gate output.
