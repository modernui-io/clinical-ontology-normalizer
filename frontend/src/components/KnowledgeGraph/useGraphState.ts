"use client";

import { useState, useCallback, useMemo, useEffect, useRef } from "react";
import * as d3 from "d3";
import type {
  SimulationNode,
  SimulationEdge,
  APIGraphNode,
  APIGraphEdge,
  LayoutMode,
  GraphDimensions,
  TooltipPosition,
} from "./types";
import { NODE_CONFIG } from "./GraphNode";
import { useNodeContextMenu } from "../graph/NodeContextMenu";

// Threshold for switching to canvas rendering
export const CANVAS_RENDER_THRESHOLD = 200;

export interface UseGraphStateProps {
  nodes: APIGraphNode[];
  edges: APIGraphEdge[];
  patientId: string;
}

export interface UseGraphStateReturn {
  // Refs
  svgRef: React.RefObject<SVGSVGElement | null>;
  minimapRef: React.RefObject<SVGSVGElement | null>;
  containerRef: React.RefObject<HTMLDivElement | null>;
  fullscreenRef: React.RefObject<HTMLDivElement | null>;
  simulationNodesRef: React.MutableRefObject<SimulationNode[]>;
  simulationEdgesRef: React.MutableRefObject<SimulationEdge[]>;

  // Dimensions
  dimensions: GraphDimensions;
  setDimensions: React.Dispatch<React.SetStateAction<GraphDimensions>>;

  // Selection state
  selectedNode: string | null;
  setSelectedNode: React.Dispatch<React.SetStateAction<string | null>>;
  hoveredNode: SimulationNode | null;
  setHoveredNode: React.Dispatch<React.SetStateAction<SimulationNode | null>>;
  tooltipPos: TooltipPosition;
  setTooltipPos: React.Dispatch<React.SetStateAction<TooltipPosition>>;
  detailsPanelNode: SimulationNode | null;
  setDetailsPanelNode: React.Dispatch<React.SetStateAction<SimulationNode | null>>;

  // Filters
  activeFilters: Set<string>;
  setActiveFilters: React.Dispatch<React.SetStateAction<Set<string>>>;
  toggleFilter: (nodeType: string) => void;
  searchQuery: string;
  setSearchQuery: React.Dispatch<React.SetStateAction<string>>;
  searchFilteredNodes: Set<string> | null;

  // Layout
  layoutMode: LayoutMode;
  setLayoutMode: React.Dispatch<React.SetStateAction<LayoutMode>>;
  showHulls: boolean;
  setShowHulls: React.Dispatch<React.SetStateAction<boolean>>;
  showLabels: boolean;
  setShowLabels: React.Dispatch<React.SetStateAction<boolean>>;

  // Transform state
  currentTransform: d3.ZoomTransform;
  setCurrentTransform: React.Dispatch<React.SetStateAction<d3.ZoomTransform>>;

  // Simulation state
  isSimulating: boolean;
  setIsSimulating: React.Dispatch<React.SetStateAction<boolean>>;

  // Fullscreen
  isFullscreen: boolean;
  setIsFullscreen: React.Dispatch<React.SetStateAction<boolean>>;
  toggleFullscreen: () => void;

  // Node visibility/pinning
  pinnedNodes: Set<string>;
  setPinnedNodes: React.Dispatch<React.SetStateAction<Set<string>>>;
  hiddenNodes: Set<string>;
  setHiddenNodes: React.Dispatch<React.SetStateAction<Set<string>>>;

  // Temporal filtering
  temporalFilterEnabled: boolean;
  setTemporalFilterEnabled: React.Dispatch<React.SetStateAction<boolean>>;
  dateRange: [Date | null, Date | null];
  setDateRange: React.Dispatch<React.SetStateAction<[Date | null, Date | null]>>;
  temporalityFilter: string | null;
  setTemporalityFilter: React.Dispatch<React.SetStateAction<string | null>>;
  eventDates: (string | null)[];

  // Render mode
  forceCanvasMode: boolean | null;
  setForceCanvasMode: React.Dispatch<React.SetStateAction<boolean | null>>;
  useCanvasRendering: boolean;

  // Provenance
  nodeProvenance: Record<string, unknown>[] | null;
  setNodeProvenance: React.Dispatch<React.SetStateAction<Record<string, unknown>[] | null>>;
  provenanceLoading: boolean;
  setProvenanceLoading: React.Dispatch<React.SetStateAction<boolean>>;

  // Context menu
  menuState: { isOpen: boolean; x: number; y: number; nodeId: string | null };
  openMenu: (x: number, y: number, nodeId: string) => void;
  closeMenu: () => void;

  // Node action handlers
  handleExpandNeighbors: (nodeId: string) => void;
  handleCollapseNeighbors: (nodeId: string) => void;
  handleHideNode: (nodeId: string) => void;
  handleShowNode: (nodeId: string) => void;
  handlePinNode: (nodeId: string) => void;
  handleUnpinNode: (nodeId: string) => void;
  handleCopyOmopId: (omopId: number) => void;
  handleFocusNode: (nodeId: string) => void;
  getNeighborCount: (nodeId: string) => number;
  getHiddenNeighborCount: (nodeId: string) => number;

  // Canvas handlers
  handleCanvasNodeClick: (node: SimulationNode, event: MouseEvent) => void;
  handleCanvasNodeHover: (node: SimulationNode | null, x: number, y: number) => void;
  handleCanvasNodeContextMenu: (node: SimulationNode, event: MouseEvent) => void;
  handleCanvasBackgroundClick: () => void;

  // Export functions
  exportAsPNG: () => void;
  exportAsSVG: () => void;
  resetView: () => void;

  // Computed values
  connectedNodes: Array<{ edge: APIGraphEdge; node: APIGraphNode | undefined }>;
  visibleNodes: APIGraphNode[];
}

export function useGraphState({ nodes, edges, patientId }: UseGraphStateProps): UseGraphStateReturn {
  // Refs
  const svgRef = useRef<SVGSVGElement | null>(null);
  const minimapRef = useRef<SVGSVGElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const fullscreenRef = useRef<HTMLDivElement | null>(null);
  const simulationNodesRef = useRef<SimulationNode[]>([]);
  const simulationEdgesRef = useRef<SimulationEdge[]>([]);

  // Dimensions
  const [dimensions, setDimensions] = useState<GraphDimensions>({ width: 800, height: 600 });

  // Selection state
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [hoveredNode, setHoveredNode] = useState<SimulationNode | null>(null);
  const [tooltipPos, setTooltipPos] = useState<TooltipPosition>({ x: 0, y: 0 });
  const [detailsPanelNode, setDetailsPanelNode] = useState<SimulationNode | null>(null);

  // Filters
  const [activeFilters, setActiveFilters] = useState<Set<string>>(
    new Set(Object.keys(NODE_CONFIG))
  );
  const [searchQuery, setSearchQuery] = useState("");

  // Layout
  const [layoutMode, setLayoutMode] = useState<LayoutMode>("radial");
  const [showHulls, setShowHulls] = useState(true);
  const [showLabels, setShowLabels] = useState(true);

  // Transform
  const [currentTransform, setCurrentTransform] = useState<d3.ZoomTransform>(d3.zoomIdentity);

  // Simulation
  const [isSimulating, setIsSimulating] = useState(true);

  // Fullscreen
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Node visibility/pinning
  const [pinnedNodes, setPinnedNodes] = useState<Set<string>>(new Set());
  const [hiddenNodes, setHiddenNodes] = useState<Set<string>>(new Set());
  const [, setExpandedNodes] = useState<Set<string>>(new Set());

  // Temporal filtering
  const [temporalFilterEnabled, setTemporalFilterEnabled] = useState(false);
  const [dateRange, setDateRange] = useState<[Date | null, Date | null]>([null, null]);
  const [temporalityFilter, setTemporalityFilter] = useState<string | null>(null);

  // Render mode
  const [forceCanvasMode, setForceCanvasMode] = useState<boolean | null>(null);

  // Provenance
  const [nodeProvenance, setNodeProvenance] = useState<Record<string, unknown>[] | null>(null);
  const [provenanceLoading, setProvenanceLoading] = useState(false);

  // Context menu
  const { menuState, openMenu, closeMenu } = useNodeContextMenu();

  // Computed: use canvas rendering for large graphs
  const useCanvasRendering = useMemo(() => {
    if (forceCanvasMode !== null) return forceCanvasMode;
    return nodes.length > CANVAS_RENDER_THRESHOLD;
  }, [forceCanvasMode, nodes.length]);

  // Computed: event dates from edges
  const eventDates = useMemo(() => {
    return edges.map((e) => e.event_date);
  }, [edges]);

  // Computed: search filtered nodes
  const searchFilteredNodes = useMemo(() => {
    if (!searchQuery.trim()) return null;
    const query = searchQuery.toLowerCase();
    return new Set(
      nodes.filter(n => n.label.toLowerCase().includes(query)).map(n => n.id)
    );
  }, [nodes, searchQuery]);

  // Computed: connected nodes for details panel
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

  // Computed: visible nodes for keyboard navigation
  const visibleNodes = useMemo(() => {
    return nodes.filter((n) => activeFilters.has(n.node_type) && !hiddenNodes.has(n.id));
  }, [nodes, activeFilters, hiddenNodes]);

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

  // Context menu handlers
  const handleExpandNeighbors = useCallback((nodeId: string) => {
    setExpandedNodes((prev) => new Set([...prev, nodeId]));
    closeMenu();
  }, [closeMenu]);

  const handleCollapseNeighbors = useCallback((nodeId: string) => {
    setExpandedNodes((prev) => {
      const next = new Set(prev);
      next.delete(nodeId);
      return next;
    });
    closeMenu();
  }, [closeMenu]);

  const handleHideNode = useCallback((nodeId: string) => {
    setHiddenNodes((prev) => new Set([...prev, nodeId]));
    closeMenu();
  }, [closeMenu]);

  const handleShowNode = useCallback((nodeId: string) => {
    setHiddenNodes((prev) => {
      const next = new Set(prev);
      next.delete(nodeId);
      return next;
    });
    closeMenu();
  }, [closeMenu]);

  const handlePinNode = useCallback((nodeId: string) => {
    setPinnedNodes((prev) => new Set([...prev, nodeId]));
    closeMenu();
  }, [closeMenu]);

  const handleUnpinNode = useCallback((nodeId: string) => {
    setPinnedNodes((prev) => {
      const next = new Set(prev);
      next.delete(nodeId);
      return next;
    });
    closeMenu();
  }, [closeMenu]);

  const handleCopyOmopId = useCallback((omopId: number) => {
    navigator.clipboard.writeText(omopId.toString());
    closeMenu();
  }, [closeMenu]);

  const handleFocusNode = useCallback((nodeId: string) => {
    const node = nodes.find((n) => n.id === nodeId);
    if (node && svgRef.current) {
      const svg = d3.select(svgRef.current);
      const zoom = (svgRef.current as SVGSVGElement & { __zoom?: d3.ZoomBehavior<SVGSVGElement, unknown> }).__zoom;
      if (zoom) {
        const { width, height } = dimensions;
        svg.transition()
          .duration(500)
          .call(
            zoom.transform,
            d3.zoomIdentity
              .translate(width / 2, height / 2)
              .scale(2)
              .translate(-((node as SimulationNode).x ?? 0), -((node as SimulationNode).y ?? 0))
          );
      }
    }
    setSelectedNode(nodeId);
    closeMenu();
  }, [nodes, dimensions, closeMenu]);

  // Get neighbor count
  const getNeighborCount = useCallback((nodeId: string) => {
    return edges.filter(
      (e) => e.source_node_id === nodeId || e.target_node_id === nodeId
    ).length;
  }, [edges]);

  const getHiddenNeighborCount = useCallback((nodeId: string) => {
    return edges.filter((e) => {
      const neighborId = e.source_node_id === nodeId ? e.target_node_id : e.source_node_id;
      return (e.source_node_id === nodeId || e.target_node_id === nodeId) && hiddenNodes.has(neighborId);
    }).length;
  }, [edges, hiddenNodes]);

  // Canvas renderer handlers
  const handleCanvasNodeClick = useCallback((node: SimulationNode, event: MouseEvent) => {
    setSelectedNode(node.id);
    if (event.detail === 2) {
      setDetailsPanelNode(node);
    }
  }, []);

  const handleCanvasNodeHover = useCallback((node: SimulationNode | null, x: number, y: number) => {
    setHoveredNode(node);
    setTooltipPos({ x, y });
  }, []);

  const handleCanvasNodeContextMenu = useCallback((node: SimulationNode, event: MouseEvent) => {
    openMenu(event.clientX, event.clientY, node.id);
  }, [openMenu]);

  const handleCanvasBackgroundClick = useCallback(() => {
    setSelectedNode(null);
    setHoveredNode(null);
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

  // Toggle fullscreen
  const toggleFullscreen = useCallback(() => {
    if (!fullscreenRef.current) return;

    if (!document.fullscreenElement) {
      fullscreenRef.current.requestFullscreen?.().then(() => {
        setIsFullscreen(true);
      }).catch(() => {
        // Fullscreen not supported
      });
    } else {
      document.exitFullscreen?.().then(() => {
        setIsFullscreen(false);
      });
    }
  }, []);

  // Reset view
  const resetView = useCallback(() => {
    if (svgRef.current) {
      const svg = d3.select(svgRef.current);
      const zoom = (svgRef.current as SVGSVGElement & { __zoom?: d3.ZoomBehavior<SVGSVGElement, unknown> }).__zoom;
      if (zoom) {
        const { width, height } = dimensions;
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
      }
    }
  }, [dimensions]);

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

  // Fullscreen change listener
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", handleFullscreenChange);
  }, []);

  // Fetch provenance when details panel node changes
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

  return {
    // Refs
    svgRef,
    minimapRef,
    containerRef,
    fullscreenRef,
    simulationNodesRef,
    simulationEdgesRef,

    // Dimensions
    dimensions,
    setDimensions,

    // Selection state
    selectedNode,
    setSelectedNode,
    hoveredNode,
    setHoveredNode,
    tooltipPos,
    setTooltipPos,
    detailsPanelNode,
    setDetailsPanelNode,

    // Filters
    activeFilters,
    setActiveFilters,
    toggleFilter,
    searchQuery,
    setSearchQuery,
    searchFilteredNodes,

    // Layout
    layoutMode,
    setLayoutMode,
    showHulls,
    setShowHulls,
    showLabels,
    setShowLabels,

    // Transform
    currentTransform,
    setCurrentTransform,

    // Simulation
    isSimulating,
    setIsSimulating,

    // Fullscreen
    isFullscreen,
    setIsFullscreen,
    toggleFullscreen,

    // Node visibility/pinning
    pinnedNodes,
    setPinnedNodes,
    hiddenNodes,
    setHiddenNodes,

    // Temporal filtering
    temporalFilterEnabled,
    setTemporalFilterEnabled,
    dateRange,
    setDateRange,
    temporalityFilter,
    setTemporalityFilter,
    eventDates,

    // Render mode
    forceCanvasMode,
    setForceCanvasMode,
    useCanvasRendering,

    // Provenance
    nodeProvenance,
    setNodeProvenance,
    provenanceLoading,
    setProvenanceLoading,

    // Context menu
    menuState,
    openMenu,
    closeMenu,

    // Node action handlers
    handleExpandNeighbors,
    handleCollapseNeighbors,
    handleHideNode,
    handleShowNode,
    handlePinNode,
    handleUnpinNode,
    handleCopyOmopId,
    handleFocusNode,
    getNeighborCount,
    getHiddenNeighborCount,

    // Canvas handlers
    handleCanvasNodeClick,
    handleCanvasNodeHover,
    handleCanvasNodeContextMenu,
    handleCanvasBackgroundClick,

    // Export functions
    exportAsPNG,
    exportAsSVG,
    resetView,

    // Computed values
    connectedNodes,
    visibleNodes,
  };
}
