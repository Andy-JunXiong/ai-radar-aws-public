import { createElement } from "react";
import { Radio, Brain, BookOpen, Network, Rocket, type LucideIcon } from "lucide-react";

const iconMap: Record<string, LucideIcon> = {
  Radio,
  Brain,
  BookOpen,
  Network,
  Rocket,
};

export function getIcon(name: string): LucideIcon {
  return iconMap[name] ?? Radio;
}

export function ArchitectureIcon({
  name,
  className,
}: {
  name: string;
  className?: string;
}) {
  return createElement(getIcon(name), { className });
}
