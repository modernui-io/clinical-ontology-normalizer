"use client";

import { useEffect, useCallback } from "react";
import * as d3 from "d3";
import type {
  SimulationNode,
  SimulationEdge,
  APIGraphNode,
  APIGraphEdge,
  LayoutMode,
  GraphDimensions,
} from "./types";
import { NODE_CONFIG } from "./GraphNode";
import { getHullPath, getTemporalityColor } from "./GraphEdge";

export interface GraphCanvasProps {
  nodes: APIGraphNode[];
  edges: APIGraphEdge[];
  dimensions: GraphDimensions;
  activeFilters: Set<string>;
  hiddenNodes: Set<string>;
  pinnedNodes: Set<string>;
  layoutMode: LayoutMode;
  showHulls: boolean;
  showLabels: boolean;
  searchFilteredNodes: Set<string> | null;
  selectedNode: string | null;
  temporalFilterEnabled: boolean;
  dateRange: [Date | null, Date | null];
  temporalityFilter: string | null;
  useCanvasRendering: boolean;
  currentTransform: d3.ZoomTransform;
  svgRef: React.RefObject<SVGSVGElement | null>;
  simulationNodesRef: React.MutableRefObject<SimulationNode[]>;
  simulationEdgesRef: React.MutableRefObject<SimulationEdge[]>;
  setCurrentTransform: (transform: d3.ZoomTransform) => void;
  setIsSimulating: (isSimulating: boolean) => void;
  setHoveredNode: (node: SimulationNode | null) => void;
  setTooltipPos: (pos: { x: number; y: number }) => void;
  setSelectedNode: (nodeId: string | null) => void;
  setDetailsPanelNode: (node: SimulationNode | null) => void;
  openMenu: (x: number, y: number, nodeId: string) => void;
}

export function useGraphCanvas({
  nodes,
  edges,
  dimensions,
  activeFilters,
  hiddenNodes,
  pinnedNodes,
  layoutMode,
  showHulls,
  showLabels,
  searchFilteredNodes,
  selectedNode,
  temporalFilterEnabled,
  dateRange,
  temporalityFilter,
  useCanvasRendering,
  currentTransform,
  svgRef,
  simulationNodesRef,
  simulationEdgesRef,
  setCurrentTransform,
  setIsSimulating,
  setHoveredNode,
  setTooltipPos,
  setSelectedNode,
  setDetailsPanelNode,
  openMenu,
}: GraphCanvasProps) {
  // D3 visualization and simulation effect
  useEffect(() => {
    // Always need nodes to run simulation
    if (!nodes.length) return;

    // For SVG mode, we need the SVG ref; for canvas mode, we just run simulation
    const svg = svgRef.current ? d3.select(svgRef.current) : null;
    if (svg) {
      svg.selectAll("*").remove();
    }

    const { width, height } = dimensions;
    const centerX = width / 2;
    const centerY = height / 2;

    // Filter nodes and edges based on active filters and hidden nodes
    const filteredNodes = nodes.filter((n) =>
      activeFilters.has(n.node_type) && !hiddenNodes.has(n.id)
    );
    const filteredNodeIds = new Set(filteredNodes.map((n) => n.id));
    const filteredEdges = edges.filter((e) => {
      // First check node connectivity
      if (!filteredNodeIds.has(e.source_node_id) || !filteredNodeIds.has(e.target_node_id)) {
        return false;
      }

      // Apply temporal filtering if enabled
      if (temporalFilterEnabled) {
        // Temporality filter (current/past/future)
        if (temporalityFilter && e.temporality !== temporalityFilter) {
          return false;
        }

        // Date range filter
        if (dateRange[0] || dateRange[1]) {
          if (!e.event_date) return false;
          const eventDate = new Date(e.event_date);
          if (dateRange[0] && eventDate < dateRange[0]) return false;
          if (dateRange[1] && eventDate > dateRange[1]) return false;
        }
      }

      return true;
    });

    // Create deep copies for D3 mutation with initial positions for radial layout
    const nodeData: SimulationNode[] = filteredNodes.map((n) => {
      const config = NODE_CONFIG[n.node_type] || NODE_CONFIG.observation;
      const ringRadius = config.ringOrder * 120;
      const nodesOfType = filteredNodes.filter(fn => fn.node_type === n.node_type);
      const indexInType = nodesOfType.indexOf(n);
      const angleSpread = Math.PI * 2 / Math.max(nodesOfType.length, 1);
      const angle = indexInType * angleSpread + (config.ringOrder * 0.5);

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

    // For canvas mode, we only need the simulation - skip all SVG setup
    if (useCanvasRendering) {
      const simulation = d3
        .forceSimulation<SimulationNode>(nodeData)
        .force("link", d3.forceLink<SimulationNode, SimulationEdge>(edgeData)
          .id((d) => d.id)
          .distance(100)
          .strength(0.5)
        )
        .force("charge", d3.forceManyBody().strength(-300).theta(0.9))
        .force("center", d3.forceCenter(centerX, centerY))
        .force("collision", d3.forceCollide<SimulationNode>().radius((d) => {
          const config = NODE_CONFIG[d.node_type];
          return (config?.radius ?? 16) + 10;
        }))
        .alphaDecay(0.02)
        .velocityDecay(0.4);

      if (layoutMode === "radial") {
        simulation.force("radial", d3.forceRadial<SimulationNode>(
          (d) => d.initialRadius ?? 100,
          centerX,
          centerY
        ).strength(0.8));
      }

      simulation.on("tick", () => {
        simulationNodesRef.current = [...nodeData];
        simulationEdgesRef.current = [...edgeData];
      });

      simulation.on("end", () => {
        setIsSimulating(false);
      });

      nodeData.forEach(d => {
        if (pinnedNodes.has(d.id)) {
          d.fx = d.x;
          d.fy = d.y;
        }
      });

      return () => {
        simulation.stop();
      };
    }

    // SVG mode - full rendering setup
    if (!svg) return;

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

    // Ripple animation filter
    const rippleFilter = defs
      .append("filter")
      .attr("id", "ripple")
      .attr("x", "-100%")
      .attr("y", "-100%")
      .attr("width", "300%")
      .attr("height", "300%");
    rippleFilter
      .append("feGaussianBlur")
      .attr("stdDeviation", 2)
      .attr("result", "blur");
    rippleFilter
      .append("feColorMatrix")
      .attr("type", "matrix")
      .attr("values", "0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 0.3 0");
    const rippleMerge = rippleFilter.append("feMerge");
    rippleMerge.append("feMergeNode").attr("in", "blur");
    rippleMerge.append("feMergeNode").attr("in", "SourceGraphic");

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

    // Node gradients for modern look
    Object.entries(NODE_CONFIG).forEach(([type, config]) => {
      const gradient = defs
        .append("radialGradient")
        .attr("id", `gradient-${type}`)
        .attr("cx", "30%")
        .attr("cy", "30%")
        .attr("r", "70%");

      gradient
        .append("stop")
        .attr("offset", "0%")
        .attr("stop-color", config.color)
        .attr("stop-opacity", 1);

      gradient
        .append("stop")
        .attr("offset", "100%")
        .attr("stop-color", config.colorEnd)
        .attr("stop-opacity", 1);
    });

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

    // Create zoom behavior with extended range and smooth transitions
    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.05, 10])
      .wheelDelta((event) => {
        return -event.deltaY * (event.deltaMode === 1 ? 0.05 : event.deltaMode ? 1 : 0.002);
      })
      .on("zoom", (event) => {
        container.attr("transform", event.transform);
        setCurrentTransform(event.transform);
      });

    // Enable touch gestures for mobile
    svg
      .call(zoom)
      .on("touchstart.zoom", null)
      .call(zoom.touchable(true as unknown as () => boolean));

    // Main container with GPU acceleration
    const container = svg.append("g")
      .attr("class", "graph-container")
      .style("will-change", "transform");

    // Create force simulation with optimized parameters for performance
    const nodeCount = nodeData.length;
    const isLargeGraph = nodeCount > 200;

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
      .force("charge", (() => {
        const charge = d3.forceManyBody()
          .strength(layoutMode === "radial" ? -200 : -400)
          .theta(isLargeGraph ? 0.9 : 0.81);
        if (isLargeGraph) {
          charge.distanceMax(300);
        }
        return charge;
      })())
      .force("collision", d3.forceCollide<SimulationNode>().radius((d) =>
        (NODE_CONFIG[d.node_type]?.radius || 16) + 10
      ))
      .alpha(1)
      .alphaDecay(isLargeGraph ? 0.05 : 0.0228)
      .alphaMin(0.001)
      .velocityDecay(isLargeGraph ? 0.4 : 0.3);

    if (layoutMode === "radial") {
      simulation
        .force("radial", d3.forceRadial<SimulationNode>(
          (d) => d.node_type === "patient" ? 0 : (NODE_CONFIG[d.node_type]?.ringOrder || 1) * 100,
          centerX,
          centerY
        ).strength(0.8))
        .force("center", null);

      const patient = nodeData.find(n => n.node_type === "patient");
      if (patient) {
        patient.fx = centerX;
        patient.fy = centerY;
      }
    } else {
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
        if (temporalFilterEnabled && d.temporality) {
          return getTemporalityColor(d.temporality);
        }
        const targetNode = nodeData.find(n => n.id === d.target_node_id);
        return NODE_CONFIG[targetNode?.node_type || "observation"]?.color || "#475569";
      })
      .attr("stroke-width", (d) => {
        if (temporalFilterEnabled && d.temporal_confidence !== null) {
          return 1.5 + d.temporal_confidence * 1.5;
        }
        return 1.5;
      })
      .attr("stroke-opacity", (d) => {
        if (temporalFilterEnabled && d.temporal_confidence !== null) {
          return 0.3 + d.temporal_confidence * 0.5;
        }
        return 0.4;
      })
      .attr("marker-end", (d) => {
        const targetNode = nodeData.find(n => n.id === d.target_node_id);
        return `url(#arrow-${targetNode?.node_type || "default"})`;
      })
      .style("transition", "stroke-opacity 0.3s ease");

    // Edge labels (hidden by default)
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

    // Track drag state for click vs drag differentiation
    const dragState = new Map<string, { startX: number; startY: number; isDragging: boolean }>();
    const DRAG_THRESHOLD = 5;

    const node = nodeGroup
      .selectAll<SVGGElement, SimulationNode>("g")
      .data(nodeData)
      .join("g")
      .attr("class", "node")
      .style("cursor", "pointer")
      .style("opacity", 0)
      .attr("pointer-events", "all")
      .call(
        d3
          .drag<SVGGElement, SimulationNode>()
          .on("start", (event, d) => {
            dragState.set(d.id, {
              startX: event.x,
              startY: event.y,
              isDragging: false
            });
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on("drag", (event, d) => {
            const state = dragState.get(d.id);
            if (state) {
              const dx = event.x - state.startX;
              const dy = event.y - state.startY;
              const distance = Math.sqrt(dx * dx + dy * dy);
              if (distance > DRAG_THRESHOLD) {
                state.isDragging = true;
              }
            }
            d.fx = event.x;
            d.fy = event.y;
          })
          .on("end", (event, d) => {
            if (!event.active) simulation.alphaTarget(0);
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

    // Invisible hit area for better click detection
    node
      .append("circle")
      .attr("class", "hit-area")
      .attr("r", (d) => (NODE_CONFIG[d.node_type]?.radius || 16) * 2)
      .attr("fill", "transparent")
      .attr("stroke", "none")
      .style("cursor", "pointer");

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

    // Node main circle with gradient fill
    node
      .append("circle")
      .attr("class", "node-circle")
      .attr("r", (d) => NODE_CONFIG[d.node_type]?.radius || 16)
      .attr("fill", (d) => {
        if (d.properties?.is_negated) {
          return d3.color(NODE_CONFIG[d.node_type]?.color || "#94a3b8")?.darker(0.5)?.toString() || "#94a3b8";
        }
        return `url(#gradient-${d.node_type})`;
      })
      .attr("stroke", (d) => NODE_CONFIG[d.node_type]?.glow || "#64748b")
      .attr("stroke-width", 2)
      .attr("stroke-opacity", 0.8)
      .attr("filter", "url(#glow)")
      .style("transition", "all 0.2s cubic-bezier(0.4, 0, 0.2, 1)");

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
          .text("\u2715");
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
        return d.label.length > maxLen ? d.label.slice(0, maxLen) + "\u2026" : d.label;
      })
      .style("pointer-events", "none")
      .style("text-shadow", "0 2px 4px rgba(0,0,0,0.9)")
      .style("opacity", showLabels ? 1 : 0);

    // Hidden neighbor count badge
    const nodesWithHiddenNeighbors = nodeData.filter((d) => {
      const hiddenCount = edges.filter((e) => {
        const neighborId = e.source_node_id === d.id ? e.target_node_id : e.source_node_id;
        return (e.source_node_id === d.id || e.target_node_id === d.id) && hiddenNodes.has(neighborId);
      }).length;
      return hiddenCount > 0;
    });

    node
      .filter((d) => nodesWithHiddenNeighbors.some((n) => n.id === d.id))
      .append("g")
      .attr("class", "hidden-neighbor-badge")
      .each(function(d) {
        const hiddenCount = edges.filter((e) => {
          const neighborId = e.source_node_id === d.id ? e.target_node_id : e.source_node_id;
          return (e.source_node_id === d.id || e.target_node_id === d.id) && hiddenNodes.has(neighborId);
        }).length;
        const r = NODE_CONFIG[d.node_type]?.radius || 16;

        d3.select(this)
          .append("circle")
          .attr("cx", r * 0.85)
          .attr("cy", -r * 0.85)
          .attr("r", 9)
          .attr("fill", "#4f46e5")
          .attr("stroke", "#020617")
          .attr("stroke-width", 2);

        d3.select(this)
          .append("text")
          .attr("x", r * 0.85)
          .attr("y", -r * 0.85)
          .attr("text-anchor", "middle")
          .attr("dy", 3.5)
          .attr("fill", "white")
          .attr("font-size", "9px")
          .attr("font-weight", "bold")
          .text(`+${hiddenCount}`);
      });

    // Pin indicator badge
    node
      .filter((d) => pinnedNodes.has(d.id))
      .append("g")
      .attr("class", "pin-indicator")
      .each(function(d) {
        const r = NODE_CONFIG[d.node_type]?.radius || 16;

        d3.select(this)
          .append("circle")
          .attr("cx", -r * 0.85)
          .attr("cy", -r * 0.85)
          .attr("r", 7)
          .attr("fill", "#f59e0b")
          .attr("stroke", "#020617")
          .attr("stroke-width", 2);

        d3.select(this)
          .append("text")
          .attr("x", -r * 0.85)
          .attr("y", -r * 0.85)
          .attr("text-anchor", "middle")
          .attr("dy", 3)
          .attr("fill", "#020617")
          .attr("font-size", "8px")
          .attr("font-weight", "bold")
          .text("P");
      });

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

    // Node interactions with enhanced visual feedback
    node
      .on("mouseenter", function (event, d) {
        setHoveredNode(d);
        setTooltipPos({ x: event.pageX, y: event.pageY });

        d3.select(this)
          .transition()
          .duration(150)
          .ease(d3.easeBackOut.overshoot(1.5))
          .attr("transform", `translate(${d.x || 0},${d.y || 0}) scale(1.1)`);

        d3.select(this)
          .select(".node-circle")
          .attr("filter", "url(#glow-selected)")
          .attr("stroke-width", 3);

        d3.select(this).style("cursor", "pointer");

        linkLabels.style("opacity", (l) => {
          const source = typeof l.source === "object" ? l.source.id : l.source;
          const target = typeof l.target === "object" ? l.target.id : l.target;
          return source === d.id || target === d.id ? 1 : 0;
        });

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

        d3.select(this)
          .transition()
          .duration(150)
          .ease(d3.easeCubicOut)
          .attr("transform", `translate(${d.x || 0},${d.y || 0}) scale(1)`);

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

        const state = dragState.get(d.id);
        if (state?.isDragging) {
          dragState.delete(d.id);
          return;
        }
        dragState.delete(d.id);

        const nodeRadius = NODE_CONFIG[d.node_type]?.radius || 16;
        const ripple = d3.select(this)
          .append("circle")
          .attr("class", "ripple-effect")
          .attr("r", nodeRadius)
          .attr("fill", "none")
          .attr("stroke", NODE_CONFIG[d.node_type]?.color || "#94a3b8")
          .attr("stroke-width", 3)
          .attr("opacity", 0.8)
          .attr("filter", "url(#ripple)");

        ripple.transition()
          .duration(400)
          .ease(d3.easeCubicOut)
          .attr("r", nodeRadius * 2.5)
          .attr("stroke-width", 0.5)
          .attr("opacity", 0)
          .remove();

        const newSelected = selectedNode === d.id ? null : d.id;
        setSelectedNode(newSelected);
        setDetailsPanelNode(newSelected ? d : null);

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
      })
      .on("contextmenu", (event, d) => {
        event.preventDefault();
        event.stopPropagation();
        openMenu(event.pageX, event.pageY, d.id);
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

      return `M${sx},${sy}Q${(sx + tx) / 2 + dy * 0.1},${(sy + ty) / 2 - dx * 0.1},${tx},${ty}`;
    };

    // Set simulating state
    setIsSimulating(true);

    // Simulation end handler
    simulation.on("end", () => {
      setIsSimulating(false);
    });

    // Level-of-detail state tracking
    let lastLodScale = 1;

    // Simulation tick
    simulation.on("tick", () => {
      simulationNodesRef.current = nodeData;
      simulationEdgesRef.current = edgeData;

      hulls.attr("d", ([, nodes]) => {
        const points: [number, number][] = nodes.map(n => [n.x || 0, n.y || 0]);
        const padding = currentTransform.k < 0.5 ? 50 : 35;
        return getHullPath(points, padding);
      });

      link.attr("d", linkPath);

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

      node.attr("transform", (d) => `translate(${d.x || 0},${d.y || 0})`);

      const currentScale = currentTransform.k;
      if (Math.abs(currentScale - lastLodScale) > 0.1) {
        lastLodScale = currentScale;

        const shouldShowLabels = currentScale >= 0.5 && showLabels;
        node.select(".node-label")
          .style("opacity", shouldShowLabels ? 1 : 0);

        if (currentScale < 0.3) {
          node.select("path").style("opacity", 0);
          node.select(".node-circle").attr("stroke-width", 1);
        } else {
          node.select("path").style("opacity", 0.9);
          node.select(".node-circle").attr("stroke-width", 2);
        }

        linkLabels.style("display", currentScale < 0.6 ? "none" : "block");
        hulls.attr("fill-opacity", currentScale < 0.5 && showHulls ? 0.04 : (showHulls ? 0.08 : 0));
      }
    });

    // Initial zoom to fit with smooth transition
    const initialScale = 0.85;
    svg.transition()
      .duration(500)
      .ease(d3.easeCubicOut)
      .call(
        zoom.transform,
        d3.zoomIdentity
          .translate(width * (1 - initialScale) / 2, height * (1 - initialScale) / 2)
          .scale(initialScale)
      );

    // Store zoom for external access
    (svgRef.current as SVGSVGElement & { __zoom?: d3.ZoomBehavior<SVGSVGElement, unknown> }).__zoom = zoom;

    return () => {
      simulation.stop();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes, edges, dimensions, activeFilters, layoutMode, showHulls, showLabels, searchFilteredNodes, selectedNode, hiddenNodes, pinnedNodes, temporalFilterEnabled, dateRange, temporalityFilter, useCanvasRendering]);
}

// Minimap hook
export function useGraphMinimap({
  nodes,
  edges,
  dimensions,
  activeFilters,
  hiddenNodes,
  currentTransform,
  minimapRef,
  svgRef,
}: {
  nodes: APIGraphNode[];
  edges: APIGraphEdge[];
  dimensions: GraphDimensions;
  activeFilters: Set<string>;
  hiddenNodes: Set<string>;
  currentTransform: d3.ZoomTransform;
  minimapRef: React.RefObject<SVGSVGElement | null>;
  svgRef: React.RefObject<SVGSVGElement | null>;
}) {
  useEffect(() => {
    if (!minimapRef.current || !nodes.length) return;

    const svg = d3.select(minimapRef.current);
    svg.selectAll("*").remove();

    const minimapWidth = 150;
    const minimapHeight = 100;
    const scale = Math.min(minimapWidth / dimensions.width, minimapHeight / dimensions.height) * 0.8;
    const offsetX = (minimapWidth - dimensions.width * scale) / 2;
    const offsetY = (minimapHeight - dimensions.height * scale) / 2;

    svg.append("rect")
      .attr("width", minimapWidth)
      .attr("height", minimapHeight)
      .attr("fill", "transparent")
      .style("cursor", "pointer");

    const filteredNodes = nodes.filter(n => activeFilters.has(n.node_type) && !hiddenNodes.has(n.id));
    const centerX = dimensions.width / 2;
    const centerY = dimensions.height / 2;

    svg.selectAll("circle.node-dot")
      .data(filteredNodes)
      .join("circle")
      .attr("class", "node-dot")
      .attr("cx", (d) => {
        const simNode = d as SimulationNode;
        const x = simNode.x ?? centerX;
        return x * scale + offsetX;
      })
      .attr("cy", (d) => {
        const simNode = d as SimulationNode;
        const y = simNode.y ?? centerY;
        return y * scale + offsetY;
      })
      .attr("r", 2)
      .attr("fill", d => NODE_CONFIG[d.node_type]?.color || "#94a3b8")
      .attr("opacity", 0.8)
      .style("pointer-events", "none");

    const viewportWidth = dimensions.width / currentTransform.k;
    const viewportHeight = dimensions.height / currentTransform.k;
    const viewportX = -currentTransform.x / currentTransform.k;
    const viewportY = -currentTransform.y / currentTransform.k;

    const viewportRect = svg.append("rect")
      .attr("class", "viewport-rect")
      .attr("x", viewportX * scale + offsetX)
      .attr("y", viewportY * scale + offsetY)
      .attr("width", Math.max(viewportWidth * scale, 10))
      .attr("height", Math.max(viewportHeight * scale, 10))
      .attr("fill", "rgba(96, 165, 250, 0.1)")
      .attr("stroke", "#60a5fa")
      .attr("stroke-width", 1.5)
      .attr("rx", 2)
      .style("cursor", "move");

    const handleMinimapClick = (event: MouseEvent) => {
      if (!svgRef.current) return;

      const [x, y] = d3.pointer(event, svg.node());
      const graphX = (x - offsetX) / scale;
      const graphY = (y - offsetY) / scale;

      const mainSvg = d3.select(svgRef.current);
      const zoom = (svgRef.current as SVGSVGElement & { __zoom?: d3.ZoomBehavior<SVGSVGElement, unknown> }).__zoom;
      if (zoom) {
        const newTransform = d3.zoomIdentity
          .translate(
            dimensions.width / 2 - graphX * currentTransform.k,
            dimensions.height / 2 - graphY * currentTransform.k
          )
          .scale(currentTransform.k);

        mainSvg.transition()
          .duration(300)
          .ease(d3.easeCubicOut)
          .call(zoom.transform, newTransform);
      }
    };

    svg.on("click", handleMinimapClick);

    const drag = d3.drag<SVGRectElement, unknown>()
      .on("drag", (event) => {
        if (!svgRef.current) return;

        const dx = event.dx / scale;
        const dy = event.dy / scale;

        const mainSvg = d3.select(svgRef.current);
        const zoom = (svgRef.current as SVGSVGElement & { __zoom?: d3.ZoomBehavior<SVGSVGElement, unknown> }).__zoom;
        if (zoom) {
          const newTransform = d3.zoomIdentity
            .translate(
              currentTransform.x - dx * currentTransform.k,
              currentTransform.y - dy * currentTransform.k
            )
            .scale(currentTransform.k);

          mainSvg.call(zoom.transform, newTransform);
        }
      });

    viewportRect.call(drag);

  }, [nodes, dimensions, activeFilters, currentTransform, hiddenNodes, minimapRef, svgRef]);
}
