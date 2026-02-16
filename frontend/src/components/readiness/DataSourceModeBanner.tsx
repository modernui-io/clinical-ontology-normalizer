import { AlertTriangle, CircleCheck, CircleDashed } from "lucide-react";
import { Badge } from "@/components/ui/badge";

type DataSourceMode = "live" | "simulation" | "mixed";

interface DataSourceModeBannerProps {
  mode: DataSourceMode;
  title: string;
  description: string;
  evidencePath?: string;
  lastUpdatedAt?: string;
  signoffText?: string;
  backendEndpoints?: string[];
}

function modeCopy(mode: DataSourceMode) {
  switch (mode) {
    case "live":
      return {
        icon: <CircleCheck className="h-4 w-4" />,
        badgeClass: "bg-emerald-100 text-emerald-800 border-emerald-200",
        badgeText: "Live",
        toneClass: "border-emerald-200 bg-emerald-50/50 text-emerald-800",
      };
    case "mixed":
      return {
        icon: <AlertTriangle className="h-4 w-4" />,
        badgeClass: "bg-amber-100 text-amber-800 border-amber-200",
        badgeText: "Mixed",
        toneClass: "border-amber-200 bg-amber-50/50 text-amber-800",
      };
    case "simulation":
    default:
      return {
        icon: <CircleDashed className="h-4 w-4" />,
        badgeClass: "bg-slate-100 text-slate-700 border-slate-200",
        badgeText: "Simulation",
        toneClass: "border-slate-200 bg-slate-50/60 text-slate-700",
      };
  }
}

export default function DataSourceModeBanner({
  mode,
  title,
  description,
  evidencePath,
  lastUpdatedAt,
  signoffText,
  backendEndpoints,
}: DataSourceModeBannerProps) {
  const info = modeCopy(mode);

  return (
    <div className={`rounded-lg border px-4 py-3 ${info.toneClass}`}>
      <div className="flex items-start gap-3">
        {info.icon}
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
            <Badge className={`border ${info.badgeClass}`}>{info.badgeText}</Badge>
          </div>
          <p className="mt-1 text-xs text-slate-600 leading-relaxed">{description}</p>
          {evidencePath ? (
            <p className="mt-1 text-[11px] text-slate-500">
              Evidence/anchor: <span className="font-mono">{evidencePath}</span>
            </p>
          ) : null}
          {lastUpdatedAt ? (
            <p className="mt-1 text-[11px] text-slate-500">
              Evidence freshness: {lastUpdatedAt}
            </p>
          ) : null}
          {signoffText ? (
            <p className="mt-1.5 text-[11px] font-medium text-slate-700 italic">
              {signoffText}
            </p>
          ) : null}
          {backendEndpoints && backendEndpoints.length > 0 ? (
            <p className="mt-1 text-[11px] text-slate-500">
              Backend endpoints:{" "}
              {backendEndpoints.map((ep, i) => (
                <span key={ep}>
                  <code className="font-mono text-[10px] bg-slate-100 px-1 rounded">{ep}</code>
                  {i < backendEndpoints.length - 1 ? ", " : ""}
                </span>
              ))}
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
