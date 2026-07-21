// ───────────────────────────────────────────────────────────────
//  Content loader
//  ⚠️  CODEX SWAP POINT
//  Today these functions read from /content JSON files.
//  When wiring real data, replace the function bodies with API
//  calls but keep the return types identical — the UI components
//  contract on the types in /lib/types.ts.
// ───────────────────────────────────────────────────────────────

import layersJson from "@/content/layers.json";
import flowJson from "@/content/flow-steps.json";
import daoJson from "@/content/dao-fa-shu.json";
import type { Layer, FlowStep, DaoFaShuItem } from "./types";

export function getLayers(): Layer[] {
  return layersJson as Layer[];
}

export function getFlowSteps(): FlowStep[] {
  return flowJson as FlowStep[];
}

export function getDaoFaShu(): DaoFaShuItem[] {
  return daoJson as DaoFaShuItem[];
}
