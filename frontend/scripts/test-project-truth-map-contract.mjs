import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";


const source = readFileSync(join(process.cwd(), "app/admin/projects/page.tsx"), "utf8");

assert.match(
  source,
  /truth_map:\s*form\.truthMapEnabled[\s\S]*schema_version:\s*1[\s\S]*anchors:\s*form\.truthMapAnchors/,
  "Project save must persist the enabled Truth Map under repo_context.truth_map",
);
assert.match(
  source,
  /truth_map:\s*form\.truthMapEnabled[\s\S]*:\s*null/,
  "Turning configured Truth Map off must send the explicit clear value",
);
assert.match(
  source,
  /Save Changes stores this configuration\.[\s\S]*Refresh Light Snapshot then reads the saved anchors/,
  "The UI must explain the separate save-then-refresh workflow",
);
assert.match(
  source,
  /configured truth map/,
  "Snapshot discovery status must identify configured Truth Map mode",
);
assert.match(
  source,
  /heuristic discovery/,
  "Snapshot discovery status must identify heuristic mode",
);
assert.match(
  source,
  /truth map invalid/,
  "Snapshot discovery status must expose invalid configuration",
);
assert.match(
  source,
  /Repo Snapshot is project review context only\. It does not verify external claims or unlock downstream actions\./,
  "Repo Snapshot UI must preserve the context-not-evidence boundary",
);
assert.match(
  source,
  /snapshot v2/,
  "Repo Snapshot UI must identify the v2 contract",
);
assert.match(
  source,
  /head \{shortSha\(repoSnapshot\.observation\.head\.sha\)\}[\s\S]*baseline \{shortSha\(repoSnapshot\.observation\.baseline\.sha\)\}/,
  "Repo Snapshot UI must expose head and baseline identifiers",
);
assert.match(
  source,
  /repoSnapshot\.delta\.status === "changed"[\s\S]*Commits[\s\S]*repoSnapshot\.delta\.status === "changed"[\s\S]*Files/,
  "Changed Snapshot v2 deltas must expose bounded commit and file facts",
);

console.log("Project Truth Map frontend contract tests passed: 10");
