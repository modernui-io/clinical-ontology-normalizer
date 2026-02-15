"use client";

import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";

interface DisagreementRecord {
  mention_text: string;
  rule_result: string | null;
  ml_result: string | null;
  ensemble_result: string | null;
  agreement: boolean;
  entity_type: string;
}

interface DisagreementSummary {
  total_mappings: number;
  agreement_rate: number;
  top_disagreements: DisagreementRecord[];
}

interface DisagreementDashboardProps {
  apiBaseUrl?: string;
  className?: string;
}

const ENTITY_TYPES = [
  { value: "", label: "All Types" },
  { value: "condition", label: "Condition" },
  { value: "drug", label: "Drug" },
  { value: "measurement", label: "Measurement" },
  { value: "procedure", label: "Procedure" },
  { value: "observation", label: "Observation" },
];

/**
 * Dashboard showing concept mapping disagreements between
 * rule-based, ML, and ensemble NLP pipelines.
 *
 * P2-011: Displays a summary with agreement rate badge
 * and a filterable table of individual disagreements.
 */
export function DisagreementDashboard({
  apiBaseUrl = "/api/v1",
  className,
}: DisagreementDashboardProps) {
  const [summary, setSummary] = useState<DisagreementSummary | null>(null);
  const [entityFilter, setEntityFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      setError(null);
      try {
        const params = entityFilter
          ? `?entity_type=${encodeURIComponent(entityFilter)}`
          : "";
        const res = await fetch(`${apiBaseUrl}/mapping-disagreements${params}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: DisagreementSummary = await res.json();
        setSummary(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load data");
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [apiBaseUrl, entityFilter]);

  const agreementColor =
    summary && summary.agreement_rate >= 90
      ? "bg-green-100 text-green-800"
      : summary && summary.agreement_rate >= 70
        ? "bg-yellow-100 text-yellow-800"
        : "bg-red-100 text-red-800";

  return (
    <div className={cn("rounded-lg border p-6", className)}>
      <h2 className="text-lg font-semibold mb-4">
        Concept Mapping Disagreements
      </h2>

      {/* Summary row */}
      {summary && !loading && (
        <div className="flex items-center gap-4 mb-6">
          <div className="text-sm text-muted-foreground">
            Total Mappings:{" "}
            <span className="font-medium text-foreground">
              {summary.total_mappings.toLocaleString()}
            </span>
          </div>
          <span
            className={cn(
              "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
              agreementColor
            )}
          >
            Agreement: {summary.agreement_rate.toFixed(1)}%
          </span>
        </div>
      )}

      {/* Filter */}
      <div className="mb-4">
        <label
          htmlFor="entity-filter"
          className="block text-sm font-medium text-muted-foreground mb-1"
        >
          Filter by Entity Type
        </label>
        <select
          id="entity-filter"
          value={entityFilter}
          onChange={(e) => setEntityFilter(e.target.value)}
          className="block w-48 rounded-md border px-3 py-1.5 text-sm"
        >
          {ENTITY_TYPES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
      </div>

      {/* Loading / Error states */}
      {loading && (
        <p className="text-sm text-muted-foreground py-8 text-center">
          Loading disagreements...
        </p>
      )}
      {error && (
        <p className="text-sm text-red-600 py-4 text-center">{error}</p>
      )}

      {/* Table */}
      {!loading && !error && summary && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="py-2 pr-4 font-medium">Mention</th>
                <th className="py-2 pr-4 font-medium">Rule Result</th>
                <th className="py-2 pr-4 font-medium">ML Result</th>
                <th className="py-2 pr-4 font-medium">Ensemble Result</th>
                <th className="py-2 font-medium">Agreement</th>
              </tr>
            </thead>
            <tbody>
              {summary.top_disagreements.length === 0 ? (
                <tr>
                  <td
                    colSpan={5}
                    className="py-8 text-center text-muted-foreground"
                  >
                    No disagreements found
                  </td>
                </tr>
              ) : (
                summary.top_disagreements.map((record, idx) => (
                  <tr key={idx} className="border-b last:border-0">
                    <td className="py-2 pr-4 font-medium">
                      {record.mention_text}
                    </td>
                    <td className="py-2 pr-4">
                      {record.rule_result ?? (
                        <span className="text-muted-foreground italic">
                          unmapped
                        </span>
                      )}
                    </td>
                    <td className="py-2 pr-4">
                      {record.ml_result ?? (
                        <span className="text-muted-foreground italic">
                          unmapped
                        </span>
                      )}
                    </td>
                    <td className="py-2 pr-4">
                      {record.ensemble_result ?? (
                        <span className="text-muted-foreground italic">
                          unmapped
                        </span>
                      )}
                    </td>
                    <td className="py-2">
                      <span
                        className={cn(
                          "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
                          record.agreement
                            ? "bg-green-100 text-green-700"
                            : "bg-red-100 text-red-700"
                        )}
                      >
                        {record.agreement ? "Yes" : "No"}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
