/**
 * P4-017 — Mode labels + per-section evidence metadata
 *
 * Validates:
 * - SectionEvidenceTag renders source, freshness, and optional artifact
 * - useSimulationGuard returns correct guard state per mode
 * - Guard blocks actions in simulation mode, allows in live mode
 */

import { render, screen } from "@testing-library/react";
import { renderHook } from "@testing-library/react";
import SectionEvidenceTag from "@/components/readiness/SectionEvidenceTag";
import { useSimulationGuard } from "@/lib/simulation-guard";

// ---------------------------------------------------------------------------
// SectionEvidenceTag
// ---------------------------------------------------------------------------
describe("SectionEvidenceTag", () => {
  it("renders source and freshness", () => {
    render(
      <SectionEvidenceTag source="/api/dashboard/admin" dataFreshness="live" />
    );
    const tag = screen.getByTestId("section-evidence-tag");
    expect(tag).toBeInTheDocument();
    expect(tag).toHaveAttribute("data-source", "/api/dashboard/admin");
    expect(tag).toHaveAttribute("data-freshness", "live");
    expect(screen.getByText("src: /api/dashboard/admin")).toBeInTheDocument();
    expect(screen.getByText("fresh: live")).toBeInTheDocument();
  });

  it("renders evidence artifact when provided", () => {
    render(
      <SectionEvidenceTag
        source="simulation"
        dataFreshness="static"
        evidenceArtifact="evidence/p4-017-audit.md"
      />
    );
    expect(
      screen.getByText("artifact: evidence/p4-017-audit.md")
    ).toBeInTheDocument();
  });

  it("does not render artifact span when omitted", () => {
    render(<SectionEvidenceTag source="simulation" dataFreshness="static" />);
    expect(screen.queryByText(/artifact:/)).not.toBeInTheDocument();
  });

  it("applies italic style for simulation source", () => {
    render(<SectionEvidenceTag source="simulation" dataFreshness="static" />);
    const tag = screen.getByTestId("section-evidence-tag");
    expect(tag.className).toContain("italic");
  });

  it("applies italic style for demo source", () => {
    render(<SectionEvidenceTag source="demo" dataFreshness="static" />);
    const tag = screen.getByTestId("section-evidence-tag");
    expect(tag.className).toContain("italic");
  });

  it("does not apply italic for live API source", () => {
    render(
      <SectionEvidenceTag source="/api/dashboard/admin" dataFreshness="live" />
    );
    const tag = screen.getByTestId("section-evidence-tag");
    expect(tag.className).not.toContain("italic");
  });
});

// ---------------------------------------------------------------------------
// useSimulationGuard
// ---------------------------------------------------------------------------
describe("useSimulationGuard", () => {
  it('returns isSimulation=true for mode "simulation"', () => {
    const { result } = renderHook(() =>
      useSimulationGuard("simulation", "admin/dashboard")
    );
    expect(result.current.isSimulation).toBe(true);
    expect(result.current.hasSimulationSections).toBe(true);
  });

  it('returns isSimulation=false, hasSimulationSections=true for mode "mixed"', () => {
    const { result } = renderHook(() =>
      useSimulationGuard("mixed", "admin/dashboard")
    );
    expect(result.current.isSimulation).toBe(false);
    expect(result.current.hasSimulationSections).toBe(true);
  });

  it('returns all false for mode "live"', () => {
    const { result } = renderHook(() =>
      useSimulationGuard("live", "admin/dashboard")
    );
    expect(result.current.isSimulation).toBe(false);
    expect(result.current.hasSimulationSections).toBe(false);
  });

  it("returns page-specific escalation text", () => {
    const { result } = renderHook(() =>
      useSimulationGuard("simulation", "admin/audit")
    );
    expect(result.current.escalationText).toContain("CISO approval");
  });

  it("returns page-specific reason text", () => {
    const { result } = renderHook(() =>
      useSimulationGuard("simulation", "clinical/intelligence")
    );
    expect(result.current.reasonText).toContain("Clinical agent API");
  });

  it("returns default escalation text for unknown page key", () => {
    const { result } = renderHook(() =>
      useSimulationGuard("simulation", "unknown/page")
    );
    expect(result.current.escalationText).toContain(
      "Contact system administrator"
    );
  });

  it("guardedAction runs action in live mode", () => {
    const { result } = renderHook(() =>
      useSimulationGuard("live", "admin/dashboard")
    );
    const fn = jest.fn();
    result.current.guardedAction(fn);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("guardedAction blocks action in simulation mode", () => {
    const { result } = renderHook(() =>
      useSimulationGuard("simulation", "admin/dashboard")
    );
    const fn = jest.fn();
    result.current.guardedAction(fn);
    expect(fn).not.toHaveBeenCalled();
  });
});
