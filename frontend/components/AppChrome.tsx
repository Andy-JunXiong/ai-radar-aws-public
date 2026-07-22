"use client";

import { usePathname } from "next/navigation";

import OperatorGuidanceWidget from "@/components/OperatorGuidanceWidget";
import PortfolioHeader from "@/components/portfolio/PortfolioHeader";
import TopNav from "@/components/TopNav";

export default function AppChrome() {
  const pathname = usePathname();
  const isPortfolio = pathname === "/portfolio" || pathname === "/portfolio/";

  if (isPortfolio) {
    return <PortfolioHeader />;
  }

  return (
    <>
      <TopNav />
      <OperatorGuidanceWidget />
    </>
  );
}
