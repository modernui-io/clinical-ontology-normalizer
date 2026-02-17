"use client";

import { useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";

interface CollapsibleListProps {
  children: ReactNode[];
  initialCount?: number;
  itemLabel?: string;
}

export default function CollapsibleList({
  children,
  initialCount = 5,
  itemLabel = "items",
}: CollapsibleListProps) {
  const [expanded, setExpanded] = useState(false);
  const total = children.length;

  if (total <= initialCount) {
    return <>{children}</>;
  }

  const visible = expanded ? children : children.slice(0, initialCount);
  const remaining = total - initialCount;

  return (
    <>
      {visible}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1.5 text-xs font-medium text-slate-600 hover:text-slate-900 transition-colors mt-2 px-1"
      >
        <ChevronDown
          className={`h-3.5 w-3.5 transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
        />
        {expanded ? "Show less" : `Show ${remaining} more ${itemLabel}`}
      </button>
    </>
  );
}
