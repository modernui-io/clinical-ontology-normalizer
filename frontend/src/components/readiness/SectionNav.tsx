"use client";

import { useEffect, useState } from "react";

interface NavAnchor {
  id: string;
  label: string;
}

const anchors: NavAnchor[] = [
  { id: "summary", label: "Summary" },
  { id: "demos", label: "Demos" },
  { id: "p0-blockers", label: "P0 Blockers" },
  { id: "evidence-map", label: "Evidence Map" },
  { id: "p4-progress", label: "P4 Progress" },
  { id: "drills", label: "Drills" },
  { id: "signoff", label: "Signoff" },
  { id: "reasoner", label: "Reasoner" },
  { id: "demo-pack", label: "Demo Pack" },
];

export default function SectionNav() {
  const [active, setActive] = useState("summary");

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActive(entry.target.id);
          }
        }
      },
      { rootMargin: "-80px 0px -60% 0px", threshold: 0 }
    );

    for (const anchor of anchors) {
      const el = document.getElementById(anchor.id);
      if (el) observer.observe(el);
    }

    return () => observer.disconnect();
  }, []);

  return (
    <nav className="sticky top-14 z-40 bg-white/90 backdrop-blur-sm border-b border-slate-200/60 -mx-6 px-6 overflow-x-auto">
      <div className="flex items-center gap-1 py-2 min-w-max">
        {anchors.map((a) => (
          <a
            key={a.id}
            href={`#${a.id}`}
            onClick={(e) => {
              e.preventDefault();
              document.getElementById(a.id)?.scrollIntoView({ behavior: "smooth", block: "start" });
            }}
            className={`px-2.5 py-1 rounded-md text-xs font-medium whitespace-nowrap transition-colors ${
              active === a.id
                ? "bg-slate-900 text-white"
                : "text-slate-500 hover:text-slate-900 hover:bg-slate-100"
            }`}
          >
            {a.label}
          </a>
        ))}
      </div>
    </nav>
  );
}
