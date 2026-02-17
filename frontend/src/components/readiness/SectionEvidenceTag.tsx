import { FileText } from "lucide-react";

export interface SectionEvidenceMeta {
  /** Source of data: e.g. "/api/dashboard/admin", "simulation", "static" */
  source: string;
  /** ISO date or relative freshness label */
  dataFreshness: string;
  /** Path to evidence artifact in repo */
  evidenceArtifact?: string;
}

/**
 * Compact inline tag showing per-card/section evidence metadata.
 * Renders source, freshness, and optional artifact path in a single
 * subtle row beneath the card content.
 */
export default function SectionEvidenceTag({
  source,
  dataFreshness,
  evidenceArtifact,
}: SectionEvidenceMeta) {
  const isSimulation = source === "simulation" || source === "demo";

  return (
    <div
      className={`mt-2 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[10px] leading-tight ${
        isSimulation ? "text-slate-400 italic" : "text-slate-500"
      }`}
      data-testid="section-evidence-tag"
      data-source={source}
      data-freshness={dataFreshness}
    >
      <span className="flex items-center gap-1">
        <FileText className="h-2.5 w-2.5" />
        <span>src: {source}</span>
      </span>
      <span>fresh: {dataFreshness}</span>
      {evidenceArtifact && (
        <span className="font-mono truncate max-w-[200px]" title={evidenceArtifact}>
          artifact: {evidenceArtifact}
        </span>
      )}
    </div>
  );
}
