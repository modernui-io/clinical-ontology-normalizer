"use client";

import * as d3 from "d3";
import type { SimulationNode } from "./types";

// Edge type to human-readable label mapping
export const EDGE_LABELS: Record<string, string> = {
  has_condition: "has",
  takes_drug: "takes",
  has_measurement: "measured",
  has_procedure: "underwent",
  has_observation: "observed",
  has_device: "uses",
  condition_treated_by: "treated by",
  drug_treats: "treats",
};

// Temporality-based edge colors
export function getTemporalityColor(temporality: string | null): string {
  switch (temporality) {
    case "current": return "#22c55e"; // green
    case "past": return "#f59e0b"; // amber
    case "future": return "#3b82f6"; // blue
    default: return "#64748b"; // slate
  }
}

// Convex hull with padding for node grouping
export function getHullPath(points: [number, number][], padding: number = 30): string {
  if (points.length < 3) {
    if (points.length === 1) {
      return `M ${points[0][0] - padding} ${points[0][1]}
              a ${padding} ${padding} 0 1 0 ${padding * 2} 0
              a ${padding} ${padding} 0 1 0 ${-padding * 2} 0`;
    }
    if (points.length === 2) {
      const [p1, p2] = points;
      const dx = p2[0] - p1[0];
      const dy = p2[1] - p1[1];
      const len = Math.sqrt(dx * dx + dy * dy);
      const nx = -dy / len * padding;
      const ny = dx / len * padding;
      return `M ${p1[0] + nx} ${p1[1] + ny}
              L ${p2[0] + nx} ${p2[1] + ny}
              A ${padding} ${padding} 0 0 1 ${p2[0] - nx} ${p2[1] - ny}
              L ${p1[0] - nx} ${p1[1] - ny}
              A ${padding} ${padding} 0 0 1 ${p1[0] + nx} ${p1[1] + ny}`;
    }
    return "";
  }

  const hull = d3.polygonHull(points);
  if (!hull) return "";

  // Expand hull by padding
  const centroid = d3.polygonCentroid(hull);
  const expandedHull = hull.map(([x, y]) => {
    const dx = x - centroid[0];
    const dy = y - centroid[1];
    const len = Math.sqrt(dx * dx + dy * dy);
    return [x + (dx / len) * padding, y + (dy / len) * padding] as [number, number];
  });

  // Create smooth curve through points
  const line = d3.line().curve(d3.curveCatmullRomClosed.alpha(0.5));
  return line(expandedHull) || "";
}

// Generate curved path for an edge
export function getLinkPath(source: SimulationNode, target: SimulationNode): string {
  const sx = source.x || 0;
  const sy = source.y || 0;
  const tx = target.x || 0;
  const ty = target.y || 0;

  const dx = tx - sx;
  const dy = ty - sy;

  // Slight curve
  return `M${sx},${sy}Q${(sx + tx) / 2 + dy * 0.1},${(sy + ty) / 2 - dx * 0.1},${tx},${ty}`;
}
