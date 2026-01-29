"use client";

import { useEffect, useRef, useCallback, useMemo } from "react";
import * as d3 from "d3";

/**
 * Canvas-based renderer for large knowledge graphs (1000+ nodes).
 *
 * Uses HTML5 Canvas for fast rendering of nodes and edges,
 * with an SVG overlay for interactive elements like selections and labels.
 *
 * Performance optimizations:
 * - Canvas rendering instead of SVG for nodes/edges
 * - Quadtree for fast hit testing
 * - Level-of-detail based on zoom level
 * - Culling of off-screen elements
 * - RequestAnimationFrame for smooth updates
 */

// Base node interface - compatible with parent's CanvasNode
export interface CanvasNode {
  id: string;
  label: string;
  node_type: string;
  x?: number;
  y?: number;
  fx?: number | null;
  fy?: number | null;
  vx?: number;
  vy?: number;
  [key: string]: unknown; // Allow additional properties
}

// Base edge interface - compatible with parent's CanvasEdge
export interface CanvasEdge {
  id: string;
  source_node_id: string;
  target_node_id: string;
  edge_type: string;
  source: CanvasNode | string;
  target: CanvasNode | string;
  temporality?: string | null;
  temporal_confidence?: number | null;
  [key: string]: unknown; // Allow additional properties
}

interface NodeConfig {
  color: string;
  colorEnd?: string;
  glow?: string;
  radius: number;
}

interface CanvasRendererProps {
  nodes: CanvasNode[];
  edges: CanvasEdge[];
  width: number;
  height: number;
  transform: d3.ZoomTransform;
  selectedNodeId: string | null;
  hoveredNodeId: string | null;
  pinnedNodes: Set<string>;
  searchHighlightedNodes: Set<string> | null;
  nodeConfig: Record<string, NodeConfig>;
  showLabels: boolean;
  temporalFilterEnabled: boolean;
  onNodeClick: (node: CanvasNode, event: MouseEvent) => void;
  onNodeHover: (node: CanvasNode | null, x: number, y: number) => void;
  onNodeContextMenu: (node: CanvasNode, event: MouseEvent) => void;
  onBackgroundClick: () => void;
}

// Temporality colors for edge rendering
const TEMPORALITY_COLORS: Record<string, string> = {
  current: "#22c55e",
  past: "#f59e0b",
  future: "#3b82f6",
};

export function CanvasRenderer({
  nodes,
  edges,
  width,
  height,
  transform,
  selectedNodeId,
  hoveredNodeId,
  pinnedNodes,
  searchHighlightedNodes,
  nodeConfig,
  showLabels,
  temporalFilterEnabled,
  onNodeClick,
  onNodeHover,
  onNodeContextMenu,
  onBackgroundClick,
}: CanvasRendererProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const overlayRef = useRef<SVGSVGElement>(null);
  const quadtreeRef = useRef<d3.Quadtree<CanvasNode> | null>(null);
  const animationFrameRef = useRef<number | null>(null);

  // Build quadtree for fast hit testing
  const quadtree = useMemo(() => {
    const qt = d3.quadtree<CanvasNode>()
      .x(d => d.x ?? 0)
      .y(d => d.y ?? 0)
      .addAll(nodes.filter(n => n.x !== undefined && n.y !== undefined));
    quadtreeRef.current = qt;
    return qt;
  }, [nodes]);

  // Find node at screen coordinates
  const findNodeAtPoint = useCallback((screenX: number, screenY: number): CanvasNode | null => {
    if (!quadtreeRef.current) return null;

    // Transform screen coordinates to graph coordinates
    const graphX = transform.invertX(screenX);
    const graphY = transform.invertY(screenY);

    // Search radius based on zoom level
    const searchRadius = 30 / transform.k;

    let closestNode: CanvasNode | null = null;
    let closestDistance = Infinity;

    quadtreeRef.current.visit((node, x0, y0, x1, y1) => {
      // Check if this quadrant could contain a closer node
      const dx = graphX < x0 ? x0 - graphX : graphX > x1 ? graphX - x1 : 0;
      const dy = graphY < y0 ? y0 - graphY : graphY > y1 ? graphY - y1 : 0;
      if (dx * dx + dy * dy > searchRadius * searchRadius) {
        return true; // Skip this quadrant
      }

      // Check leaf nodes - cast to access data property
      if (!node.length) {
        const leafNode = node as d3.QuadtreeLeaf<CanvasNode>;
        if (!leafNode.data) return false;
        const d = leafNode.data;
        const distance = Math.sqrt(
          Math.pow((d.x ?? 0) - graphX, 2) + Math.pow((d.y ?? 0) - graphY, 2)
        );
        const nodeRadius = (nodeConfig[d.node_type]?.radius ?? 16) / transform.k;

        if (distance < nodeRadius * 1.5 && distance < closestDistance) {
          closestDistance = distance;
          closestNode = d;
        }
      }
      return false;
    });

    return closestNode;
  }, [transform, nodeConfig]);

  // Canvas rendering function
  const render = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;

    // Clear canvas
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.restore();

    // Apply transform
    ctx.save();
    ctx.translate(transform.x * dpr, transform.y * dpr);
    ctx.scale(transform.k * dpr, transform.k * dpr);

    // Calculate visible bounds for culling
    const visibleBounds = {
      x0: -transform.x / transform.k - 100,
      y0: -transform.y / transform.k - 100,
      x1: (width - transform.x) / transform.k + 100,
      y1: (height - transform.y) / transform.k + 100,
    };

    // Determine level of detail based on zoom
    const lod = transform.k < 0.3 ? "low" : transform.k < 0.7 ? "medium" : "high";

    // Draw edges
    ctx.lineWidth = 1.5 / transform.k;
    ctx.lineCap = "round";

    for (const edge of edges) {
      const source = typeof edge.source === "string"
        ? nodes.find(n => n.id === edge.source)
        : edge.source;
      const target = typeof edge.target === "string"
        ? nodes.find(n => n.id === edge.target)
        : edge.target;

      if (!source?.x || !source?.y || !target?.x || !target?.y) continue;

      // Culling: skip edges outside visible bounds
      const edgeBounds = {
        x0: Math.min(source.x, target.x),
        y0: Math.min(source.y, target.y),
        x1: Math.max(source.x, target.x),
        y1: Math.max(source.y, target.y),
      };

      if (edgeBounds.x1 < visibleBounds.x0 || edgeBounds.x0 > visibleBounds.x1 ||
          edgeBounds.y1 < visibleBounds.y0 || edgeBounds.y0 > visibleBounds.y1) {
        continue;
      }

      // Edge color based on temporality or target node type
      let edgeColor: string;
      if (temporalFilterEnabled && edge.temporality) {
        edgeColor = TEMPORALITY_COLORS[edge.temporality] ?? "#64748b";
      } else {
        edgeColor = nodeConfig[target.node_type]?.color ?? "#64748b";
      }

      // Edge opacity based on confidence when temporal filter enabled
      let edgeOpacity = 0.4;
      if (temporalFilterEnabled && edge.temporal_confidence !== null && edge.temporal_confidence !== undefined) {
        edgeOpacity = 0.3 + edge.temporal_confidence * 0.5;
      }

      ctx.strokeStyle = edgeColor;
      ctx.globalAlpha = edgeOpacity;

      // Draw curved edge
      const midX = (source.x + target.x) / 2;
      const midY = (source.y + target.y) / 2;
      const dx = target.x - source.x;
      const dy = target.y - source.y;
      const offset = Math.min(Math.sqrt(dx * dx + dy * dy) * 0.1, 30);
      const controlX = midX - dy * offset / Math.sqrt(dx * dx + dy * dy + 1);
      const controlY = midY + dx * offset / Math.sqrt(dx * dx + dy * dy + 1);

      ctx.beginPath();
      ctx.moveTo(source.x, source.y);
      ctx.quadraticCurveTo(controlX, controlY, target.x, target.y);
      ctx.stroke();

      // Draw arrowhead (only at high LOD)
      if (lod === "high") {
        const angle = Math.atan2(target.y - controlY, target.x - controlX);
        const arrowSize = 6;
        const targetRadius = nodeConfig[target.node_type]?.radius ?? 16;
        const arrowX = target.x - Math.cos(angle) * (targetRadius + 2);
        const arrowY = target.y - Math.sin(angle) * (targetRadius + 2);

        ctx.beginPath();
        ctx.moveTo(arrowX, arrowY);
        ctx.lineTo(
          arrowX - arrowSize * Math.cos(angle - Math.PI / 6),
          arrowY - arrowSize * Math.sin(angle - Math.PI / 6)
        );
        ctx.lineTo(
          arrowX - arrowSize * Math.cos(angle + Math.PI / 6),
          arrowY - arrowSize * Math.sin(angle + Math.PI / 6)
        );
        ctx.closePath();
        ctx.fillStyle = edgeColor;
        ctx.fill();
      }
    }

    ctx.globalAlpha = 1;

    // Draw nodes
    for (const node of nodes) {
      if (node.x === undefined || node.y === undefined) continue;

      // Culling: skip nodes outside visible bounds
      if (node.x < visibleBounds.x0 || node.x > visibleBounds.x1 ||
          node.y < visibleBounds.y0 || node.y > visibleBounds.y1) {
        continue;
      }

      const config = nodeConfig[node.node_type] ?? { color: "#a1a1aa", radius: 14 };
      const radius = config.radius;
      const isSelected = node.id === selectedNodeId;
      const isHovered = node.id === hoveredNodeId;
      const isPinned = pinnedNodes.has(node.id);
      const isSearchHighlighted = searchHighlightedNodes?.has(node.id);

      // Draw glow for selected/highlighted nodes
      if (isSelected || isSearchHighlighted) {
        const glowRadius = radius + 8;
        const gradient = ctx.createRadialGradient(
          node.x, node.y, radius,
          node.x, node.y, glowRadius
        );
        gradient.addColorStop(0, config.glow ?? config.color);
        gradient.addColorStop(1, "transparent");
        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(node.x, node.y, glowRadius, 0, Math.PI * 2);
        ctx.fill();
      }

      // Draw node circle with gradient
      const nodeGradient = ctx.createRadialGradient(
        node.x - radius * 0.3, node.y - radius * 0.3, 0,
        node.x, node.y, radius
      );
      nodeGradient.addColorStop(0, config.color);
      nodeGradient.addColorStop(1, config.colorEnd ?? config.color);

      ctx.fillStyle = nodeGradient;
      ctx.beginPath();
      ctx.arc(node.x, node.y, radius, 0, Math.PI * 2);
      ctx.fill();

      // Draw border
      ctx.strokeStyle = isSelected ? "#fff" : isHovered ? "#e2e8f0" : "rgba(255,255,255,0.3)";
      ctx.lineWidth = isSelected ? 3 : isHovered ? 2 : 1;
      ctx.stroke();

      // Draw pin indicator
      if (isPinned) {
        ctx.fillStyle = "#fbbf24";
        ctx.beginPath();
        ctx.arc(node.x + radius * 0.7, node.y - radius * 0.7, 4, 0, Math.PI * 2);
        ctx.fill();
      }

      // Draw label (only at high LOD or for important nodes)
      if (showLabels && (lod === "high" || isSelected || isHovered || node.node_type === "patient")) {
        const labelText = node.label.length > 20 ? node.label.slice(0, 17) + "..." : node.label;
        const fontSize = Math.max(10, 12 / Math.sqrt(transform.k));

        ctx.font = `${fontSize}px Inter, system-ui, sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "top";

        // Text background
        const textMetrics = ctx.measureText(labelText);
        const textWidth = textMetrics.width;
        const textHeight = fontSize;
        const padding = 3;

        ctx.fillStyle = "rgba(15, 23, 42, 0.85)";
        ctx.beginPath();
        ctx.roundRect(
          node.x - textWidth / 2 - padding,
          node.y + radius + 4,
          textWidth + padding * 2,
          textHeight + padding * 2,
          3
        );
        ctx.fill();

        // Text
        ctx.fillStyle = "#e2e8f0";
        ctx.fillText(labelText, node.x, node.y + radius + 6 + padding);
      }
    }

    ctx.restore();
  }, [
    nodes, edges, width, height, transform, selectedNodeId, hoveredNodeId,
    pinnedNodes, searchHighlightedNodes, nodeConfig, showLabels, temporalFilterEnabled
  ]);

  // Set up canvas size and DPR
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;

    render();
  }, [width, height, render]);

  // Re-render on any changes
  useEffect(() => {
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
    }
    animationFrameRef.current = requestAnimationFrame(render);

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [render]);

  // Mouse event handlers
  const handleMouseMove = useCallback((event: React.MouseEvent) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;

    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const node = findNodeAtPoint(x, y);

    onNodeHover(node, event.clientX, event.clientY);
  }, [findNodeAtPoint, onNodeHover]);

  const handleClick = useCallback((event: React.MouseEvent) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;

    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const node = findNodeAtPoint(x, y);

    if (node) {
      onNodeClick(node, event.nativeEvent);
    } else {
      onBackgroundClick();
    }
  }, [findNodeAtPoint, onNodeClick, onBackgroundClick]);

  const handleContextMenu = useCallback((event: React.MouseEvent) => {
    event.preventDefault();

    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;

    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const node = findNodeAtPoint(x, y);

    if (node) {
      onNodeContextMenu(node, event.nativeEvent);
    }
  }, [findNodeAtPoint, onNodeContextMenu]);

  return (
    <div className="relative" style={{ width, height }}>
      <canvas
        ref={canvasRef}
        className="absolute inset-0"
        style={{ cursor: hoveredNodeId ? "pointer" : "default" }}
        onMouseMove={handleMouseMove}
        onClick={handleClick}
        onContextMenu={handleContextMenu}
      />
      {/* SVG overlay for additional interactive elements could go here */}
      <svg
        ref={overlayRef}
        className="absolute inset-0 pointer-events-none"
        width={width}
        height={height}
      >
        {/* Selection rings, tooltips, etc. can be rendered here */}
      </svg>
    </div>
  );
}

export default CanvasRenderer;
