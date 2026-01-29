"use client";

import type { GraphNode as APIGraphNode, GraphEdge as APIGraphEdge } from "@/lib/api";
import * as d3 from "d3";

// Extended types for D3 simulation
export interface SimulationNode extends APIGraphNode {
  x?: number;
  y?: number;
  fx?: number | null;
  fy?: number | null;
  vx?: number;
  vy?: number;
  initialAngle?: number;
  initialRadius?: number;
}

export interface SimulationEdge {
  id: string;
  source_node_id: string;
  target_node_id: string;
  edge_type: string;
  source: SimulationNode | string;
  target: SimulationNode | string;
  // Temporal fields
  temporality: string | null;
  temporal_confidence: number | null;
  event_date: string | null;
}

export interface KnowledgeGraphProps {
  nodes: APIGraphNode[];
  edges: APIGraphEdge[];
  patientId: string;
}

export type LayoutMode = "force" | "radial";

export interface NodeConfig {
  color: string;
  colorEnd: string;
  glow: string;
  label: string;
  icon: string;
  radius: number;
  ringOrder: number;
}

export interface GraphDimensions {
  width: number;
  height: number;
}

export interface TooltipPosition {
  x: number;
  y: number;
}

export interface MenuState {
  isOpen: boolean;
  x: number;
  y: number;
  nodeId: string | null;
}

// Re-export for convenience
export type { APIGraphNode, APIGraphEdge };
export type ZoomTransform = d3.ZoomTransform;
