"use client";

import type { NodeConfig } from "./types";

// Node type configuration with vibrant 2026 medical color palette
export const NODE_CONFIG: Record<string, NodeConfig> = {
  patient: {
    color: "#a78bfa",
    colorEnd: "#7c3aed",
    glow: "#8b5cf6",
    label: "Patient",
    icon: "M12 4.354a4 4 0 110 5.292M15 21H9m6 0a2 2 0 100-4H9a2 2 0 100 4m6 0v-4H9v4m3-14v4",
    radius: 28,
    ringOrder: 0,
  },
  condition: {
    color: "#fb7185",
    colorEnd: "#e11d48",
    glow: "#f43f5e",
    label: "Conditions",
    icon: "M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z",
    radius: 18,
    ringOrder: 1,
  },
  drug: {
    color: "#38bdf8",
    colorEnd: "#0284c7",
    glow: "#0ea5e9",
    label: "Drugs",
    icon: "M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z",
    radius: 16,
    ringOrder: 2,
  },
  measurement: {
    color: "#4ade80",
    colorEnd: "#16a34a",
    glow: "#22c55e",
    label: "Measurements",
    icon: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z",
    radius: 16,
    ringOrder: 3,
  },
  procedure: {
    color: "#fbbf24",
    colorEnd: "#d97706",
    glow: "#f59e0b",
    label: "Procedures",
    icon: "M12 14l9-5-9-5-9 5 9 5zm0 7l9-5-9-5-9 5 9 5z",
    radius: 16,
    ringOrder: 4,
  },
  observation: {
    color: "#a1a1aa",
    colorEnd: "#71717a",
    glow: "#a1a1aa",
    label: "Observations",
    icon: "M15 12a3 3 0 11-6 0 3 3 0 016 0z M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z",
    radius: 14,
    ringOrder: 5,
  },
  device: {
    color: "#f472b6",
    colorEnd: "#db2777",
    glow: "#ec4899",
    label: "Devices",
    icon: "M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z",
    radius: 14,
    ringOrder: 6,
  },
};

// Get node config with fallback to observation
export function getNodeConfig(nodeType: string): NodeConfig {
  return NODE_CONFIG[nodeType] || NODE_CONFIG.observation;
}

// Get node config for canvas renderer (subset of properties)
export function getNodeConfigForCanvas(): Record<string, { color: string; colorEnd: string; glow: string; radius: number }> {
  const config: Record<string, { color: string; colorEnd: string; glow: string; radius: number }> = {};
  for (const [type, c] of Object.entries(NODE_CONFIG)) {
    config[type] = {
      color: c.color,
      colorEnd: c.colorEnd,
      glow: c.glow,
      radius: c.radius,
    };
  }
  return config;
}
