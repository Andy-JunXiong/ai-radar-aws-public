import AppContainer from "@/components/AppContainer";
import PageHeader from "@/components/PageHeader";
import ThreeViewDemoClient from "./ThreeViewDemoClient";

export const metadata = {
  title: "Signal Lifecycle Demo | AI Radar",
  description:
    "A static three-view architecture demo for node, event, and output perspectives.",
};

export default function SignalLifecycleDemoPage() {
  return (
    <AppContainer style={{ paddingTop: "28px" }}>
      <PageHeader
        title="Signal Lifecycle Demo"
        description="A static architecture model showing one AI Radar signal across node view, event stream, and output view."
        marginBottom="22px"
      />
      <ThreeViewDemoClient />
    </AppContainer>
  );
}
