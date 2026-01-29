"use client";

import { useEffect, useCallback } from "react";
import * as d3 from "d3";
import type { KnowledgeGraphProps, SimulationNode } from "./types";
import { NODE_CONFIG, getNodeConfigForCanvas } from "./GraphNode";
import { EDGE_LABELS } from "./GraphEdge";
import { useGraphState } from "./useGraphState";
import { useGraphCanvas, useGraphMinimap } from "./GraphCanvas";
import { GraphSearchCombobox } from "../graph/GraphSearchCombobox";
import { TemporalSlider } from "../graph/TemporalSlider";
import { CanvasRenderer } from "../graph/CanvasRenderer";

export default function KnowledgeGraph({ nodes, edges, patientId }: KnowledgeGraphProps) {
  const state = useGraphState({ nodes, edges, patientId });

  const {
    // Refs
    svgRef,
    minimapRef,
    containerRef,
    fullscreenRef,
    simulationNodesRef,
    simulationEdgesRef,

    // Dimensions
    dimensions,

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
    toggleFullscreen,

    // Node visibility/pinning
    pinnedNodes,
    hiddenNodes,

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
    provenanceLoading,

    // Context menu
    menuState,
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
    openMenu,
  } = state;

  // Use D3 canvas rendering hook
  useGraphCanvas({
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
  });

  // Use minimap hook
  useGraphMinimap({
    nodes,
    edges,
    dimensions,
    activeFilters,
    hiddenNodes,
    currentTransform,
    minimapRef,
    svgRef,
  });

  // Keyboard navigation handler
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
      return;
    }

    const currentIndex = selectedNode
      ? visibleNodes.findIndex((n) => n.id === selectedNode)
      : -1;

    switch (e.key) {
      case "Tab":
        e.preventDefault();
        if (visibleNodes.length === 0) return;
        const nextIndex = e.shiftKey
          ? (currentIndex - 1 + visibleNodes.length) % visibleNodes.length
          : (currentIndex + 1) % visibleNodes.length;
        const nextNode = visibleNodes[nextIndex];
        setSelectedNode(nextNode.id);
        break;

      case "ArrowRight":
      case "ArrowDown":
        e.preventDefault();
        if (visibleNodes.length === 0) return;
        const forwardIndex = (currentIndex + 1) % visibleNodes.length;
        setSelectedNode(visibleNodes[forwardIndex].id);
        break;

      case "ArrowLeft":
      case "ArrowUp":
        e.preventDefault();
        if (visibleNodes.length === 0) return;
        const backIndex = (currentIndex - 1 + visibleNodes.length) % visibleNodes.length;
        setSelectedNode(visibleNodes[backIndex].id);
        break;

      case "Enter":
        if (selectedNode) {
          const node = nodes.find((n) => n.id === selectedNode);
          if (node) {
            setDetailsPanelNode(node as SimulationNode);
          }
        }
        break;

      case "Escape":
        setSelectedNode(null);
        setDetailsPanelNode(null);
        closeMenu();
        break;

      case "+":
      case "=":
        e.preventDefault();
        if (svgRef.current) {
          const svg = d3.select(svgRef.current);
          const zoom = (svgRef.current as SVGSVGElement & { __zoom?: d3.ZoomBehavior<SVGSVGElement, unknown> }).__zoom;
          if (zoom) {
            svg.transition()
              .duration(300)
              .call(zoom.scaleBy, 1.3);
          }
        }
        break;

      case "-":
      case "_":
        e.preventDefault();
        if (svgRef.current) {
          const svg = d3.select(svgRef.current);
          const zoom = (svgRef.current as SVGSVGElement & { __zoom?: d3.ZoomBehavior<SVGSVGElement, unknown> }).__zoom;
          if (zoom) {
            svg.transition()
              .duration(300)
              .call(zoom.scaleBy, 0.7);
          }
        }
        break;

      case "f":
      case "F":
        if (!e.ctrlKey && !e.metaKey) {
          e.preventDefault();
          toggleFullscreen();
        }
        break;

      case "r":
      case "R":
        if (!e.ctrlKey && !e.metaKey) {
          e.preventDefault();
          resetView();
        }
        break;

      case "0":
        e.preventDefault();
        resetView();
        break;
    }
  }, [selectedNode, visibleNodes, nodes, closeMenu, toggleFullscreen, resetView, setSelectedNode, setDetailsPanelNode, svgRef]);

  // Add keyboard event listener
  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  // Node config for canvas renderer
  const nodeConfigForCanvas = getNodeConfigForCanvas();

  return (
    <div
      ref={fullscreenRef}
      className={`relative w-full h-full min-h-[600px] bg-slate-950 rounded-xl overflow-hidden ${
        isFullscreen ? "fixed inset-0 z-50 rounded-none" : ""
      }`}
      tabIndex={0}
    >
      {/* Animated gradient background with ambient glow */}
      <div className="absolute inset-0 overflow-hidden">
        {/* Primary gradient orbs */}
        <div
          className="absolute inset-0 opacity-40"
          style={{
            background: `
              radial-gradient(ellipse 600px 400px at 20% 20%, rgba(139, 92, 246, 0.2) 0%, transparent 70%),
              radial-gradient(ellipse 500px 350px at 80% 80%, rgba(244, 63, 94, 0.15) 0%, transparent 70%),
              radial-gradient(ellipse 400px 300px at 50% 50%, rgba(34, 197, 94, 0.1) 0%, transparent 70%),
              radial-gradient(ellipse 300px 200px at 70% 30%, rgba(56, 189, 248, 0.1) 0%, transparent 70%)
            `,
          }}
        />
        {/* Animated floating orbs */}
        <div
          className="absolute w-96 h-96 rounded-full opacity-[0.03] blur-3xl animate-pulse"
          style={{
            background: "linear-gradient(135deg, #8b5cf6 0%, #ec4899 100%)",
            top: "10%",
            left: "20%",
            animationDuration: "8s",
          }}
        />
        <div
          className="absolute w-80 h-80 rounded-full opacity-[0.04] blur-3xl animate-pulse"
          style={{
            background: "linear-gradient(135deg, #0ea5e9 0%, #22c55e 100%)",
            bottom: "20%",
            right: "15%",
            animationDuration: "10s",
            animationDelay: "2s",
          }}
        />
        {/* Grid pattern with fade */}
        <div
          className="absolute inset-0 opacity-[0.02]"
          style={{
            backgroundImage: `
              linear-gradient(rgba(148, 163, 184, 0.8) 1px, transparent 1px),
              linear-gradient(90deg, rgba(148, 163, 184, 0.8) 1px, transparent 1px)
            `,
            backgroundSize: '40px 40px',
            mask: 'radial-gradient(ellipse at center, black 30%, transparent 80%)',
            WebkitMask: 'radial-gradient(ellipse at center, black 30%, transparent 80%)',
          }}
        />
        {/* Vignette effect */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background: 'radial-gradient(ellipse at center, transparent 50%, rgba(2, 6, 23, 0.5) 100%)',
          }}
        />
      </div>

      {/* Top toolbar */}
      <div className="absolute top-4 left-4 right-4 z-10 flex items-start justify-between gap-4">
        {/* Left controls */}
        <div className="flex flex-col gap-3">
          {/* Search with Autocomplete */}
          <GraphSearchCombobox
            nodes={nodes}
            onSelect={handleFocusNode}
            onSearch={setSearchQuery}
            className="w-56"
          />

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

          {/* Temporal Filter */}
          <TemporalSlider
            eventDates={eventDates}
            dateRange={dateRange}
            onDateRangeChange={setDateRange}
            enabled={temporalFilterEnabled}
            onToggle={setTemporalFilterEnabled}
            temporalityFilter={temporalityFilter}
            onTemporalityChange={setTemporalityFilter}
          />
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
              <div className="w-px h-4 bg-slate-700" />
              <button
                onClick={() => setForceCanvasMode(prev => prev === null ? !useCanvasRendering : prev === true ? false : true)}
                className={`flex items-center gap-1.5 px-1.5 py-0.5 rounded transition-colors ${
                  useCanvasRendering
                    ? "bg-emerald-500/20 text-emerald-400"
                    : "bg-slate-700/50 text-slate-400"
                }`}
                title={`Render mode: ${useCanvasRendering ? "Canvas (fast)" : "SVG (detailed)"}. Click to toggle.`}
              >
                <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                <span className="text-[10px] font-medium">
                  {useCanvasRendering ? "Fast" : "SVG"}
                </span>
              </button>
            </div>
          </div>

          {/* View controls */}
          <div className="bg-slate-900/95 backdrop-blur-sm rounded-lg border border-slate-800 flex">
            <button
              onClick={resetView}
              className="px-3 py-2 text-xs text-slate-400 hover:text-white hover:bg-slate-800 transition-all rounded-l-lg border-r border-slate-800"
              title="Reset view (R)"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>
            <button
              onClick={toggleFullscreen}
              className="px-3 py-2 text-xs text-slate-400 hover:text-white hover:bg-slate-800 transition-all border-r border-slate-800"
              title="Fullscreen (F)"
            >
              {isFullscreen ? (
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 9V4.5M9 9H4.5M9 9L3.75 3.75M9 15v4.5M9 15H4.5M9 15l-5.25 5.25M15 9h4.5M15 9V4.5M15 9l5.25-5.25M15 15h4.5M15 15v4.5m0-4.5l5.25 5.25" />
                </svg>
              ) : (
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3.75 3.75v4.5m0-4.5h4.5m-4.5 0L9 9M3.75 20.25v-4.5m0 4.5h4.5m-4.5 0L9 15M20.25 3.75h-4.5m4.5 0v4.5m0-4.5L15 9m5.25 11.25h-4.5m4.5 0v-4.5m0 4.5L15 15" />
                </svg>
              )}
            </button>
            <button
              onClick={exportAsPNG}
              className="px-3 py-2 text-xs text-slate-400 hover:text-white hover:bg-slate-800 transition-all border-r border-slate-800"
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
          <div><span className="text-slate-400">Click</span> to select - <span className="text-slate-400">Double-click</span> for details</div>
        </div>
      </div>

      {/* Graph Container - SVG or Canvas based on node count */}
      <div ref={containerRef} className="w-full h-full">
        {useCanvasRendering ? (
          <CanvasRenderer
            nodes={simulationNodesRef.current as unknown as import("../graph/CanvasRenderer").CanvasNode[]}
            edges={simulationEdgesRef.current as unknown as import("../graph/CanvasRenderer").CanvasEdge[]}
            width={dimensions.width}
            height={dimensions.height}
            transform={currentTransform}
            selectedNodeId={selectedNode}
            hoveredNodeId={hoveredNode?.id ?? null}
            pinnedNodes={pinnedNodes}
            searchHighlightedNodes={searchFilteredNodes}
            nodeConfig={nodeConfigForCanvas}
            showLabels={showLabels}
            temporalFilterEnabled={temporalFilterEnabled}
            onNodeClick={handleCanvasNodeClick as unknown as (node: import("../graph/CanvasRenderer").CanvasNode, event: MouseEvent) => void}
            onNodeHover={handleCanvasNodeHover as unknown as (node: import("../graph/CanvasRenderer").CanvasNode | null, x: number, y: number) => void}
            onNodeContextMenu={handleCanvasNodeContextMenu as unknown as (node: import("../graph/CanvasRenderer").CanvasNode, event: MouseEvent) => void}
            onBackgroundClick={handleCanvasBackgroundClick}
          />
        ) : (
          <svg
            ref={svgRef}
            width={dimensions.width}
            height={dimensions.height}
            className="w-full h-full"
          />
        )}
      </div>

      {/* Loading state - skeleton while simulation warms up */}
      {isSimulating && nodes.length > 0 && (
        <div className="absolute top-4 right-4 z-30">
          <div className="bg-slate-900/95 backdrop-blur-sm rounded-lg px-3 py-2 border border-slate-800 flex items-center gap-2">
            <div className="w-3 h-3 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
            <span className="text-xs text-slate-400">Calculating layout...</span>
          </div>
        </div>
      )}

      {/* Empty state when no nodes match filters */}
      {nodes.filter(n => activeFilters.has(n.node_type)).length === 0 && nodes.length > 0 && (
        <div className="absolute inset-0 flex items-center justify-center z-20 pointer-events-none">
          <div className="bg-slate-900/98 backdrop-blur-sm rounded-2xl px-8 py-6 border border-slate-800 text-center pointer-events-auto">
            <svg className="w-12 h-12 mx-auto mb-3 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <h3 className="text-slate-300 font-medium mb-1">No nodes to display</h3>
            <p className="text-sm text-slate-500 mb-4">Try adjusting your filters to see more nodes</p>
            <button
              onClick={() => setActiveFilters(new Set(Object.keys(NODE_CONFIG)))}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg transition-colors"
            >
              Reset filters
            </button>
          </div>
        </div>
      )}

      {/* Empty state when no nodes at all */}
      {nodes.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center z-20 pointer-events-none">
          <div className="bg-slate-900/98 backdrop-blur-sm rounded-2xl px-8 py-6 border border-slate-800 text-center">
            <svg className="w-12 h-12 mx-auto mb-3 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            <h3 className="text-slate-300 font-medium mb-1">No graph data</h3>
            <p className="text-sm text-slate-500">Build the knowledge graph to visualize patient data</p>
          </div>
        </div>
      )}

      {/* Context Menu */}
      {menuState.isOpen && menuState.nodeId && (
        <>
          {/* Backdrop to close menu */}
          <div
            className="fixed inset-0 z-40"
            onClick={closeMenu}
            onContextMenu={(e) => {
              e.preventDefault();
              closeMenu();
            }}
          />
          {/* Menu */}
          <div
            className="fixed z-50 min-w-[200px] bg-slate-900/98 backdrop-blur-sm border border-slate-700 rounded-xl shadow-2xl p-1.5 animate-in fade-in zoom-in-95 duration-100"
            style={{
              left: menuState.x,
              top: menuState.y,
            }}
          >
            {(() => {
              const node = nodes.find((n) => n.id === menuState.nodeId);
              if (!node) return null;
              const neighborCount = getNeighborCount(node.id);
              const hiddenNeighborCount = getHiddenNeighborCount(node.id);
              const isPinned = pinnedNodes.has(node.id);
              const isHidden = hiddenNodes.has(node.id);

              return (
                <>
                  {/* Header */}
                  <div className="px-3 py-2 border-b border-slate-800 mb-1">
                    <div className="text-sm font-medium text-slate-200 truncate max-w-[180px]">
                      {node.label}
                    </div>
                    <div className="text-xs text-slate-500 capitalize">{node.node_type}</div>
                  </div>

                  {/* Expand/Collapse Neighbors */}
                  {hiddenNeighborCount > 0 ? (
                    <button
                      className="flex w-full items-center gap-2 px-3 py-2 text-sm text-slate-200 hover:bg-slate-800 rounded-lg cursor-pointer"
                      onClick={() => handleExpandNeighbors(node.id)}
                    >
                      <svg className="w-4 h-4 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
                      </svg>
                      <span>Expand neighbors</span>
                      <span className="ml-auto text-xs text-slate-500 bg-slate-800 px-1.5 py-0.5 rounded">
                        {hiddenNeighborCount}
                      </span>
                    </button>
                  ) : neighborCount > 0 ? (
                    <button
                      className="flex w-full items-center gap-2 px-3 py-2 text-sm text-slate-200 hover:bg-slate-800 rounded-lg cursor-pointer"
                      onClick={() => handleCollapseNeighbors(node.id)}
                    >
                      <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
                      </svg>
                      <span>Collapse neighbors</span>
                    </button>
                  ) : null}

                  {/* Focus on this node */}
                  <button
                    className="flex w-full items-center gap-2 px-3 py-2 text-sm text-slate-200 hover:bg-slate-800 rounded-lg cursor-pointer"
                    onClick={() => handleFocusNode(node.id)}
                  >
                    <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7" />
                    </svg>
                    <span>Focus on node</span>
                  </button>

                  <div className="h-px bg-slate-800 my-1" />

                  {/* Hide/Show Node */}
                  {isHidden ? (
                    <button
                      className="flex w-full items-center gap-2 px-3 py-2 text-sm text-slate-200 hover:bg-slate-800 rounded-lg cursor-pointer"
                      onClick={() => handleShowNode(node.id)}
                    >
                      <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                      </svg>
                      <span>Show node</span>
                    </button>
                  ) : (
                    <button
                      className="flex w-full items-center gap-2 px-3 py-2 text-sm text-slate-200 hover:bg-slate-800 rounded-lg cursor-pointer"
                      onClick={() => handleHideNode(node.id)}
                    >
                      <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                      </svg>
                      <span>Hide node</span>
                    </button>
                  )}

                  {/* Pin/Unpin Position */}
                  {isPinned ? (
                    <button
                      className="flex w-full items-center gap-2 px-3 py-2 text-sm text-slate-200 hover:bg-slate-800 rounded-lg cursor-pointer"
                      onClick={() => handleUnpinNode(node.id)}
                    >
                      <svg className="w-4 h-4 text-amber-400" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M16 12V4h1V2H7v2h1v8l-2 2v2h5.2v6h1.6v-6H18v-2l-2-2z" />
                      </svg>
                      <span>Unpin position</span>
                    </button>
                  ) : (
                    <button
                      className="flex w-full items-center gap-2 px-3 py-2 text-sm text-slate-200 hover:bg-slate-800 rounded-lg cursor-pointer"
                      onClick={() => handlePinNode(node.id)}
                    >
                      <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 12V4h1V2H7v2h1v8l-2 2v2h5.2v6h1.6v-6H18v-2l-2-2z" />
                      </svg>
                      <span>Pin position</span>
                    </button>
                  )}

                  <div className="h-px bg-slate-800 my-1" />

                  {/* Copy OMOP ID */}
                  {node.omop_concept_id && (
                    <button
                      className="flex w-full items-center gap-2 px-3 py-2 text-sm text-slate-200 hover:bg-slate-800 rounded-lg cursor-pointer"
                      onClick={() => handleCopyOmopId(node.omop_concept_id!)}
                    >
                      <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                      </svg>
                      <span>Copy OMOP ID</span>
                      <span className="ml-auto text-xs text-indigo-400 font-mono">{node.omop_concept_id}</span>
                    </button>
                  )}

                  {/* Copy Node ID */}
                  <button
                    className="flex w-full items-center gap-2 px-3 py-2 text-sm text-slate-200 hover:bg-slate-800 rounded-lg cursor-pointer"
                    onClick={() => {
                      navigator.clipboard.writeText(node.id);
                      closeMenu();
                    }}
                  >
                    <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                    </svg>
                    <span>Copy node ID</span>
                  </button>
                </>
              );
            })()}
          </div>
        </>
      )}

      {/* Tooltip with rich preview data */}
      {hoveredNode && !detailsPanelNode && (
        <div
          className="fixed z-50 pointer-events-none animate-in fade-in duration-150"
          style={{
            left: tooltipPos.x + 16,
            top: tooltipPos.y - 12,
          }}
        >
          <div className="bg-slate-900/95 backdrop-blur-sm border border-slate-700 rounded-xl shadow-2xl px-4 py-3 max-w-sm">
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

            <div className="text-xs text-slate-400 space-y-1.5">
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

              {/* Connection count */}
              <div className="flex justify-between">
                <span className="text-slate-500">Connections</span>
                <span className="font-medium text-slate-300">
                  {edges.filter((e) => e.source_node_id === hoveredNode.id || e.target_node_id === hoveredNode.id).length}
                </span>
              </div>

              {/* Confidence score with visual bar */}
              {typeof hoveredNode.properties?.confidence_score === "number" && (
                <div className="space-y-1">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Confidence</span>
                    <span className={`font-medium ${
                      hoveredNode.properties.confidence_score >= 0.8
                        ? "text-emerald-400"
                        : hoveredNode.properties.confidence_score >= 0.6
                          ? "text-amber-400"
                          : "text-red-400"
                    }`}>
                      {Math.round(hoveredNode.properties.confidence_score * 100)}%
                    </span>
                  </div>
                  <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                    <div
                      className={`h-full rounded-full ${
                        hoveredNode.properties.confidence_score >= 0.8
                          ? "bg-emerald-500"
                          : hoveredNode.properties.confidence_score >= 0.6
                            ? "bg-amber-500"
                            : "bg-red-500"
                      }`}
                      style={{ width: `${hoveredNode.properties.confidence_score * 100}%` }}
                    />
                  </div>
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

              {/* Provenance source text excerpt */}
              {typeof hoveredNode.properties?.source_text === "string" && (
                <div className="mt-2 pt-2 border-t border-slate-800">
                  <span className="text-slate-500">Source: </span>
                  <span className="text-slate-300 italic text-[10px] leading-relaxed">
                    &quot;{hoveredNode.properties.source_text.length > 80
                      ? hoveredNode.properties.source_text.slice(0, 80) + "..."
                      : hoveredNode.properties.source_text}&quot;
                  </span>
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

              {/* Click for details hint */}
              <div className="mt-2 pt-2 border-t border-slate-800 text-center">
                <span className="text-[10px] text-slate-600">Click to select - Double-click for details</span>
              </div>
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
                    <span className="text-xs text-slate-600">-</span>
                    <span className="text-xs text-slate-500">
                      {edges.filter((e) => e.source_node_id === selectedNode || e.target_node_id === selectedNode).length} connections
                    </span>
                    <button
                      onClick={() => setDetailsPanelNode(node as SimulationNode)}
                      className="ml-2 px-2 py-1 text-xs text-indigo-400 hover:text-indigo-300 hover:bg-indigo-950/50 rounded transition-colors"
                    >
                      View details
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
