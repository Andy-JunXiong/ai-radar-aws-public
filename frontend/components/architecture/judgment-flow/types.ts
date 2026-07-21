export type GateKind = "system" | "human";

export type JudgmentStage = {
  id: string;
  trackLabel: string;
  stageLabel: string;
  subLabel: string;
  gateLabel: string;
  gateKind: GateKind;
  whatHappens: string;
  stateDiff: Record<string, unknown>;
  designDecision: string;
  reflectionEvent?: {
    type: string;
    location: string;
    contentSummary: string;
    feedsIntoEvidence: boolean;
    feedsIntoContext: boolean;
  };
};
