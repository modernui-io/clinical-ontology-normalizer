"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import DataSourceModeBanner from "@/components/readiness/DataSourceModeBanner";
import { useAuth } from "@/hooks/use-auth";
import {
  Network,
  Search,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Download,
  RefreshCw,
  Filter,
  Activity,
  Pill,
  Stethoscope,
  FlaskConical,
  Eye,
  Dna,
  GitBranch,
  ChevronRight,
  Info,
  Loader2,
  AlertCircle,
  CheckCircle,
  Database,
  Server,
} from "lucide-react";

// ============================================================================
// Types
// ============================================================================

interface GraphNode {
  id: string;
  concept_id: number;
  concept_name: string;
  vocabulary_id: string;
  domain_id: string;
  concept_class_id?: string;
  synonyms?: string[];
  x?: number;
  y?: number;
  z?: number;
  color?: string;
  size?: number;
}

interface GraphEdge {
  source: string;
  target: string;
  relationship_type: string;
}

interface ConceptNeighbor {
  concept: {
    concept_id: number;
    concept_name: string;
    vocabulary_id: string;
    domain_id: string;
  };
  relationship: string;
  direction: string;
}

interface SearchResult {
  concept_id: number;
  concept_name: string;
  vocabulary_id: string;
  domain_id: string;
  concept_class_id?: string;
  synonyms?: string[];
}

interface HealthStatus {
  status: string;
  latency_ms: number | null;
  server_version: string | null;
  database: string | null;
  error_message: string | null;
  mock_mode?: boolean;
}

// Domain colors for nodes
const DOMAIN_COLORS: Record<string, string> = {
  Condition: "#ef4444", // red
  Drug: "#3b82f6", // blue
  Procedure: "#22c55e", // green
  Measurement: "#f59e0b", // amber
  Observation: "#8b5cf6", // violet
  Gene: "#ec4899", // pink
  Pathway: "#06b6d4", // cyan
  default: "#6b7280", // gray
};

const DOMAIN_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  Condition: Stethoscope,
  Drug: Pill,
  Procedure: Activity,
  Measurement: FlaskConical,
  Observation: Eye,
  Gene: Dna,
  Pathway: GitBranch,
};

// ============================================================================
// Graph Canvas Component (2D with Canvas API)
// ============================================================================

interface GraphCanvasProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedNode: GraphNode | null;
  onNodeClick: (node: GraphNode) => void;
  onNodeHover: (node: GraphNode | null) => void;
}

function GraphCanvas({ nodes, edges, selectedNode, onNodeClick, onNodeHover }: GraphCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null);

  // Apply force-directed layout
  useEffect(() => {
    if (nodes.length === 0) return;

    // Simple force-directed layout
    const width = 800;
    const height = 600;
    const centerX = width / 2;
    const centerY = height / 2;

    // Initialize positions in a circle
    nodes.forEach((node, i) => {
      const angle = (i / nodes.length) * 2 * Math.PI;
      const radius = Math.min(width, height) / 3;
      node.x = centerX + radius * Math.cos(angle);
      node.y = centerY + radius * Math.sin(angle);
    });

    // Simple iteration for layout
    for (let iter = 0; iter < 50; iter++) {
      // Repulsion between nodes
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = (nodes[j].x || 0) - (nodes[i].x || 0);
          const dy = (nodes[j].y || 0) - (nodes[i].y || 0);
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          const force = 1000 / (dist * dist);
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;
          nodes[i].x = (nodes[i].x || 0) - fx;
          nodes[i].y = (nodes[i].y || 0) - fy;
          nodes[j].x = (nodes[j].x || 0) + fx;
          nodes[j].y = (nodes[j].y || 0) + fy;
        }
      }

      // Attraction along edges
      edges.forEach(edge => {
        const source = nodes.find(n => n.id === edge.source);
        const target = nodes.find(n => n.id === edge.target);
        if (source && target) {
          const dx = (target.x || 0) - (source.x || 0);
          const dy = (target.y || 0) - (source.y || 0);
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          const force = dist * 0.01;
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;
          source.x = (source.x || 0) + fx;
          source.y = (source.y || 0) + fy;
          target.x = (target.x || 0) - fx;
          target.y = (target.y || 0) - fy;
        }
      });

      // Center gravity
      nodes.forEach(node => {
        node.x = (node.x || 0) * 0.99 + centerX * 0.01;
        node.y = (node.y || 0) * 0.99 + centerY * 0.01;
      });
    }
  }, [nodes, edges]);

  // Draw canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;

    // Clear
    ctx.fillStyle = "#0f172a";
    ctx.fillRect(0, 0, width, height);

    // Apply transforms
    ctx.save();
    ctx.translate(offset.x + width / 2, offset.y + height / 2);
    ctx.scale(zoom, zoom);
    ctx.translate(-width / 2, -height / 2);

    // Draw edges
    ctx.strokeStyle = "#374151";
    ctx.lineWidth = 1;
    edges.forEach(edge => {
      const source = nodes.find(n => n.id === edge.source);
      const target = nodes.find(n => n.id === edge.target);
      if (source && target && source.x && source.y && target.x && target.y) {
        ctx.beginPath();
        ctx.moveTo(source.x, source.y);
        ctx.lineTo(target.x, target.y);
        ctx.stroke();
      }
    });

    // Draw nodes
    nodes.forEach(node => {
      if (!node.x || !node.y) return;

      const isSelected = selectedNode?.id === node.id;
      const isHovered = hoveredNode?.id === node.id;
      const color = DOMAIN_COLORS[node.domain_id] || DOMAIN_COLORS.default;
      const radius = isSelected ? 20 : isHovered ? 18 : 15;

      // Node circle
      ctx.beginPath();
      ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI);
      ctx.fillStyle = color;
      ctx.fill();

      if (isSelected || isHovered) {
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 3;
        ctx.stroke();
      }

      // Node label
      ctx.fillStyle = "#ffffff";
      ctx.font = "10px sans-serif";
      ctx.textAlign = "center";
      const label = node.concept_name.length > 20
        ? node.concept_name.substring(0, 17) + "..."
        : node.concept_name;
      ctx.fillText(label, node.x, node.y + radius + 15);
    });

    ctx.restore();

    // Draw legend
    ctx.fillStyle = "#ffffff";
    ctx.font = "12px sans-serif";
    ctx.textAlign = "left";
    let legendY = 20;
    Object.entries(DOMAIN_COLORS).filter(([k]) => k !== "default").forEach(([domain, color]) => {
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(20, legendY, 6, 0, 2 * Math.PI);
      ctx.fill();
      ctx.fillStyle = "#ffffff";
      ctx.fillText(domain, 35, legendY + 4);
      legendY += 20;
    });

  }, [nodes, edges, zoom, offset, selectedNode, hoveredNode]);

  // Mouse handlers
  const handleMouseDown = (e: React.MouseEvent) => {
    setDragging(true);
    setDragStart({ x: e.clientX - offset.x, y: e.clientY - offset.y });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left - offset.x - canvas.width / 2) / zoom + canvas.width / 2;
    const y = (e.clientY - rect.top - offset.y - canvas.height / 2) / zoom + canvas.height / 2;

    // Check for node hover
    let foundNode: GraphNode | null = null;
    for (const node of nodes) {
      if (node.x && node.y) {
        const dx = x - node.x;
        const dy = y - node.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 20) {
          foundNode = node;
          break;
        }
      }
    }
    setHoveredNode(foundNode);
    onNodeHover(foundNode);

    if (dragging) {
      setOffset({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y,
      });
    }
  };

  const handleMouseUp = () => {
    setDragging(false);
  };

  const handleClick = (e: React.MouseEvent) => {
    if (hoveredNode) {
      onNodeClick(hoveredNode);
    }
  };

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setZoom(z => Math.max(0.1, Math.min(5, z * delta)));
  };

  return (
    <div className="relative w-full h-full bg-slate-900 rounded-lg overflow-hidden">
      <canvas
        ref={canvasRef}
        width={800}
        height={600}
        className="w-full h-full cursor-grab"
        style={{ cursor: dragging ? "grabbing" : hoveredNode ? "pointer" : "grab" }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onClick={handleClick}
        onWheel={handleWheel}
      />

      {/* Zoom controls */}
      <div className="absolute bottom-4 right-4 flex flex-col gap-2">
        <Button
          variant="secondary"
          size="icon"
          className="h-8 w-8"
          onClick={() => setZoom(z => Math.min(5, z * 1.2))}
        >
          <ZoomIn className="h-4 w-4" />
        </Button>
        <Button
          variant="secondary"
          size="icon"
          className="h-8 w-8"
          onClick={() => setZoom(z => Math.max(0.1, z / 1.2))}
        >
          <ZoomOut className="h-4 w-4" />
        </Button>
        <Button
          variant="secondary"
          size="icon"
          className="h-8 w-8"
          onClick={() => { setZoom(1); setOffset({ x: 0, y: 0 }); }}
        >
          <Maximize2 className="h-4 w-4" />
        </Button>
      </div>

      {/* Node count */}
      <div className="absolute top-4 right-4 bg-slate-800/80 px-3 py-1 rounded-full text-xs text-slate-300">
        {nodes.length} nodes, {edges.length} edges
      </div>
    </div>
  );
}

// ============================================================================
// Main Page Component
// ============================================================================

export default function GraphExplorerPage() {
  const { isDemo, isLoading: isAuthLoading } = useAuth();
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null);
  const [dataMode, setDataMode] = useState<"live" | "simulation">("live");
  const [activeFilters, setActiveFilters] = useState<string[]>([
    "Condition",
    "Drug",
    "Procedure",
    "Measurement",
  ]);
  const [neighborDepth, setNeighborDepth] = useState("1");

  // Check Neo4j health on load (skip in demo mode)
  useEffect(() => {
    if (isAuthLoading) return;
    if (isDemo) {
      setHealthStatus({ status: "mock_mode", latency_ms: null, server_version: null, database: null, error_message: null, mock_mode: true });
      setDataMode("simulation");
      return;
    }
    const checkHealth = async () => {
      try {
        const response = await fetch("/api/graph/health");
        if (response.ok) {
          const data = await response.json();
          setHealthStatus(data);
        }
      } catch {
        setHealthStatus({
          status: "error",
          latency_ms: null,
          server_version: null,
          database: null,
          error_message: "Cannot connect to API",
        });
      }
    };
    checkHealth();
  }, [isDemo, isAuthLoading]);

  // Load initial sample data (use mock in demo mode)
  useEffect(() => {
    if (isAuthLoading) return;
    if (isDemo) {
      loadMockData();
      return;
    }
    loadSampleData();
  }, [isDemo, isAuthLoading]);

  const loadSampleData = async () => {
    setIsLoading(true);
    try {
      // First try to load sample data
      await fetch("/api/graph/etl/load-sample", {
        method: "POST",
      });

      // Then search for diabetes to show an example
      const response = await fetch(
        "/api/graph/concepts/search?q=diabetes&limit=5"
      );
      if (response.ok) {
        const data = await response.json();
        if (data.concepts && data.concepts.length > 0) {
          // Load neighbors for the first concept
          const conceptId = data.concepts[0].concept_id;
          await loadConceptNeighbors(conceptId);
        }
      }
    } catch (error) {
      console.error("Failed to load sample data:", error);
      // Load mock data as fallback
      loadMockData();
      setDataMode("simulation");
    } finally {
      setIsLoading(false);
    }
  };

  const loadMockData = () => {
    const mockNodes: GraphNode[] = [
      { id: "201826", concept_id: 201826, concept_name: "Type 2 diabetes mellitus", vocabulary_id: "SNOMED", domain_id: "Condition" },
      { id: "4329847", concept_id: 4329847, concept_name: "Diabetic retinopathy", vocabulary_id: "SNOMED", domain_id: "Condition" },
      { id: "316866", concept_id: 316866, concept_name: "Hypertensive disorder", vocabulary_id: "SNOMED", domain_id: "Condition" },
      { id: "1503297", concept_id: 1503297, concept_name: "Metformin", vocabulary_id: "RxNorm", domain_id: "Drug" },
      { id: "1510202", concept_id: 1510202, concept_name: "Insulin glargine", vocabulary_id: "RxNorm", domain_id: "Drug" },
      { id: "1308216", concept_id: 1308216, concept_name: "Lisinopril", vocabulary_id: "RxNorm", domain_id: "Drug" },
      { id: "4058243", concept_id: 4058243, concept_name: "HbA1c measurement", vocabulary_id: "LOINC", domain_id: "Measurement" },
      { id: "3004501", concept_id: 3004501, concept_name: "Blood glucose", vocabulary_id: "LOINC", domain_id: "Measurement" },
      { id: "4000479", concept_id: 4000479, concept_name: "Eye exam", vocabulary_id: "SNOMED", domain_id: "Procedure" },
      { id: "45770817", concept_id: 45770817, concept_name: "TCF7L2 gene", vocabulary_id: "HGNC", domain_id: "Gene" },
    ];

    const mockEdges: GraphEdge[] = [
      { source: "201826", target: "4329847", relationship_type: "HAS_COMPLICATION" },
      { source: "1503297", target: "201826", relationship_type: "MAY_TREAT" },
      { source: "1510202", target: "201826", relationship_type: "MAY_TREAT" },
      { source: "1308216", target: "316866", relationship_type: "MAY_TREAT" },
      { source: "4058243", target: "201826", relationship_type: "MEASURES" },
      { source: "3004501", target: "201826", relationship_type: "MEASURES" },
      { source: "4000479", target: "4329847", relationship_type: "DIAGNOSES" },
      { source: "45770817", target: "201826", relationship_type: "ASSOCIATED_WITH" },
    ];

    setNodes(mockNodes.filter(n => activeFilters.includes(n.domain_id) || n.domain_id === "Gene"));
    setEdges(mockEdges);
  };

  const loadConceptNeighbors = async (conceptId: number) => {
    setIsLoading(true);
    try {
      const categories = activeFilters.map(f => `categories=${f}`).join("&");
      const response = await fetch(
        `/api/graph/concepts/${conceptId}/neighbors?max_depth=${neighborDepth}&${categories}&limit=30`
      );

      if (response.ok) {
        const data = await response.json();
        const neighbors: ConceptNeighbor[] = data.neighbors || [];

        // Build nodes and edges
        const newNodes: GraphNode[] = [];
        const newEdges: GraphEdge[] = [];
        const nodeIds = new Set<string>();

        // Add center node if not exists
        const centerNodeId = String(conceptId);
        const existingCenter = nodes.find(n => n.id === centerNodeId);
        if (existingCenter) {
          newNodes.push(existingCenter);
        } else if (selectedNode && selectedNode.concept_id === conceptId) {
          newNodes.push({ ...selectedNode, id: centerNodeId });
        }
        nodeIds.add(centerNodeId);

        // Add neighbors
        neighbors.forEach(neighbor => {
          const nodeId = String(neighbor.concept.concept_id);
          if (!nodeIds.has(nodeId)) {
            nodeIds.add(nodeId);
            newNodes.push({
              id: nodeId,
              concept_id: neighbor.concept.concept_id,
              concept_name: neighbor.concept.concept_name,
              vocabulary_id: neighbor.concept.vocabulary_id,
              domain_id: neighbor.concept.domain_id,
            });
          }

          // Add edge
          if (neighbor.direction === "outgoing") {
            newEdges.push({
              source: centerNodeId,
              target: nodeId,
              relationship_type: neighbor.relationship,
            });
          } else {
            newEdges.push({
              source: nodeId,
              target: centerNodeId,
              relationship_type: neighbor.relationship,
            });
          }
        });

        setNodes(newNodes);
        setEdges(newEdges);
      }
    } catch (error) {
      console.error("Failed to load neighbors:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;

    setIsSearching(true);
    try {
      const categories = activeFilters.map(f => `categories=${f}`).join("&");
      const response = await fetch(
        `/api/graph/concepts/search?q=${encodeURIComponent(searchQuery)}&${categories}&limit=20`
      );

      if (response.ok) {
        const data = await response.json();
        setSearchResults(data.concepts || []);
      }
    } catch (error) {
      console.error("Search failed:", error);
      setSearchResults([]);
    } finally {
      setIsSearching(false);
    }
  };

  const handleSelectSearchResult = async (result: SearchResult) => {
    const node: GraphNode = {
      id: String(result.concept_id),
      concept_id: result.concept_id,
      concept_name: result.concept_name,
      vocabulary_id: result.vocabulary_id,
      domain_id: result.domain_id,
      concept_class_id: result.concept_class_id,
      synonyms: result.synonyms,
    };

    setSelectedNode(node);
    setSearchResults([]);
    setSearchQuery("");

    // Load neighbors for this concept
    await loadConceptNeighbors(result.concept_id);
  };

  const handleNodeClick = (node: GraphNode) => {
    setSelectedNode(node);
  };

  const handleExpandNode = async () => {
    if (selectedNode) {
      await loadConceptNeighbors(selectedNode.concept_id);
    }
  };

  const toggleFilter = (domain: string) => {
    setActiveFilters(prev =>
      prev.includes(domain)
        ? prev.filter(d => d !== domain)
        : [...prev, domain]
    );
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Network className="h-6 w-6" />
            Knowledge Graph Explorer
          </h1>
          <p className="text-muted-foreground">
            Explore clinical ontology relationships in the knowledge graph
          </p>
        </div>
        <div className="flex items-center gap-4">
          {/* Connection Status */}
          <div className="flex items-center gap-2 text-sm">
            {healthStatus?.status === "connected" && (
              <>
                <CheckCircle className="h-4 w-4 text-green-500" />
                <span className="text-green-600">Neo4j Connected</span>
                {healthStatus.latency_ms && (
                  <span className="text-muted-foreground">
                    ({healthStatus.latency_ms}ms)
                  </span>
                )}
              </>
            )}
            {healthStatus?.status === "mock_mode" && (
              <>
                <Database className="h-4 w-4 text-amber-500" />
                <span className="text-amber-600">Demo Mode</span>
              </>
            )}
            {healthStatus?.status === "error" && (
              <>
                <AlertCircle className="h-4 w-4 text-red-500" />
                <span className="text-red-600">Disconnected</span>
              </>
            )}
          </div>
          <Link href="/analytics/graph/patients">
            <Button variant="outline">
              Patient Similarity
              <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </Link>
          <Link href="/analytics/graph/pathways">
            <Button variant="outline">
              Drug-Disease Pathways
              <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </Link>
        </div>
      </div>

      {dataMode === "simulation" && (
        <DataSourceModeBanner
          mode={dataMode}
          title="Graph explorer data source"
          description="Backend API is unavailable. Graph visualization shows demonstration knowledge graph data."
          backendEndpoints={["/api/graph/health", "/api/graph/concepts/search"]}
        />
      )}

      {/* Main Content */}
      <div className="grid grid-cols-12 gap-6">
        {/* Left Panel - Search and Filters */}
        <div className="col-span-3 space-y-4">
          {/* Search */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Search Concepts</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex gap-2">
                <Input
                  placeholder="Search by name..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                />
                <Button
                  size="icon"
                  onClick={handleSearch}
                  disabled={isSearching}
                >
                  {isSearching ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Search className="h-4 w-4" />
                  )}
                </Button>
              </div>

              {/* Search Results */}
              {searchResults.length > 0 && (
                <ScrollArea className="h-[200px] border rounded-md">
                  <div className="p-2 space-y-1">
                    {searchResults.map((result) => (
                      <div
                        key={result.concept_id}
                        className="p-2 rounded hover:bg-accent cursor-pointer"
                        onClick={() => handleSelectSearchResult(result)}
                      >
                        <div className="flex items-center gap-2">
                          <div
                            className="h-2 w-2 rounded-full"
                            style={{
                              backgroundColor:
                                DOMAIN_COLORS[result.domain_id] ||
                                DOMAIN_COLORS.default,
                            }}
                          />
                          <span className="text-sm font-medium truncate">
                            {result.concept_name}
                          </span>
                        </div>
                        <div className="text-xs text-muted-foreground ml-4">
                          {result.vocabulary_id} | {result.domain_id}
                        </div>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              )}
            </CardContent>
          </Card>

          {/* Filters */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <Filter className="h-4 w-4" />
                Node Filters
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {Object.entries(DOMAIN_COLORS)
                .filter(([k]) => k !== "default")
                .map(([domain, color]) => {
                  const Icon = DOMAIN_ICONS[domain] || Activity;
                  return (
                    <div
                      key={domain}
                      className="flex items-center space-x-2"
                    >
                      <Checkbox
                        id={domain}
                        checked={activeFilters.includes(domain)}
                        onCheckedChange={() => toggleFilter(domain)}
                      />
                      <label
                        htmlFor={domain}
                        className="flex items-center gap-2 text-sm cursor-pointer"
                      >
                        <span style={{ color }}>
                          <Icon className="h-4 w-4" />
                        </span>
                        {domain}
                      </label>
                    </div>
                  );
                })}

              <Separator />

              <div className="space-y-2">
                <Label className="text-xs">Neighbor Depth</Label>
                <Select
                  value={neighborDepth}
                  onValueChange={setNeighborDepth}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="1">1 hop</SelectItem>
                    <SelectItem value="2">2 hops</SelectItem>
                    <SelectItem value="3">3 hops</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>

          {/* Selected Node Details */}
          {selectedNode && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Info className="h-4 w-4" />
                  Selected Concept
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div>
                  <div className="font-medium">{selectedNode.concept_name}</div>
                  <div className="text-xs text-muted-foreground">
                    ID: {selectedNode.concept_id}
                  </div>
                </div>

                <div className="flex flex-wrap gap-1">
                  <Badge
                    style={{
                      backgroundColor:
                        DOMAIN_COLORS[selectedNode.domain_id] ||
                        DOMAIN_COLORS.default,
                    }}
                  >
                    {selectedNode.domain_id}
                  </Badge>
                  <Badge variant="outline">
                    {selectedNode.vocabulary_id}
                  </Badge>
                </div>

                {selectedNode.synonyms && selectedNode.synonyms.length > 0 && (
                  <div>
                    <div className="text-xs font-medium text-muted-foreground mb-1">
                      Synonyms
                    </div>
                    <div className="text-xs">
                      {selectedNode.synonyms.join(", ")}
                    </div>
                  </div>
                )}

                <Button
                  className="w-full"
                  variant="outline"
                  size="sm"
                  onClick={handleExpandNode}
                  disabled={isLoading}
                >
                  {isLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  ) : (
                    <GitBranch className="h-4 w-4 mr-2" />
                  )}
                  Expand Neighbors
                </Button>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Center - Graph Visualization */}
        <div className="col-span-9">
          <Card className="h-[700px]">
            <CardContent className="p-0 h-full">
              {isLoading ? (
                <div className="flex items-center justify-center h-full">
                  <div className="text-center">
                    <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4 text-primary" />
                    <p className="text-muted-foreground">Loading graph data...</p>
                  </div>
                </div>
              ) : nodes.length === 0 ? (
                <div className="flex items-center justify-center h-full">
                  <div className="text-center">
                    <Network className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
                    <h3 className="font-medium mb-2">No Data Loaded</h3>
                    <p className="text-muted-foreground text-sm mb-4">
                      Search for a concept or load sample data to explore the graph
                    </p>
                    <Button onClick={loadMockData}>
                      <RefreshCw className="h-4 w-4 mr-2" />
                      Load Sample Data
                    </Button>
                  </div>
                </div>
              ) : (
                <GraphCanvas
                  nodes={nodes}
                  edges={edges}
                  selectedNode={selectedNode}
                  onNodeClick={handleNodeClick}
                  onNodeHover={setHoveredNode}
                />
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Navigation Cards */}
      <div className="grid grid-cols-3 gap-4">
        <Link href="/analytics/graph/patients">
          <Card className="hover:shadow-md transition-shadow cursor-pointer">
            <CardHeader>
              <CardTitle className="text-sm flex items-center gap-2">
                <Activity className="h-4 w-4" />
                Patient Similarity Network
              </CardTitle>
              <CardDescription>
                Find patients with similar clinical profiles based on shared
                conditions, medications, and procedures.
              </CardDescription>
            </CardHeader>
          </Card>
        </Link>

        <Link href="/analytics/graph/pathways">
          <Card className="hover:shadow-md transition-shadow cursor-pointer">
            <CardHeader>
              <CardTitle className="text-sm flex items-center gap-2">
                <GitBranch className="h-4 w-4" />
                Drug-Disease-Gene Pathways
              </CardTitle>
              <CardDescription>
                Explore multi-layer relationships between drugs, diseases, and
                genes with pathway highlighting.
              </CardDescription>
            </CardHeader>
          </Card>
        </Link>

        <Card className="hover:shadow-md transition-shadow cursor-pointer opacity-60">
          <CardHeader>
            <CardTitle className="text-sm flex items-center gap-2">
              <Server className="h-4 w-4" />
              Graph Statistics
            </CardTitle>
            <CardDescription>
              View overall graph metrics including node counts, relationship
              types, and data quality indicators.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    </div>
  );
}
