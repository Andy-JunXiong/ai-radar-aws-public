import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";
import vm from "node:vm";

const require = createRequire(import.meta.url);
const ts = require("typescript");

function loadTsModule(relativePath) {
  const sourcePath = join(process.cwd(), relativePath);
  const source = readFileSync(sourcePath, "utf8");
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const sandbox = { exports: {}, module: { exports: {} }, require };
  sandbox.exports = sandbox.module.exports;
  vm.runInNewContext(compiled, sandbox, { filename: sourcePath });
  return sandbox.module.exports;
}

const { isPublicRoute, isLoginRoute } = loadTsModule("lib/publicRoutes.ts");

for (const pathname of ["/", "/portfolio", "/portfolio/"]) {
  assert.equal(isPublicRoute(pathname), true, `${pathname} should be public`);
}
for (const pathname of ["/login", "/signals", "/workspace/projects/review", "/admin", "/portfolio/private"]) {
  assert.equal(isPublicRoute(pathname), false, `${pathname} should remain protected or separately handled`);
}
assert.equal(isLoginRoute("/login/"), true, "login slash variant should be handled as login");

const authGate = readFileSync(join(process.cwd(), "components/AppAuthGate.tsx"), "utf8");
assert.match(authGate, /isPublicRoute\(pathname \|\| "\/"\)/, "auth gate should use canonical public-route helper");
assert.match(authGate, /if \(isLoginPage \|\| isPublicPage\)/, "public route should return before token/session access");

const chrome = readFileSync(join(process.cwd(), "components/AppChrome.tsx"), "utf8");
assert.match(chrome, /if \(isPortfolio\)/, "portfolio should have dedicated public chrome");
const publicBranch = chrome.slice(chrome.indexOf("if (isPortfolio)"), chrome.indexOf("return (", chrome.indexOf("if (isPortfolio)") + 1));
assert.doesNotMatch(publicBranch, /TopNav|OperatorGuidanceWidget/, "public branch must exclude internal chrome");

const portfolioPage = readFileSync(join(process.cwd(), "app/portfolio/page.tsx"), "utf8");
assert.match(portfolioPage, /Code-traced · Test-supported/, "implementation trace must disclose its evidence tier");
assert.match(portfolioPage, /Policy failure returns HTTP 400/, "implementation trace must show the enforced result");
assert.match(portfolioPage, /Product outcome<\/dt><dd>Not claimed here/, "implementation trace must not masquerade as a product outcome");
assert.doesNotMatch(portfolioPage, /from\s+["']@\/lib\/(api|adminAuth)/, "portfolio must not import authenticated API helpers");

const portfolioHeader = readFileSync(join(process.cwd(), "components/portfolio/PortfolioHeader.tsx"), "utf8");
for (const forbidden of ["Admin", "Workspace", "Manual Upload", "Log out", "Log in"]) {
  assert.equal(portfolioHeader.includes(forbidden), false, `public header must not expose ${forbidden}`);
}
assert.match(portfolioHeader, /ai-radar-bg-theme/, "portfolio should reuse the shared theme preference");
assert.match(portfolioHeader, /Light/, "portfolio should expose the light theme");
assert.match(portfolioHeader, /Navy/, "portfolio should expose the navy theme");
assert.match(portfolioHeader, /ai-radar-aws-public/, "public header should link to the sanitized public repository");

const portfolioContent = readFileSync(join(process.cwd(), "content/portfolio.ts"), "utf8");
assert.match(portfolioContent, /ai-radar-aws-public/, "portfolio evidence should use the public repository");
assert.doesNotMatch(
  portfolioContent,
  /github\.com\/Andy-JunXiong\/ai-radar-aws(?:["`/])(?!(?:-public))/,
  "portfolio evidence must not link cold visitors to the private development repository"
);

console.log("Public route contract tests passed: anonymous portfolio stays narrow and protected routes remain protected");
