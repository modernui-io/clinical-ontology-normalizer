import { useCallback, useMemo } from "react";

type DataSourceMode = "live" | "mixed" | "simulation";

export interface SimulationGuard {
  /** True when mode is "simulation" */
  isSimulation: boolean;
  /** True when mode is "simulation" or "mixed" */
  hasSimulationSections: boolean;
  /** Wraps an action: runs it if live, shows warning text if simulation */
  guardedAction: (action: () => void, label?: string) => void;
  /** Escalation text for switching to live */
  escalationText: string;
  /** Short reason text for why simulation is active */
  reasonText: string;
}

const ESCALATION_MAP: Record<string, string> = {
  "admin/dashboard":
    "To enable live resource monitoring, wire /api/v1/metrics streaming endpoint. Contact CTO + Ops for provisioning approval.",
  "admin/audit":
    "Connect production audit API at /api/v1/audit/events to view real audit trail. Requires CISO approval for audit data access.",
  "clinical":
    "Ensure backend services (provider + biller dashboards) are running. Contact CTO for service connectivity.",
  "clinical/intelligence":
    "Connect clinical-agent API at /api/clinical-agent/* to enable live import, graph, and Q&A. Requires CTO approval.",
  "dashboard":
    "Connect backend API endpoints for documents, patients, trials, and audit logs to enable live dashboard data.",
  "documents":
    "Connect backend document processing API at /api/v1/documents to view live clinical notes.",
  "patients":
    "Connect backend patient API at /api/v1/patients to view live patient records.",
  "analytics/graph":
    "Connect backend knowledge graph API to enable live graph visualization.",
  default:
    "Contact system administrator to connect production data sources.",
};

const REASON_MAP: Record<string, string> = {
  "admin/dashboard":
    "Resource gauges and request volume use client-side generated data. No streaming metrics endpoint is connected.",
  "admin/audit":
    "All audit entries and statistics are seeded demonstration records. No production audit API is connected.",
  "clinical":
    "Backend API returned an error or is unavailable. Clinical data cannot be loaded from production endpoints.",
  "clinical/intelligence":
    "Clinical agent API is unavailable. Graph data, Q&A responses, and import results are client-side simulations.",
  "dashboard":
    "Backend API is unavailable. Dashboard metrics and activity feed show demonstration data.",
  "documents":
    "Backend API is unavailable. Document list shows demonstration clinical notes.",
  "patients":
    "Backend API is unavailable. Patient list shows demonstration patient records.",
  "analytics/graph":
    "Backend API is unavailable. Graph visualization shows demonstration knowledge graph data.",
  default: "Some data on this page comes from simulation or demonstration sources.",
};

/**
 * Hook that provides simulation-mode guard utilities for a page.
 * @param mode - The current data source mode for the page
 * @param pageKey - A key identifying the page (e.g., "admin/dashboard")
 */
export function useSimulationGuard(
  mode: DataSourceMode,
  pageKey: string = "default"
): SimulationGuard {
  const isSimulation = mode === "simulation";
  const hasSimulationSections = mode === "simulation" || mode === "mixed";

  const escalationText = useMemo(
    () => ESCALATION_MAP[pageKey] ?? ESCALATION_MAP.default,
    [pageKey]
  );

  const reasonText = useMemo(
    () => REASON_MAP[pageKey] ?? REASON_MAP.default,
    [pageKey]
  );

  const guardedAction = useCallback(
    (action: () => void, _label?: string) => {
      if (isSimulation) {
        // In a real app this would show a toast; we just no-op
        return;
      }
      action();
    },
    [isSimulation]
  );

  return {
    isSimulation,
    hasSimulationSections,
    guardedAction,
    escalationText,
    reasonText,
  };
}
