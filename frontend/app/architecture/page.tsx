import AppContainer from "@/components/AppContainer";
import PageHeader from "@/components/PageHeader";
import { getDaoFaShu, getLayers } from "@/lib/content";
import ArchitectureDemoClient from "./ArchitectureDemoClient";

export const metadata = {
  title: "Architecture | AI Radar",
  description: "Internal architecture demo for the AI Radar intelligence system.",
};

export default function ArchitecturePage() {
  return (
    <AppContainer style={{ paddingTop: "24px" }}>
      <PageHeader
        title="Architecture Demo"
        description="A product-internal walkthrough of how AI Radar moves from external signals into structured insight, reflection, knowledge, and project action."
        marginBottom="22px"
      />
      <ArchitectureDemoClient
        layers={getLayers()}
        daoFaShu={getDaoFaShu()}
      />
    </AppContainer>
  );
}
