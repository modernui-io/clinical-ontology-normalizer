"use client";

import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import * as d3 from "d3";
import type { GraphNode as APIGraphNode, GraphEdge as APIGraphEdge } from "@/lib/api";

// Extended types for D3 simulation
interface SimulationNode extends APIGraphNode {
  x?: number;
  y?: number;
  fx?: number | null;
  fy?: number | null;
  vx?: number;
  vy?: number;
  initialAngle?: number;
  initialRadius?: number;
}

interface SimulationEdge {
  id: string;
  source_node_id: string;
  target_node_id: string;
  edge_type: string;
  source: SimulationNode | string;
  target: SimulationNode | string;
}

interface KnowledgeGraphProps {
  nodes: APIGraphNode[];
  edges: APIGraphEdge[];
  patientId: string;
}

type LayoutMode = "force" | "radial";

// Node type configuration with medical-inspired colors and icons
const NODE_CONFIG: Record<string, {
  color: string;
  glow: string;
  label: string;
  icon: string;
  radius: number;
  ringOrder: number;
}> = {
  patient: {
    color: "#a78bfa",
    glow: "#8b5cf6",
    label: "Patient",
    icon: "M12 4.354a4 4 0 110 5.292M15 21H9m6 0a2 2 0 100-4H9a2 2 0 100 4m6 0v-4H9v4m3-14v4",
    radius: 28,
    ringOrder: 0,
  },
  condition: {
    color: "#f87171",
    glow: "#ef4444",
    label: "Conditions",
    icon: "M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z",
    radius: 18,
    ringOrder: 1,
  },
  drug: {
    color: "#60a5fa",
    glow: "#3b82f6",
    label: "Drugs",
    icon: "M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z",
    radius: 16,
    ringOrder: 2,
  },
  measurement: {
    color: "#4ade80",
    glow: "#22c55e",
    label: "Measurements",
    icon: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z",
    radius: 16,
    ringOrder: 3,
  },
  procedure: {
    color: "#fb923c",
    glow: "#f97316",
    label: "Procedures",
    icon: "M12 14l9-5-9-5-9 5 9 5zm0 7l9-5-9-5-9 5 9 5z",
    radius: 16,
    ringOrder: 4,
  },
  observation: {
    color: "#94a3b8",
    glow: "#64748b",
    label: "Observations",
    icon: "M15 12a3 3 0 11-6 0 3 3 0 016 0z M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z",
    radius: 14,
    ringOrder: 5,
  },
  device: {
    color: "#f472b6",
    glow: "#ec4899",
    label: "Devices",
    icon: "M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z",
    radius: 14,
    ringOrder: 6,
  },
};

const EDGE_LABELS: Record<string, string> = {
  has_condition: "has",
  takes_drug: "takes",
  has_measurement: "measured",
  has_procedure: "underwent",
  has_observation: "observed",
  has_device: "uses",
  condition_treated_by: "treated by",
  drug_treats: "treats",
};

// Convex hull with padding
function getHullPath(points: [number, number][], padding: number = 30): string {
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

export default function KnowledgeGraph({ nodes, edges, patientId }: KnowledgeGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const minimapRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [hoveredNode, setHoveredNode] = useState<SimulationNode | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });
  const [activeFilters, setActiveFilters] = useState<Set<string>>(
    new Set(Object.keys(NODE_CONFIG))
  );
  const [layoutMode, setLayoutMode] = useState<LayoutMode>("radial");
  const [searchQuery, setSearchQuery] = useState("");
  const [showHulls, setShowHulls] = useState(true);
  const [showLabels, setShowLabels] = useState(true);
  const [detailsPanelNode, setDetailsPanelNode] = useState<SimulationNode | null>(null);
  const [currentTransform, setCurrentTransform] = useState<d3.ZoomTransform>(d3.zoomIdentity);
  const [nodeProvenance, setNodeProvenance] = useState<Record<string, unknown>[] | null>(null);
  const [provenanceLoading, setProvenanceLoading] = useState(false);

  // Filter nodes based on search
  const searchFilteredNodes = useMemo(() => {
    if (!searchQuery.trim()) return null;
    const query = searchQuery.toLowerCase();
    return new Set(
      nodes.filter(n => n.label.toLowerCase().includes(query)).map(n => n.id)
    );
  }, [nodes, searchQuery]);

  // Handle resize
  useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        const { width, height } = containerRef.current.getBoundingClientRect();
        setDimensions({ width, height: Math.max(height, 500) });
      }
    };

    updateDimensions();
    window.addEventListener("resize", updateDimensions);
    return () => window.removeEventListener("resize", updateDimensions);
  }, []);

  // Toggle filter
  const toggleFilter = useCallback((nodeType: string) => {
    setActiveFilters((prev) => {
      const next = new Set(prev);
      if (next.has(nodeType)) {
        next.delete(nodeType);
      } else {
        next.add(nodeType);
      }
      return next;
    });
  }, []);

  // Export functions
  const exportAsPNG = useCallback(() => {
    if (!svgRef.current) return;
    const svgData = new XMLSerializer().serializeToString(svgRef.current);
    const canvas = document.createElement("canvas");
    canvas.width = dimensions.width * 2;
    canvas.height = dimensions.height * 2;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.fillStyle = "#020617";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    const img = new Image();
    img.onload = () => {
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      const link = document.createElement("a");
      link.download = `knowledge-graph-${patientId}.png`;
      link.href = canvas.toDataURL("image/png");
      link.click();
    };
    img.src = "data:image/svg+xml;base64," + btoa(unescape(encodeURIComponent(svgData)));
  }, [dimensions, patientId]);

  const exportAsSVG = useCallback(() => {
    if (!svgRef.current) return;
    const svgData = new XMLSerializer().serializeToString(svgRef.current);
    const blob = new Blob([svgData], { type: "image/svg+xml" });
    const link = document.createElement("a");
    link.download = `knowledge-graph-${patientId}.svg`;
    link.href = URL.createObjectURL(blob);
    link.click();
  }, [patientId]);

  // D3 visualization
  useEffect(() => {
    if (!svgRef.current || !nodes.length) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const { width, height } = dimensions;
    const centerX = width / 2;
    const centerY = height / 2;

    // Filter nodes and edges based on active filters
    const filteredNodes = nodes.filter((n) => activeFilters.has(n.node_type));
    const filteredNodeIds = new Set(filteredNodes.map((n) => n.id));
    const filteredEdges = edges.filter(
      (e) =>
        filteredNodeIds.has(e.source_node_id) && filteredNodeIds.has(e.target_node_id)
    );

    // Create deep copies for D3 mutation with initial positions for radial layout
    const patientNode = filteredNodes.find(n => n.node_type === "patient");
    const nodeData: SimulationNode[] = filteredNodes.map((n, i) => {
      const config = NODE_CONFIG[n.node_type] || NODE_CONFIG.observation;
      const ringRadius = config.ringOrder * 120;
      const nodesOfType = filteredNodes.filter(fn => fn.node_type === n.node_type);
      const indexInType = nodesOfType.indexOf(n);
      const angleSpread = Math.PI * 2 / Math.max(nodesOfType.length, 1);
      const angle = indexInType * angleSpread + (config.ringOrder * 0.5); // Offset each ring

      return {
        ...n,
        x: n.node_type === "patient" ? centerX : centerX + Math.cos(angle) * ringRadius,
        y: n.node_type === "patient" ? centerY : centerY + Math.sin(angle) * ringRadius,
        initialAngle: angle,
        initialRadius: ringRadius,
      };
    });

    const edgeData: SimulationEdge[] = filteredEdges.map((e) => ({
      ...e,
      source: e.source_node_id,
      target: e.target_node_id,
    }));

    // Define gradients and filters
    const defs = svg.append("defs");

    // Glow filters
    const createGlowFilter = (id: string, stdDev: number) => {
      const filter = defs
        .append("filter")
        .attr("id", id)
        .attr("x", "-100%")
        .attr("y", "-100%")
        .attr("width", "300%")
        .attr("height", "300%");

      filter
        .append("feGaussianBlur")
        .attr("stdDeviation", stdDev)
        .attr("result", "coloredBlur");

      const feMerge = filter.append("feMerge");
      feMerge.append("feMergeNode").attr("in", "coloredBlur");
      feMerge.append("feMergeNode").attr("in", "SourceGraphic");
    };

    createGlowFilter("glow", 3);
    createGlowFilter("glow-selected", 8);
    createGlowFilter("glow-search", 12);

    // Negation pattern
    const negationPattern = defs
      .append("pattern")
      .attr("id", "negation-pattern")
      .attr("patternUnits", "userSpaceOnUse")
      .attr("width", 8)
      .attr("height", 8)
      .attr("patternTransform", "rotate(45)");

    negationPattern
      .append("line")
      .attr("x1", 0)
      .attr("y1", 0)
      .attr("x2", 0)
      .attr("y2", 8)
      .attr("stroke", "#ef4444")
      .attr("stroke-width", 2);

    // Arrow markers with different colors
    Object.entries(NODE_CONFIG).forEach(([type, config]) => {
      defs
        .append("marker")
        .attr("id", `arrow-${type}`)
        .attr("viewBox", "-0 -5 10 10")
        .attr("refX", 25)
        .attr("refY", 0)
        .attr("orient", "auto")
        .attr("markerWidth", 5)
        .attr("markerHeight", 5)
        .append("path")
        .attr("d", "M 0,-4 L 8,0 L 0,4")
        .attr("fill", config.color)
        .attr("opacity", 0.6);
    });

    // Default arrow
    defs
      .append("marker")
      .attr("id", "arrow-default")
      .attr("viewBox", "-0 -5 10 10")
      .attr("refX", 25)
      .attr("refY", 0)
      .attr("orient", "auto")
      .attr("markerWidth", 5)
      .attr("markerHeight", 5)
      .append("path")
      .attr("d", "M 0,-4 L 8,0 L 0,4")
      .attr("fill", "#475569")
      .attr("opacity", 0.6);

    // Create zoom behavior
    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 6])
      .on("zoom", (event) => {
        container.attr("transform", event.transform);
        setCurrentTransform(event.transform);
      });

    svg.call(zoom);

    // Main container
    const container = svg.append("g").attr("class", "graph-container");

    // Create force simulation
    const simulation = d3
      .forceSimulation<SimulationNode>(nodeData)
      .force(
        "link",
        d3
          .forceLink<SimulationNode, SimulationEdge>(edgeData)
          .id((d) => d.id)
          .distance(layoutMode === "radial" ? 80 : 120)
          .strength(layoutMode === "radial" ? 0.3 : 0.5)
      )
      .force("charge", d3.forceManyBody().strength(layoutMode === "radial" ? -200 : -400))
      .force("collision", d3.forceCollide<SimulationNode>().radius((d) =>
        (NODE_CONFIG[d.node_type]?.radius || 16) + 10
      ));

    if (layoutMode === "radial") {
      // Radial layout: position nodes in rings around patient
      simulation
        .force("radial", d3.forceRadial<SimulationNode>(
          (d) => d.node_type === "patient" ? 0 : (NODE_CONFIG[d.node_type]?.ringOrder || 1) * 100,
          centerX,
          centerY
        ).strength(0.8))
        .force("center", null);

      // Pin patient to center
      const patient = nodeData.find(n => n.node_type === "patient");
      if (patient) {
        patient.fx = centerX;
        patient.fy = centerY;
      }
    } else {
      // Force layout
      simulation
        .force("center", d3.forceCenter(centerX, centerY))
        .force("x", d3.forceX(centerX).strength(0.03))
        .force("y", d3.forceY(centerY).strength(0.03));
    }

    // Group nodes by type for hulls
    const nodesByType = d3.group(nodeData, d => d.node_type);

    // Draw convex hulls for each node type (background)
    const hullGroup = container.append("g").attr("class", "hulls");

    const hulls = hullGroup
      .selectAll<SVGPathElement, [string, SimulationNode[]]>("path")
      .data(Array.from(nodesByType.entries()).filter(([type]) => type !== "patient"))
      .join("path")
      .attr("class", "hull")
      .attr("fill", ([type]) => NODE_CONFIG[type]?.color || "#94a3b8")
      .attr("fill-opacity", showHulls ? 0.08 : 0)
      .attr("stroke", ([type]) => NODE_CONFIG[type]?.color || "#94a3b8")
      .attr("stroke-opacity", showHulls ? 0.2 : 0)
      .attr("stroke-width", 1)
      .style("transition", "fill-opacity 0.3s, stroke-opacity 0.3s");

    // Draw edges with curves
    const linkGroup = container.append("g").attr("class", "links");

    const link = linkGroup
      .selectAll<SVGPathElement, SimulationEdge>("path")
      .data(edgeData)
      .join("path")
      .attr("fill", "none")
      .attr("stroke", (d) => {
        const targetNode = nodeData.find(n => n.id === d.target_node_id);
        return NODE_CONFIG[targetNode?.node_type || "observation"]?.color || "#475569";
      })
      .attr("stroke-width", 1.5)
      .attr("stroke-opacity", 0.4)
      .attr("marker-end", (d) => {
        const targetNode = nodeData.find(n => n.id === d.target_node_id);
        return `url(#arrow-${targetNode?.node_type || "default"})`;
      })
      .style("transition", "stroke-opacity 0.3s ease");

    // Edge labels (hidden by default)
    const linkLabels = container
      .append("g")
      .attr("class", "link-labels")
      .selectAll<SVGTextElement, SimulationEdge>("text")
      .data(edgeData)
      .join("text")
      .attr("font-size", "8px")
      .attr("fill", "#94a3b8")
      .attr("text-anchor", "middle")
      .attr("dy", -6)
      .text((d) => EDGE_LABELS[d.edge_type] || d.edge_type)
      .style("pointer-events", "none")
      .style("opacity", 0)
      .style("font-weight", "500");

    // Draw nodes
    const nodeGroup = container.append("g").attr("class", "nodes");

    const node = nodeGroup
      .selectAll<SVGGElement, SimulationNode>("g")
      .data(nodeData)
      .join("g")
      .attr("class", "node")
      .style("cursor", "pointer")
      .style("opacity", 0)
      .call(
        d3
          .drag<SVGGElement, SimulationNode>()
          .on("start", (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on("drag", (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on("end", (event, d) => {
            if (!event.active) simulation.alphaTarget(0);
            // In radial mode, only keep patient pinned
            if (layoutMode === "radial" && d.node_type !== "patient") {
              d.fx = null;
              d.fy = null;
            } else if (layoutMode !== "radial") {
              d.fx = null;
              d.fy = null;
            }
          })
      );

    // Staggered entrance animation
    node
      .transition()
      .delay((_, i) => i * 30)
      .duration(500)
      .ease(d3.easeCubicOut)
      .style("opacity", 1);

    // Node outer ring (for search highlight)
    node
      .append("circle")
      .attr("class", "search-ring")
      .attr("r", (d) => (NODE_CONFIG[d.node_type]?.radius || 16) + 6)
      .attr("fill", "none")
      .attr("stroke", "#fbbf24")
      .attr("stroke-width", 3)
      .attr("opacity", 0);

    // Node background circle (for negation pattern)
    node
      .filter((d) => Boolean(d.properties?.is_negated))
      .append("circle")
      .attr("class", "negation-bg")
      .attr("r", (d) => NODE_CONFIG[d.node_type]?.radius || 16)
      .attr("fill", "url(#negation-pattern)")
      .attr("opacity", 0.3);

    // Node main circle
    node
      .append("circle")
      .attr("class", "node-circle")
      .attr("r", (d) => NODE_CONFIG[d.node_type]?.radius || 16)
      .attr("fill", (d) => {
        if (d.properties?.is_negated) {
          return d3.color(NODE_CONFIG[d.node_type]?.color || "#94a3b8")?.darker(0.5)?.toString() || "#94a3b8";
        }
        return NODE_CONFIG[d.node_type]?.color || "#94a3b8";
      })
      .attr("stroke", (d) => NODE_CONFIG[d.node_type]?.glow || "#64748b")
      .attr("stroke-width", 2)
      .attr("filter", "url(#glow)")
      .style("transition", "all 0.3s ease");

    // Node icons
    node
      .append("path")
      .attr("d", (d) => NODE_CONFIG[d.node_type]?.icon || "")
      .attr("fill", "none")
      .attr("stroke", "white")
      .attr("stroke-width", 1.5)
      .attr("stroke-linecap", "round")
      .attr("stroke-linejoin", "round")
      .attr("transform", (d) => {
        const r = NODE_CONFIG[d.node_type]?.radius || 16;
        const scale = r / 20;
        return `translate(${-12 * scale}, ${-12 * scale}) scale(${scale})`;
      })
      .attr("opacity", 0.9)
      .style("pointer-events", "none");

    // Negation X mark for negated nodes
    node
      .filter((d) => Boolean(d.properties?.is_negated))
      .append("g")
      .attr("class", "negation-mark")
      .each(function(d) {
        const r = NODE_CONFIG[d.node_type]?.radius || 16;
        d3.select(this)
          .append("circle")
          .attr("cx", r * 0.7)
          .attr("cy", -r * 0.7)
          .attr("r", 8)
          .attr("fill", "#dc2626")
          .attr("stroke", "#020617")
          .attr("stroke-width", 2);

        d3.select(this)
          .append("text")
          .attr("x", r * 0.7)
          .attr("y", -r * 0.7)
          .attr("text-anchor", "middle")
          .attr("dy", 4)
          .attr("fill", "white")
          .attr("font-size", "10px")
          .attr("font-weight", "bold")
          .text("✕");
      });

    // Node labels
    node
      .append("text")
      .attr("class", "node-label")
      .attr("dy", (d) => (NODE_CONFIG[d.node_type]?.radius || 16) + 14)
      .attr("text-anchor", "middle")
      .attr("fill", "#e2e8f0")
      .attr("font-size", (d) => (d.node_type === "patient" ? "11px" : "9px"))
      .attr("font-weight", (d) => (d.node_type === "patient" ? "600" : "500"))
      .text((d) => {
        const maxLen = 18;
        return d.label.length > maxLen ? d.label.slice(0, maxLen) + "…" : d.label;
      })
      .style("pointer-events", "none")
      .style("text-shadow", "0 2px 4px rgba(0,0,0,0.9)")
      .style("opacity", showLabels ? 1 : 0);

    // Update search highlighting
    const updateSearchHighlight = () => {
      node.select(".search-ring")
        .attr("opacity", (d) =>
          searchFilteredNodes && searchFilteredNodes.has(d.id) ? 1 : 0
        )
        .attr("filter", (d) =>
          searchFilteredNodes && searchFilteredNodes.has(d.id) ? "url(#glow-search)" : "none"
        );
    };
    updateSearchHighlight();

    // Node interactions
    node
      .on("mouseenter", function (event, d) {
        setHoveredNode(d);
        setTooltipPos({ x: event.pageX, y: event.pageY });

        d3.select(this)
          .select(".node-circle")
          .attr("filter", "url(#glow-selected)")
          .attr("stroke-width", 3);

        // Show connected edge labels
        linkLabels.style("opacity", (l) => {
          const source = typeof l.source === "object" ? l.source.id : l.source;
          const target = typeof l.target === "object" ? l.target.id : l.target;
          return source === d.id || target === d.id ? 1 : 0;
        });

        // Highlight connected edges
        link.attr("stroke-opacity", (l) => {
          const source = typeof l.source === "object" ? l.source.id : l.source;
          const target = typeof l.target === "object" ? l.target.id : l.target;
          return source === d.id || target === d.id ? 0.9 : 0.15;
        });
      })
      .on("mousemove", (event) => {
        setTooltipPos({ x: event.pageX, y: event.pageY });
      })
      .on("mouseleave", function (_, d) {
        setHoveredNode(null);

        if (selectedNode !== d.id) {
          d3.select(this)
            .select(".node-circle")
            .attr("filter", "url(#glow)")
            .attr("stroke-width", 2);
        }

        linkLabels.style("opacity", 0);
        link.attr("stroke-opacity", 0.4);
      })
      .on("click", function (event, d) {
        event.stopPropagation();
        const newSelected = selectedNode === d.id ? null : d.id;
        setSelectedNode(newSelected);
        setDetailsPanelNode(newSelected ? d : null);

        // Reset all nodes
        node
          .select(".node-circle")
          .attr("filter", "url(#glow)")
          .attr("stroke-width", 2)
          .style("opacity", 1);

        node.select(".node-label").style("opacity", showLabels ? 1 : 0);
        link.attr("stroke-opacity", 0.4);

        if (newSelected) {
          const connectedIds = new Set<string>();
          connectedIds.add(newSelected);

          edgeData.forEach((e) => {
            const source = typeof e.source === "object" ? e.source.id : e.source;
            const target = typeof e.target === "object" ? e.target.id : e.target;
            if (source === newSelected) connectedIds.add(target as string);
            if (target === newSelected) connectedIds.add(source as string);
          });

          node
            .select(".node-circle")
            .style("opacity", (n) => (connectedIds.has(n.id) ? 1 : 0.15));

          node
            .select(".node-label")
            .style("opacity", (n) => (connectedIds.has(n.id) && showLabels ? 1 : 0.15));

          link.attr("stroke-opacity", (l) => {
            const source = typeof l.source === "object" ? l.source.id : l.source;
            const target = typeof l.target === "object" ? l.target.id : l.target;
            return source === newSelected || target === newSelected ? 0.9 : 0.05;
          });

          d3.select(this)
            .select(".node-circle")
            .attr("filter", "url(#glow-selected)")
            .attr("stroke-width", 3);
        }
      })
      .on("dblclick", (event, d) => {
        event.stopPropagation();
        setDetailsPanelNode(d);
      });

    // Background click to deselect
    svg.on("click", () => {
      setSelectedNode(null);
      setDetailsPanelNode(null);
      node
        .select(".node-circle")
        .attr("filter", "url(#glow)")
        .attr("stroke-width", 2)
        .style("opacity", 1);
      node.select(".node-label").style("opacity", showLabels ? 1 : 0);
      link.attr("stroke-opacity", 0.4);
    });

    // Curved path generator
    const linkPath = (d: SimulationEdge): string => {
      const source = d.source as SimulationNode;
      const target = d.target as SimulationNode;
      const sx = source.x || 0;
      const sy = source.y || 0;
      const tx = target.x || 0;
      const ty = target.y || 0;

      const dx = tx - sx;
      const dy = ty - sy;
      const dr = Math.sqrt(dx * dx + dy * dy) * 0.8;

      // Slight curve
      return `M${sx},${sy}Q${(sx + tx) / 2 + dy * 0.1},${(sy + ty) / 2 - dx * 0.1},${tx},${ty}`;
    };

    // Simulation tick
    simulation.on("tick", () => {
      // Update hulls
      hulls.attr("d", ([type, nodes]) => {
        const points: [number, number][] = nodes.map(n => [n.x || 0, n.y || 0]);
        return getHullPath(points, 35);
      });

      // Update edges with curves
      link.attr("d", linkPath);

      // Update edge labels
      linkLabels
        .attr("x", (d) => {
          const source = d.source as SimulationNode;
          const target = d.target as SimulationNode;
          return ((source.x || 0) + (target.x || 0)) / 2;
        })
        .attr("y", (d) => {
          const source = d.source as SimulationNode;
          const target = d.target as SimulationNode;
          return ((source.y || 0) + (target.y || 0)) / 2;
        });

      // Update nodes
      node.attr("transform", (d) => `translate(${d.x || 0},${d.y || 0})`);
    });

    // Initial zoom to fit
    const initialScale = 0.85;
    svg.call(
      zoom.transform,
      d3.zoomIdentity
        .translate(width * (1 - initialScale) / 2, height * (1 - initialScale) / 2)
        .scale(initialScale)
    );

    return () => {
      simulation.stop();
    };
  }, [nodes, edges, dimensions, activeFilters, layoutMode, showHulls, showLabels, searchFilteredNodes, selectedNode]);

  // Update minimap
  useEffect(() => {
    if (!minimapRef.current || !nodes.length) return;

    const svg = d3.select(minimapRef.current);
    svg.selectAll("*").remove();

    const minimapWidth = 150;
    const minimapHeight = 100;
    const scale = Math.min(minimapWidth / dimensions.width, minimapHeight / dimensions.height) * 0.8;

    // Draw nodes as small dots
    const filteredNodes = nodes.filter(n => activeFilters.has(n.node_type));

    svg.selectAll("circle")
      .data(filteredNodes)
      .join("circle")
      .attr("cx", (_, i) => 75 + Math.cos(i * 0.5) * 30)
      .attr("cy", (_, i) => 50 + Math.sin(i * 0.5) * 20)
      .attr("r", 2)
      .attr("fill", d => NODE_CONFIG[d.node_type]?.color || "#94a3b8")
      .attr("opacity", 0.8);

    // Draw viewport rectangle
    const viewportWidth = dimensions.width / currentTransform.k;
    const viewportHeight = dimensions.height / currentTransform.k;
    const viewportX = -currentTransform.x / currentTransform.k;
    const viewportY = -currentTransform.y / currentTransform.k;

    svg.append("rect")
      .attr("x", viewportX * scale + (minimapWidth - dimensions.width * scale) / 2)
      .attr("y", viewportY * scale + (minimapHeight - dimensions.height * scale) / 2)
      .attr("width", viewportWidth * scale)
      .attr("height", viewportHeight * scale)
      .attr("fill", "none")
      .attr("stroke", "#60a5fa")
      .attr("stroke-width", 1)
      .attr("opacity", 0.8);

  }, [nodes, dimensions, activeFilters, currentTransform]);

  // Fetch provenance when a node is selected in the details panel
  useEffect(() => {
    if (!detailsPanelNode) {
      setNodeProvenance(null);
      return;
    }

    const fetchProvenance = async () => {
      setProvenanceLoading(true);
      try {
        const response = await fetch(
          `/api/clinical-agent/lineage/${patientId}/${detailsPanelNode.id}`
        );
        if (response.ok) {
          const data = await response.json();
          setNodeProvenance(data.provenance_chain?.provenance_records ?? []);
        } else {
          setNodeProvenance([]);
        }
      } catch {
        setNodeProvenance([]);
      } finally {
        setProvenanceLoading(false);
      }
    };

    fetchProvenance();
  }, [detailsPanelNode, patientId]);

  // Get connected nodes for details panel
  const connectedNodes = useMemo(() => {
    if (!detailsPanelNode) return [];
    return edges
      .filter(e => e.source_node_id === detailsPanelNode.id || e.target_node_id === detailsPanelNode.id)
      .map(e => {
        const connectedId = e.source_node_id === detailsPanelNode.id ? e.target_node_id : e.source_node_id;
        const node = nodes.find(n => n.id === connectedId);
        return { edge: e, node };
      })
      .filter(item => item.node);
  }, [detailsPanelNode, edges, nodes]);

  return (
    <div className="relative w-full h-full min-h-[600px] bg-slate-950 rounded-xl overflow-hidden">
      {/* Animated gradient background */}
      <div className="absolute inset-0">
        <div
          className="absolute inset-0 opacity-30"
          style={{
            background: `
              radial-gradient(ellipse at 20% 20%, rgba(99, 102, 241, 0.15) 0%, transparent 50%),
              radial-gradient(ellipse at 80% 80%, rgba(236, 72, 153, 0.1) 0%, transparent 50%),
              radial-gradient(ellipse at 50% 50%, rgba(34, 197, 94, 0.08) 0%, transparent 60%)
            `,
          }}
        />
        <div
          className="absolute inset-0 opacity-[0.015]"
          style={{
            backgroundImage: `
              linear-gradient(rgba(148, 163, 184, 0.5) 1px, transparent 1px),
              linear-gradient(90deg, rgba(148, 163, 184, 0.5) 1px, transparent 1px)
            `,
            backgroundSize: '50px 50px',
          }}
        />
      </div>

      {/* Top toolbar */}
      <div className="absolute top-4 left-4 right-4 z-10 flex items-start justify-between gap-4">
        {/* Left controls */}
        <div className="flex flex-col gap-3">
          {/* Search */}
          <div className="bg-slate-900/95 backdrop-blur-sm rounded-lg border border-slate-800 overflow-hidden">
            <div className="flex items-center px-3 py-2 gap-2">
              <svg className="w-4 h-4 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                type="text"
                placeholder="Search nodes..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="bg-transparent text-sm text-slate-200 placeholder-slate-500 outline-none w-40"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery("")}
                  className="text-slate-500 hover:text-slate-300"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              )}
            </div>
            {searchFilteredNodes && searchFilteredNodes.size > 0 && (
              <div className="px-3 py-1 bg-slate-800/50 border-t border-slate-800 text-xs text-amber-400">
                {searchFilteredNodes.size} node{searchFilteredNodes.size !== 1 ? "s" : ""} found
              </div>
            )}
          </div>

          {/* Node type filters */}
          <div className="bg-slate-900/95 backdrop-blur-sm rounded-lg p-3 border border-slate-800">
            <div className="text-[10px] font-semibold text-slate-500 mb-2 uppercase tracking-wider">
              Node Types
            </div>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(NODE_CONFIG).map(([type, config]) => {
                const count = nodes.filter((n) => n.node_type === type).length;
                if (count === 0 && type !== "patient") return null;

                const isActive = activeFilters.has(type);
                return (
                  <button
                    key={type}
                    onClick={() => toggleFilter(type)}
                    className={`
                      flex items-center gap-1.5 px-2 py-1 rounded text-[11px] font-medium
                      transition-all duration-200 border
                      ${isActive
                        ? "border-slate-600 bg-slate-800/80"
                        : "border-slate-800 bg-slate-900/50 opacity-40"
                      }
                    `}
                  >
                    <span
                      className="w-2 h-2 rounded-full"
                      style={{
                        backgroundColor: config.color,
                        boxShadow: isActive ? `0 0 6px ${config.glow}` : "none",
                      }}
                    />
                    <span className="text-slate-300">{config.label}</span>
                    <span className="text-slate-500 tabular-nums">({count})</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Right controls */}
        <div className="flex flex-col gap-3 items-end">
          {/* Layout & view controls */}
          <div className="bg-slate-900/95 backdrop-blur-sm rounded-lg border border-slate-800 p-2 flex gap-1">
            <button
              onClick={() => setLayoutMode("radial")}
              className={`px-3 py-1.5 rounded text-xs font-medium transition-all ${
                layoutMode === "radial"
                  ? "bg-indigo-600 text-white"
                  : "text-slate-400 hover:text-white hover:bg-slate-800"
              }`}
              title="Radial layout - Patient centered"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <circle cx="12" cy="12" r="3" strokeWidth="2"/>
                <circle cx="12" cy="12" r="8" strokeWidth="1.5" strokeDasharray="2 2"/>
              </svg>
            </button>
            <button
              onClick={() => setLayoutMode("force")}
              className={`px-3 py-1.5 rounded text-xs font-medium transition-all ${
                layoutMode === "force"
                  ? "bg-indigo-600 text-white"
                  : "text-slate-400 hover:text-white hover:bg-slate-800"
              }`}
              title="Force-directed layout"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <circle cx="6" cy="6" r="2" strokeWidth="2"/>
                <circle cx="18" cy="6" r="2" strokeWidth="2"/>
                <circle cx="12" cy="18" r="2" strokeWidth="2"/>
                <path d="M8 6h8M7 8l4 8M17 8l-4 8" strokeWidth="1.5"/>
              </svg>
            </button>
            <div className="w-px bg-slate-700 mx-1" />
            <button
              onClick={() => setShowHulls(!showHulls)}
              className={`px-3 py-1.5 rounded text-xs font-medium transition-all ${
                showHulls
                  ? "bg-slate-700 text-white"
                  : "text-slate-500 hover:text-white hover:bg-slate-800"
              }`}
              title="Toggle group backgrounds"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6z" strokeWidth="2"/>
                <path d="M14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6z" strokeWidth="2"/>
                <path d="M4 16a2 2 0 012-2h12a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2z" strokeWidth="2"/>
              </svg>
            </button>
            <button
              onClick={() => setShowLabels(!showLabels)}
              className={`px-3 py-1.5 rounded text-xs font-medium transition-all ${
                showLabels
                  ? "bg-slate-700 text-white"
                  : "text-slate-500 hover:text-white hover:bg-slate-800"
              }`}
              title="Toggle labels"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M4 6h16M4 12h16M4 18h10" strokeWidth="2" strokeLinecap="round"/>
              </svg>
            </button>
          </div>

          {/* Stats */}
          <div className="bg-slate-900/95 backdrop-blur-sm rounded-lg px-3 py-2 border border-slate-800">
            <div className="flex items-center gap-4 text-xs">
              <div>
                <span className="text-slate-500">Nodes</span>
                <span className="ml-1.5 text-slate-200 font-semibold tabular-nums">
                  {nodes.filter((n) => activeFilters.has(n.node_type)).length}
                </span>
              </div>
              <div className="w-px h-4 bg-slate-700" />
              <div>
                <span className="text-slate-500">Edges</span>
                <span className="ml-1.5 text-slate-200 font-semibold tabular-nums">
                  {edges.filter((e) => {
                    const sourceNode = nodes.find((n) => n.id === e.source_node_id);
                    const targetNode = nodes.find((n) => n.id === e.target_node_id);
                    return sourceNode && targetNode &&
                      activeFilters.has(sourceNode.node_type) &&
                      activeFilters.has(targetNode.node_type);
                  }).length}
                </span>
              </div>
            </div>
          </div>

          {/* Export */}
          <div className="bg-slate-900/95 backdrop-blur-sm rounded-lg border border-slate-800 flex">
            <button
              onClick={exportAsPNG}
              className="px-3 py-2 text-xs text-slate-400 hover:text-white hover:bg-slate-800 transition-all rounded-l-lg border-r border-slate-800"
              title="Export as PNG"
            >
              PNG
            </button>
            <button
              onClick={exportAsSVG}
              className="px-3 py-2 text-xs text-slate-400 hover:text-white hover:bg-slate-800 transition-all rounded-r-lg"
              title="Export as SVG"
            >
              SVG
            </button>
          </div>

          {/* Minimap */}
          <div className="bg-slate-900/95 backdrop-blur-sm rounded-lg border border-slate-800 p-1">
            <svg
              ref={minimapRef}
              width={150}
              height={100}
              className="rounded"
              style={{ background: "rgba(15, 23, 42, 0.5)" }}
            />
          </div>
        </div>
      </div>

      {/* Instructions */}
      <div className="absolute bottom-4 left-4 z-10 bg-slate-900/90 backdrop-blur-sm rounded-lg px-3 py-2 border border-slate-800">
        <div className="text-[10px] text-slate-500 space-y-0.5">
          <div><span className="text-slate-400">Scroll</span> to zoom</div>
          <div><span className="text-slate-400">Drag background</span> to pan</div>
          <div><span className="text-slate-400">Drag node</span> to move</div>
          <div><span className="text-slate-400">Click</span> to select • <span className="text-slate-400">Double-click</span> for details</div>
        </div>
      </div>

      {/* SVG Container */}
      <div ref={containerRef} className="w-full h-full">
        <svg
          ref={svgRef}
          width={dimensions.width}
          height={dimensions.height}
          className="w-full h-full"
        />
      </div>

      {/* Tooltip */}
      {hoveredNode && !detailsPanelNode && (
        <div
          className="fixed z-50 pointer-events-none animate-in fade-in duration-150"
          style={{
            left: tooltipPos.x + 16,
            top: tooltipPos.y - 12,
          }}
        >
          <div className="bg-slate-900/95 backdrop-blur-sm border border-slate-700 rounded-xl shadow-2xl px-4 py-3 max-w-xs">
            <div className="flex items-center gap-2.5 mb-2">
              <span
                className="w-3 h-3 rounded-full"
                style={{
                  backgroundColor: NODE_CONFIG[hoveredNode.node_type]?.color,
                  boxShadow: `0 0 0 2px ${NODE_CONFIG[hoveredNode.node_type]?.glow}, 0 0 8px ${NODE_CONFIG[hoveredNode.node_type]?.glow}`,
                }}
              />
              <span className="text-sm font-semibold text-slate-100">
                {hoveredNode.label}
              </span>
            </div>

            <div className="text-xs text-slate-400 space-y-1">
              <div className="flex justify-between">
                <span className="text-slate-500">Type</span>
                <span className="capitalize font-medium">{hoveredNode.node_type}</span>
              </div>

              {hoveredNode.omop_concept_id && (
                <div className="flex justify-between">
                  <span className="text-slate-500">OMOP ID</span>
                  <span className="font-mono text-indigo-400">{hoveredNode.omop_concept_id}</span>
                </div>
              )}

              {typeof hoveredNode.properties?.assertion === "string" && (
                <div className="flex justify-between">
                  <span className="text-slate-500">Assertion</span>
                  <span className={
                    hoveredNode.properties.assertion === "absent"
                      ? "text-red-400 font-medium"
                      : hoveredNode.properties.assertion === "possible"
                        ? "text-amber-400 font-medium"
                        : "text-emerald-400 font-medium"
                  }>
                    {hoveredNode.properties.assertion}
                  </span>
                </div>
              )}

              {typeof hoveredNode.properties?.temporality === "string" && (
                <div className="flex justify-between">
                  <span className="text-slate-500">Temporality</span>
                  <span className="font-medium">{hoveredNode.properties.temporality}</span>
                </div>
              )}

              {Boolean(hoveredNode.properties?.is_negated) && (
                <div className="mt-2 pt-2 border-t border-slate-800">
                  <span className="inline-flex items-center gap-1.5 text-red-400 font-medium">
                    <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                    </svg>
                    Negated Finding
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Details Panel */}
      {detailsPanelNode && (
        <div className="absolute top-4 bottom-4 right-4 w-80 z-20 animate-in slide-in-from-right duration-300">
          <div className="h-full bg-slate-900/98 backdrop-blur-sm border border-slate-700 rounded-xl shadow-2xl flex flex-col overflow-hidden">
            {/* Header */}
            <div className="p-4 border-b border-slate-800">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <span
                    className="w-4 h-4 rounded-full"
                    style={{
                      backgroundColor: NODE_CONFIG[detailsPanelNode.node_type]?.color,
                      boxShadow: `0 0 0 2px #0f172a, 0 0 0 4px ${NODE_CONFIG[detailsPanelNode.node_type]?.glow}`,
                    }}
                  />
                  <div>
                    <h3 className="text-base font-semibold text-slate-100 leading-tight">
                      {detailsPanelNode.label}
                    </h3>
                    <span className="text-xs text-slate-500 capitalize">
                      {detailsPanelNode.node_type}
                    </span>
                  </div>
                </div>
                <button
                  onClick={() => setDetailsPanelNode(null)}
                  className="p-1 text-slate-500 hover:text-white hover:bg-slate-800 rounded transition-colors"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {/* Properties */}
              <div>
                <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                  Properties
                </h4>
                <div className="bg-slate-800/50 rounded-lg p-3 space-y-2 text-sm">
                  {detailsPanelNode.omop_concept_id && (
                    <div className="flex justify-between">
                      <span className="text-slate-400">OMOP Concept ID</span>
                      <span className="font-mono text-indigo-400">{detailsPanelNode.omop_concept_id}</span>
                    </div>
                  )}

                  {typeof detailsPanelNode.properties?.assertion === "string" && (
                    <div className="flex justify-between">
                      <span className="text-slate-400">Assertion</span>
                      <span className={
                        detailsPanelNode.properties.assertion === "absent"
                          ? "text-red-400 font-medium"
                          : detailsPanelNode.properties.assertion === "possible"
                            ? "text-amber-400 font-medium"
                            : "text-emerald-400 font-medium"
                      }>
                        {detailsPanelNode.properties.assertion}
                      </span>
                    </div>
                  )}

                  {typeof detailsPanelNode.properties?.temporality === "string" && (
                    <div className="flex justify-between">
                      <span className="text-slate-400">Temporality</span>
                      <span className="text-slate-200">{detailsPanelNode.properties.temporality}</span>
                    </div>
                  )}

                  {Boolean(detailsPanelNode.properties?.is_negated) && (
                    <div className="flex justify-between">
                      <span className="text-slate-400">Status</span>
                      <span className="text-red-400 font-medium">Negated</span>
                    </div>
                  )}

                  {typeof detailsPanelNode.properties?.value !== "undefined" && (
                    <div className="flex justify-between">
                      <span className="text-slate-400">Value</span>
                      <span className="text-slate-200">
                        {String(detailsPanelNode.properties.value)}
                        {detailsPanelNode.properties?.unit ? ` ${String(detailsPanelNode.properties.unit)}` : null}
                      </span>
                    </div>
                  )}

                  <div className="flex justify-between">
                    <span className="text-slate-400">Node ID</span>
                    <span className="font-mono text-xs text-slate-500 truncate max-w-[140px]">
                      {detailsPanelNode.id}
                    </span>
                  </div>
                </div>
              </div>

              {/* Connected Nodes */}
              <div>
                <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                  Connections ({connectedNodes.length})
                </h4>
                <div className="space-y-1.5">
                  {connectedNodes.map(({ edge, node }) => (
                    <button
                      key={edge.id}
                      onClick={() => node && setDetailsPanelNode(node as SimulationNode)}
                      className="w-full flex items-center gap-2 p-2 bg-slate-800/30 hover:bg-slate-800/60 rounded-lg transition-colors text-left"
                    >
                      <span
                        className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                        style={{ backgroundColor: NODE_CONFIG[node?.node_type || "observation"]?.color }}
                      />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm text-slate-200 truncate">{node?.label}</div>
                        <div className="text-[10px] text-slate-500">
                          {EDGE_LABELS[edge.edge_type] || edge.edge_type}
                        </div>
                      </div>
                      <svg className="w-4 h-4 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </button>
                  ))}
                  {connectedNodes.length === 0 && (
                    <div className="text-sm text-slate-500 text-center py-4">
                      No connections
                    </div>
                  )}
                </div>
              </div>

              {/* Provenance */}
              <div>
                <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                  Provenance
                </h4>
                {provenanceLoading ? (
                  <div className="text-sm text-slate-500 text-center py-4">
                    Loading provenance...
                  </div>
                ) : nodeProvenance && nodeProvenance.length > 0 ? (
                  <div className="space-y-1.5">
                    {nodeProvenance.map((record, idx) => (
                      <div
                        key={idx}
                        className="bg-slate-800/30 rounded-lg p-2 text-xs space-y-1"
                      >
                        <div className="flex justify-between">
                          <span className="text-slate-400">Method</span>
                          <span className="text-slate-200 capitalize">
                            {String(record.extraction_method ?? "unknown").replace(/_/g, " ")}
                          </span>
                        </div>
                        {record.confidence_score != null && (
                          <div className="flex justify-between">
                            <span className="text-slate-400">Confidence</span>
                            <span
                              className={`font-medium ${
                                Number(record.confidence_score) >= 0.8
                                  ? "text-emerald-400"
                                  : Number(record.confidence_score) >= 0.6
                                    ? "text-amber-400"
                                    : "text-red-400"
                              }`}
                            >
                              {Math.round(Number(record.confidence_score) * 100)}%
                            </span>
                          </div>
                        )}
                        {record.confidence_level != null && (
                          <div className="flex justify-between">
                            <span className="text-slate-400">Level</span>
                            <span className="text-slate-200 capitalize">
                              {String(record.confidence_level)}
                            </span>
                          </div>
                        )}
                        {record.extracted_text != null && (
                          <div className="mt-1 pt-1 border-t border-slate-800">
                            <span className="text-slate-400">Source text: </span>
                            <span className="text-slate-300 italic">
                              {String(record.extracted_text).length > 100
                                ? String(record.extracted_text).slice(0, 100) + "..."
                                : String(record.extracted_text)}
                            </span>
                          </div>
                        )}
                        {record.source_document_id != null && (
                          <div className="flex justify-between">
                            <span className="text-slate-400">Source Doc</span>
                            <span className="font-mono text-xs text-indigo-400 truncate max-w-[140px]">
                              {String(record.source_document_id)}
                            </span>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : nodeProvenance !== null ? (
                  <div className="text-sm text-slate-500 text-center py-4">
                    No provenance data
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Selected node bar (only when no details panel) */}
      {selectedNode && !detailsPanelNode && (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-10 animate-in slide-in-from-bottom duration-200">
          <div className="bg-slate-900/98 backdrop-blur-sm border border-slate-700 rounded-xl px-4 py-3 shadow-2xl">
            <div className="flex items-center gap-3">
              {(() => {
                const node = nodes.find((n) => n.id === selectedNode);
                if (!node) return null;
                return (
                  <>
                    <span
                      className="w-3 h-3 rounded-full"
                      style={{
                        backgroundColor: NODE_CONFIG[node.node_type]?.color,
                        boxShadow: `0 0 8px ${NODE_CONFIG[node.node_type]?.glow}`,
                      }}
                    />
                    <span className="text-sm font-semibold text-slate-100">
                      {node.label}
                    </span>
                    <span className="text-xs text-slate-500 capitalize">
                      {node.node_type}
                    </span>
                    <span className="text-xs text-slate-600">•</span>
                    <span className="text-xs text-slate-500">
                      {edges.filter((e) => e.source_node_id === selectedNode || e.target_node_id === selectedNode).length} connections
                    </span>
                    <button
                      onClick={() => setDetailsPanelNode(node as SimulationNode)}
                      className="ml-2 px-2 py-1 text-xs text-indigo-400 hover:text-indigo-300 hover:bg-indigo-950/50 rounded transition-colors"
                    >
                      View details →
                    </button>
                  </>
                );
              })()}
              <button
                onClick={() => setSelectedNode(null)}
                className="ml-2 p-1 text-slate-500 hover:text-slate-300 transition-colors"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
