import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";


const pageSource = readFileSync(
  join(process.cwd(), "app/workspace/projects/changes/page.tsx"),
  "utf8",
);
const projectsSource = readFileSync(
  join(process.cwd(), "app/workspace/projects/page.tsx"),
  "utf8",
);
const understandingSource = readFileSync(
  join(process.cwd(), "app/workspace/projects/intelligence/page.tsx"),
  "utf8",
);

assert.match(pageSource, /<RequireAdminAuth>/, "Project Change Review must require the existing admin session");
assert.match(pageSource, /apiUrl\("\/projects\/repo-snapshot-changes"\)/, "The page must use the cached cross-project read endpoint");
assert.match(pageSource, /Back to Project Takeaways/, "The page must provide the primary Project Takeaways return path");
assert.match(pageSource, /Manage Projects/, "The page must provide the project configuration path");
assert.match(pageSource, /Cached snapshots only · page loads never refresh GitHub/, "The page must disclose its cached read boundary");
assert.match(pageSource, /Needs attention/, "The page must expose attention triage");
assert.match(pageSource, /Changed/, "The page must expose changed projects");
assert.match(pageSource, /Baseline/, "The page must distinguish initial baselines");
assert.match(pageSource, /Unchanged/, "The page must expose unchanged projects");
assert.match(pageSource, /snapshot \{item\.snapshot_status/, "Snapshot health must remain visible");
assert.match(pageSource, /delta \{item\.delta_status/, "Repository delta must remain a separate visible dimension");
assert.match(pageSource, /Open Project Understanding/, "Each project must hand off to existing bounded understanding");
assert.match(pageSource, /encodeURIComponent\(item\.project_id\)/, "Project Understanding links must encode project IDs");
assert.match(pageSource, /does not verify claims, infer development progress, run Deep Scan, or unlock downstream actions/, "The context-not-evidence and no-Deep-Scan boundary must be explicit");
assert.match(pageSource, /min\(100%, 360px\)/, "Project cards must remain responsive at narrow widths");
assert.doesNotMatch(pageSource, /repo-snapshot\/refresh/, "The review page must not refresh a repository");
assert.doesNotMatch(pageSource, /method:\s*["']POST["']/, "The review page must remain read-only");
assert.doesNotMatch(pageSource, /Run Deep Scan/, "The review page must not expose Deep Scan");
assert.match(projectsSource, /href="\/workspace\/projects\/changes"[\s\S]*Project Changes/, "Project Takeaways must expose the Project Changes entry point");
assert.match(understandingSource, /href="\/workspace\/projects\/changes"[\s\S]*Review Project Changes/, "Project Understanding must return to the cross-project review");

console.log("Project Change Review contract tests passed: 20");
