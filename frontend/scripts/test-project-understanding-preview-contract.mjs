import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";


const previewSource = readFileSync(
  join(process.cwd(), "app/workspace/projects/intelligence/page.tsx"),
  "utf8",
);
const adminSource = readFileSync(
  join(process.cwd(), "app/admin/projects/page.tsx"),
  "utf8",
);

assert.match(
  adminSource,
  /\/workspace\/projects\/intelligence\?project_id=\$\{encodeURIComponent\(selectedProjectId\)\}/,
  "Admin must open the dedicated Project Understanding route with an encoded project ID",
);
assert.match(adminSource, /Open Project Understanding/, "Admin must use the same Project Understanding label as the destination page");
assert.match(
  previewSource,
  /\/projects\/\$\{encodeURIComponent\(projectId\)\}\/repo-snapshot/,
  "Project Understanding must load the existing cached snapshot envelope",
);
assert.match(previewSource, /<RequireAdminAuth>/, "Project Understanding must require the existing admin session");
assert.match(previewSource, /Back to Project Takeaways/, "Project Understanding must provide the primary return path");
assert.match(previewSource, /Manage Projects/, "Project Understanding must provide the Admin management path");
assert.match(previewSource, /Cached context only · no automatic repository refresh/, "The page must disclose that it does not refresh automatically");
assert.match(previewSource, /Observation/, "The page must label the repository observation layer");
assert.match(previewSource, /Deterministic interpretation/, "The page must label deterministic interpretation separately");
assert.match(previewSource, /Operator-owned project context/, "The page must distinguish operator-owned project context");
assert.match(previewSource, /Source-reported development reality/, "The page must expose source-reported development reality");
assert.match(previewSource, /What is developed, active, blocked, and next/, "The page must state the development-reality question");
assert.match(previewSource, /"current_state", "development_plan", "roadmap"/, "Only explicit development source roles may feed repository development reality");
assert.match(previewSource, /Completed[\s\S]*In progress[\s\S]*Blocked[\s\S]*Next up/, "The page must render the four development-state categories");
assert.match(previewSource, /Repository source · \{entry\.path\}/, "Every reported development state must name its repository source path");
assert.match(previewSource, /source updated \$\{entry\.sourceLastUpdated\}/, "Development Reality must distinguish source update time from snapshot scan time");
assert.match(previewSource, /Active plan/, "The page must expose the configured development plan as a separate active-plan summary");
assert.match(previewSource, /View source details/, "Dense source excerpts must be collapsed behind an explicit disclosure");
assert.match(previewSource, /items\.length === 5/, "Default development summaries must be bounded to five items");
assert.match(previewSource, /cleanDevelopmentItem/, "Default development summaries must remove Markdown syntax deterministically");
assert.match(previewSource, /min\(100%, 420px\)/, "Development cards must use a responsive two-column-friendly minimum width");
assert.match(previewSource, /Commit counts and unchanged deltas do not determine development state\./, "The page must reject commit-based development inference");
assert.match(previewSource, /Unknown — no configured source reported this state\./, "Missing development facts must remain explicitly unknown");
assert.match(adminSource, /Development Reality reads excerpt anchors named/, "Admin must explain the source roles that enable Development Reality");
assert.match(previewSource, /Snapshot \{snapshotStatusLabel\(snapshot\?\.status\)\}/, "The page must expose non-fresh snapshot states");
assert.match(previewSource, /snapshot\?\.delta\?\.status === "changed"/, "Changed delta facts must be conditionally rendered");
assert.match(
  previewSource,
  /Repository context is project review context only\. It does not verify external claims or unlock downstream actions\./,
  "The preview must preserve the context-not-evidence boundary",
);
assert.doesNotMatch(previewSource, /repo-snapshot\/refresh/, "The preview must not call the refresh endpoint");
assert.doesNotMatch(previewSource, /github-context/, "The preview must not create a second repository-reading path");
assert.doesNotMatch(previewSource, /method:\s*["']POST["']/, "The preview must remain read-only");
assert.doesNotMatch(previewSource, /Run Deep Scan/, "The preview must not expose Deep Scan");

console.log("Project Understanding Preview contract tests passed: 31");
