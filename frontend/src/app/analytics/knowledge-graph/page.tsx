"use client";

import { useState, useEffect, useRef, useMemo, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Search,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Maximize2,
  Filter,
  Download,
  Box,
  Layers,
  Link2,
  Circle,
  GitBranch,
  Eye,
  EyeOff,
  Play,
  Pause,
} from "lucide-react";

// Types
interface GraphNode {
  id: string;
  label: string;
  type: "concept" | "drug" | "condition" | "procedure" | "measurement" | "person";
  vocabulary?: string;
  conceptCode?: string;
  domain?: string;
  x: number;
  y: number;
  z: number;
  vx: number;
  vy: number;
  vz: number;
  connections: number;
  selected?: boolean;
}

interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  weight: number;
}

interface GraphStats {
  nodeCount: number;
  edgeCount: number;
  avgDegree: number;
  clusters: number;
  density: number;
}

// Mock knowledge graph data
const generateMockGraph = (): { nodes: GraphNode[]; edges: GraphEdge[] } => {
  const nodeTypes: GraphNode["type"][] = ["concept", "drug", "condition", "procedure", "measurement"];
  const vocabularies = ["SNOMED", "ICD10CM", "RxNorm", "LOINC", "CPT4"];

  const concepts = [
    { id: "c1", label: "Type 2 Diabetes Mellitus", type: "condition" as const, vocabulary: "SNOMED", code: "44054006" },
    { id: "c2", label: "Essential Hypertension", type: "condition" as const, vocabulary: "SNOMED", code: "59621000" },
    { id: "c3", label: "Metformin", type: "drug" as const, vocabulary: "RxNorm", code: "6809" },
    { id: "c4", label: "Lisinopril", type: "drug" as const, vocabulary: "RxNorm", code: "29046" },
    { id: "c5", label: "HbA1c Measurement", type: "measurement" as const, vocabulary: "LOINC", code: "4548-4" },
    { id: "c6", label: "Blood Pressure", type: "measurement" as const, vocabulary: "LOINC", code: "55284-4" },
    { id: "c7", label: "Chronic Kidney Disease", type: "condition" as const, vocabulary: "SNOMED", code: "709044004" },
    { id: "c8", label: "Diabetic Nephropathy", type: "condition" as const, vocabulary: "SNOMED", code: "127013003" },
    { id: "c9", label: "SGLT2 Inhibitor", type: "drug" as const, vocabulary: "RxNorm", code: "1545653" },
    { id: "c10", label: "GLP-1 Agonist", type: "drug" as const, vocabulary: "RxNorm", code: "1992689" },
    { id: "c11", label: "Retinopathy", type: "condition" as const, vocabulary: "SNOMED", code: "4855003" },
    { id: "c12", label: "Neuropathy", type: "condition" as const, vocabulary: "SNOMED", code: "386033004" },
    { id: "c13", label: "Fundoscopy", type: "procedure" as const, vocabulary: "CPT4", code: "92002" },
    { id: "c14", label: "eGFR", type: "measurement" as const, vocabulary: "LOINC", code: "33914-3" },
    { id: "c15", label: "Insulin", type: "drug" as const, vocabulary: "RxNorm", code: "5856" },
    { id: "c16", label: "Glucose Level", type: "measurement" as const, vocabulary: "LOINC", code: "2345-7" },
    { id: "c17", label: "Obesity", type: "condition" as const, vocabulary: "SNOMED", code: "414916001" },
    { id: "c18", label: "Dyslipidemia", type: "condition" as const, vocabulary: "SNOMED", code: "370992007" },
    { id: "c19", label: "Atorvastatin", type: "drug" as const, vocabulary: "RxNorm", code: "83367" },
    { id: "c20", label: "LDL Cholesterol", type: "measurement" as const, vocabulary: "LOINC", code: "2089-1" },
    { id: "c21", label: "ACE Inhibitor", type: "drug" as const, vocabulary: "RxNorm", code: "18867" },
    { id: "c22", label: "Coronary Artery Disease", type: "condition" as const, vocabulary: "SNOMED", code: "53741008" },
    { id: "c23", label: "Heart Failure", type: "condition" as const, vocabulary: "SNOMED", code: "84114007" },
    { id: "c24", label: "BNP Level", type: "measurement" as const, vocabulary: "LOINC", code: "30934-4" },
    { id: "c25", label: "Echocardiogram", type: "procedure" as const, vocabulary: "CPT4", code: "93306" },
  ];

  // Initialize nodes with random 3D positions
  const nodes: GraphNode[] = concepts.map((c) => ({
    id: c.id,
    label: c.label,
    type: c.type,
    vocabulary: c.vocabulary,
    conceptCode: c.code,
    domain: c.type,
    x: (Math.random() - 0.5) * 500,
    y: (Math.random() - 0.5) * 500,
    z: (Math.random() - 0.5) * 200,
    vx: 0,
    vy: 0,
    vz: 0,
    connections: 0,
  }));

  // Create edges based on clinical relationships
  const edges: GraphEdge[] = [
    // Diabetes relationships
    { id: "e1", source: "c1", target: "c3", type: "treated_by", weight: 1.0 },
    { id: "e2", source: "c1", target: "c9", type: "treated_by", weight: 0.8 },
    { id: "e3", source: "c1", target: "c10", type: "treated_by", weight: 0.7 },
    { id: "e4", source: "c1", target: "c15", type: "treated_by", weight: 0.9 },
    { id: "e5", source: "c1", target: "c5", type: "monitored_by", weight: 1.0 },
    { id: "e6", source: "c1", target: "c16", type: "monitored_by", weight: 1.0 },
    { id: "e7", source: "c1", target: "c8", type: "complication_of", weight: 0.6 },
    { id: "e8", source: "c1", target: "c11", type: "complication_of", weight: 0.5 },
    { id: "e9", source: "c1", target: "c12", type: "complication_of", weight: 0.5 },

    // Hypertension relationships
    { id: "e10", source: "c2", target: "c4", type: "treated_by", weight: 0.9 },
    { id: "e11", source: "c2", target: "c21", type: "treated_by", weight: 0.85 },
    { id: "e12", source: "c2", target: "c6", type: "monitored_by", weight: 1.0 },
    { id: "e13", source: "c2", target: "c7", type: "complication_of", weight: 0.4 },
    { id: "e14", source: "c2", target: "c22", type: "associated_with", weight: 0.7 },

    // CKD relationships
    { id: "e15", source: "c7", target: "c14", type: "monitored_by", weight: 1.0 },
    { id: "e16", source: "c7", target: "c8", type: "subtype_of", weight: 0.8 },
    { id: "e17", source: "c7", target: "c21", type: "treated_by", weight: 0.7 },
    { id: "e18", source: "c8", target: "c1", type: "caused_by", weight: 0.9 },

    // Cardiovascular relationships
    { id: "e19", source: "c22", target: "c23", type: "progression_to", weight: 0.6 },
    { id: "e20", source: "c23", target: "c24", type: "monitored_by", weight: 1.0 },
    { id: "e21", source: "c23", target: "c25", type: "diagnosed_by", weight: 0.9 },
    { id: "e22", source: "c22", target: "c19", type: "treated_by", weight: 0.8 },

    // Lipid relationships
    { id: "e23", source: "c18", target: "c19", type: "treated_by", weight: 0.9 },
    { id: "e24", source: "c18", target: "c20", type: "monitored_by", weight: 1.0 },
    { id: "e25", source: "c18", target: "c22", type: "associated_with", weight: 0.7 },

    // Obesity relationships
    { id: "e26", source: "c17", target: "c1", type: "risk_factor_for", weight: 0.8 },
    { id: "e27", source: "c17", target: "c2", type: "risk_factor_for", weight: 0.7 },
    { id: "e28", source: "c17", target: "c10", type: "treated_by", weight: 0.6 },

    // Cross-disease relationships
    { id: "e29", source: "c1", target: "c2", type: "comorbid_with", weight: 0.8 },
    { id: "e30", source: "c1", target: "c17", type: "comorbid_with", weight: 0.7 },
    { id: "e31", source: "c1", target: "c18", type: "comorbid_with", weight: 0.6 },

    // Eye examination
    { id: "e32", source: "c11", target: "c13", type: "diagnosed_by", weight: 0.9 },
  ];

  // Count connections
  edges.forEach((edge) => {
    const sourceNode = nodes.find((n) => n.id === edge.source);
    const targetNode = nodes.find((n) => n.id === edge.target);
    if (sourceNode) sourceNode.connections++;
    if (targetNode) targetNode.connections++;
  });

  return { nodes, edges };
};

const nodeColors: Record<string, string> = {
  condition: "#ef4444",
  drug: "#22c55e",
  measurement: "#3b82f6",
  procedure: "#f59e0b",
  concept: "#8b5cf6",
  person: "#06b6d4",
};

const edgeTypeColors: Record<string, string> = {
  treated_by: "#22c55e",
  monitored_by: "#3b82f6",
  complication_of: "#ef4444",
  associated_with: "#8b5cf6",
  risk_factor_for: "#f59e0b",
  comorbid_with: "#06b6d4",
  subtype_of: "#64748b",
  caused_by: "#dc2626",
  progression_to: "#ea580c",
  diagnosed_by: "#0ea5e9",
};

export default function KnowledgeGraphPage() {
  const { nodes: initialNodes, edges } = useMemo(() => generateMockGraph(), []);
  const [nodes, setNodes] = useState<GraphNode[]>(initialNodes);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [visibleTypes, setVisibleTypes] = useState<Set<string>>(
    new Set(["condition", "drug", "measurement", "procedure"])
  );
  const [showLabels, setShowLabels] = useState(true);
  const [simulationRunning, setSimulationRunning] = useState(true);
  const [linkStrength, setLinkStrength] = useState([0.3]);
  const [chargeStrength, setChargeStrength] = useState([-100]);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number | null>(null);
  const isDragging = useRef(false);
  const dragStart = useRef({ x: 0, y: 0 });

  // Force simulation
  useEffect(() => {
    if (!simulationRunning) return;

    const simulate = () => {
      setNodes((prevNodes) => {
        const newNodes = prevNodes.map((node) => ({ ...node }));

        // Apply forces
        newNodes.forEach((node, i) => {
          if (!visibleTypes.has(node.type)) return;

          // Repulsion between nodes
          newNodes.forEach((other, j) => {
            if (i === j || !visibleTypes.has(other.type)) return;
            const dx = node.x - other.x;
            const dy = node.y - other.y;
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;
            const force = (chargeStrength[0] / dist) * 0.1;
            node.vx += (dx / dist) * force;
            node.vy += (dy / dist) * force;
          });

          // Attraction along edges
          edges.forEach((edge) => {
            if (edge.source === node.id || edge.target === node.id) {
              const otherId = edge.source === node.id ? edge.target : edge.source;
              const other = newNodes.find((n) => n.id === otherId);
              if (!other || !visibleTypes.has(other.type)) return;

              const dx = other.x - node.x;
              const dy = other.y - node.y;
              const dist = Math.sqrt(dx * dx + dy * dy) || 1;
              node.vx += dx * linkStrength[0] * 0.01;
              node.vy += dy * linkStrength[0] * 0.01;
            }
          });

          // Center gravity
          node.vx -= node.x * 0.001;
          node.vy -= node.y * 0.001;

          // Damping
          node.vx *= 0.9;
          node.vy *= 0.9;

          // Update position
          node.x += node.vx;
          node.y += node.vy;
        });

        return newNodes;
      });

      animationRef.current = requestAnimationFrame(simulate);
    };

    animationRef.current = requestAnimationFrame(simulate);
    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [simulationRunning, edges, visibleTypes, linkStrength, chargeStrength]);

  // Canvas rendering
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const render = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.save();
      ctx.translate(canvas.width / 2 + pan.x, canvas.height / 2 + pan.y);
      ctx.scale(zoom, zoom);

      // Draw edges
      edges.forEach((edge) => {
        const source = nodes.find((n) => n.id === edge.source);
        const target = nodes.find((n) => n.id === edge.target);
        if (!source || !target) return;
        if (!visibleTypes.has(source.type) || !visibleTypes.has(target.type)) return;

        ctx.beginPath();
        ctx.moveTo(source.x, source.y);
        ctx.lineTo(target.x, target.y);
        ctx.strokeStyle = edgeTypeColors[edge.type] || "#94a3b8";
        ctx.globalAlpha = selectedNode
          ? source.id === selectedNode.id || target.id === selectedNode.id
            ? 0.8
            : 0.1
          : 0.3;
        ctx.lineWidth = edge.weight * 2;
        ctx.stroke();
      });

      ctx.globalAlpha = 1;

      // Draw nodes
      nodes.forEach((node) => {
        if (!visibleTypes.has(node.type)) return;

        const isHighlighted =
          !selectedNode ||
          node.id === selectedNode.id ||
          edges.some(
            (e) =>
              (e.source === selectedNode.id && e.target === node.id) ||
              (e.target === selectedNode.id && e.source === node.id)
          );

        const radius = 8 + Math.sqrt(node.connections) * 3;

        // Node circle
        ctx.beginPath();
        ctx.arc(node.x, node.y, radius, 0, Math.PI * 2);
        ctx.fillStyle = nodeColors[node.type] || "#64748b";
        ctx.globalAlpha = isHighlighted ? 1 : 0.2;
        ctx.fill();

        // Selection ring
        if (node.id === selectedNode?.id) {
          ctx.beginPath();
          ctx.arc(node.x, node.y, radius + 4, 0, Math.PI * 2);
          ctx.strokeStyle = "#000";
          ctx.lineWidth = 2;
          ctx.stroke();
        }

        // Label
        if (showLabels && isHighlighted) {
          ctx.font = "11px sans-serif";
          ctx.fillStyle = "#1f2937";
          ctx.textAlign = "center";
          ctx.globalAlpha = 1;
          ctx.fillText(node.label, node.x, node.y + radius + 14);
        }
      });

      ctx.restore();
      requestAnimationFrame(render);
    };

    render();
  }, [nodes, edges, zoom, pan, selectedNode, visibleTypes, showLabels]);

  // Mouse handlers
  const handleCanvasClick = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const canvas = canvasRef.current;
      if (!canvas) return;

      const rect = canvas.getBoundingClientRect();
      const x = (e.clientX - rect.left - canvas.width / 2 - pan.x) / zoom;
      const y = (e.clientY - rect.top - canvas.height / 2 - pan.y) / zoom;

      // Find clicked node
      const clickedNode = nodes.find((node) => {
        if (!visibleTypes.has(node.type)) return false;
        const radius = 8 + Math.sqrt(node.connections) * 3;
        const dx = node.x - x;
        const dy = node.y - y;
        return Math.sqrt(dx * dx + dy * dy) < radius;
      });

      setSelectedNode(clickedNode || null);
    },
    [nodes, zoom, pan, visibleTypes]
  );

  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    isDragging.current = true;
    dragStart.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDragging.current) return;
    setPan({
      x: e.clientX - dragStart.current.x,
      y: e.clientY - dragStart.current.y,
    });
  };

  const handleMouseUp = () => {
    isDragging.current = false;
  };

  const handleWheel = (e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setZoom((z) => Math.min(Math.max(z * delta, 0.1), 5));
  };

  const toggleType = (type: string) => {
    setVisibleTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) {
        next.delete(type);
      } else {
        next.add(type);
      }
      return next;
    });
  };

  const filteredNodes = nodes.filter(
    (n) =>
      visibleTypes.has(n.type) &&
      (searchQuery === "" || n.label.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const stats: GraphStats = {
    nodeCount: filteredNodes.length,
    edgeCount: edges.filter(
      (e) =>
        filteredNodes.some((n) => n.id === e.source) &&
        filteredNodes.some((n) => n.id === e.target)
    ).length,
    avgDegree:
      filteredNodes.length > 0
        ? filteredNodes.reduce((sum, n) => sum + n.connections, 0) / filteredNodes.length
        : 0,
    clusters: 4,
    density: 0.12,
  };

  const connectedNodes = selectedNode
    ? edges
        .filter((e) => e.source === selectedNode.id || e.target === selectedNode.id)
        .map((e) => {
          const otherId = e.source === selectedNode.id ? e.target : e.source;
          const other = nodes.find((n) => n.id === otherId);
          return { node: other, edge: e };
        })
        .filter((item) => item.node)
    : [];

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Knowledge Graph Explorer</h1>
          <p className="text-muted-foreground">
            Interactive visualization of clinical ontology relationships
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline">
            <Download className="h-4 w-4 mr-2" />
            Export
          </Button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-5 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Circle className="h-5 w-5 text-blue-500" />
              <div>
                <p className="text-sm text-muted-foreground">Nodes</p>
                <p className="text-2xl font-bold">{stats.nodeCount}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Link2 className="h-5 w-5 text-green-500" />
              <div>
                <p className="text-sm text-muted-foreground">Edges</p>
                <p className="text-2xl font-bold">{stats.edgeCount}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <GitBranch className="h-5 w-5 text-orange-500" />
              <div>
                <p className="text-sm text-muted-foreground">Avg Degree</p>
                <p className="text-2xl font-bold">{stats.avgDegree.toFixed(1)}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Layers className="h-5 w-5 text-purple-500" />
              <div>
                <p className="text-sm text-muted-foreground">Clusters</p>
                <p className="text-2xl font-bold">{stats.clusters}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Box className="h-5 w-5 text-cyan-500" />
              <div>
                <p className="text-sm text-muted-foreground">Density</p>
                <p className="text-2xl font-bold">{stats.density.toFixed(2)}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-4 gap-6">
        {/* Controls Panel */}
        <Card className="col-span-1">
          <CardHeader>
            <CardTitle className="text-lg">Controls</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Search */}
            <div className="space-y-2">
              <Label>Search Nodes</Label>
              <div className="relative">
                <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search concepts..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-8"
                />
              </div>
            </div>

            {/* Node Type Filters */}
            <div className="space-y-2">
              <Label>Node Types</Label>
              <div className="space-y-2">
                {Object.entries(nodeColors).map(([type, color]) => (
                  <label key={type} className="flex items-center gap-2 cursor-pointer">
                    <Switch
                      checked={visibleTypes.has(type)}
                      onCheckedChange={() => toggleType(type)}
                    />
                    <div className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
                    <span className="text-sm capitalize">{type}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Simulation Controls */}
            <div className="space-y-2">
              <Label>Simulation</Label>
              <div className="flex gap-2">
                <Button
                  variant={simulationRunning ? "default" : "outline"}
                  size="sm"
                  onClick={() => setSimulationRunning(!simulationRunning)}
                >
                  {simulationRunning ? (
                    <>
                      <Pause className="h-4 w-4 mr-1" /> Pause
                    </>
                  ) : (
                    <>
                      <Play className="h-4 w-4 mr-1" /> Play
                    </>
                  )}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setZoom(1);
                    setPan({ x: 0, y: 0 });
                  }}
                >
                  <RotateCcw className="h-4 w-4 mr-1" /> Reset
                </Button>
              </div>
            </div>

            {/* Force Parameters */}
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>Link Strength: {linkStrength[0].toFixed(2)}</Label>
                <Slider
                  value={linkStrength}
                  onValueChange={setLinkStrength}
                  min={0}
                  max={1}
                  step={0.05}
                />
              </div>
              <div className="space-y-2">
                <Label>Repulsion: {chargeStrength[0]}</Label>
                <Slider
                  value={chargeStrength}
                  onValueChange={setChargeStrength}
                  min={-300}
                  max={0}
                  step={10}
                />
              </div>
            </div>

            {/* Display Options */}
            <div className="space-y-2">
              <label className="flex items-center gap-2">
                <Switch checked={showLabels} onCheckedChange={setShowLabels} />
                <span className="text-sm">Show Labels</span>
              </label>
            </div>

            {/* Zoom Controls */}
            <div className="space-y-2">
              <Label>Zoom: {(zoom * 100).toFixed(0)}%</Label>
              <div className="flex gap-2">
                <Button variant="outline" size="icon" onClick={() => setZoom((z) => z * 1.2)}>
                  <ZoomIn className="h-4 w-4" />
                </Button>
                <Button variant="outline" size="icon" onClick={() => setZoom((z) => z / 1.2)}>
                  <ZoomOut className="h-4 w-4" />
                </Button>
                <Button variant="outline" size="icon" onClick={() => setZoom(1)}>
                  <Maximize2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Graph Canvas */}
        <Card className="col-span-3">
          <CardHeader className="pb-2">
            <div className="flex justify-between items-center">
              <CardTitle>Graph Visualization</CardTitle>
              {selectedNode && (
                <Badge variant="outline">
                  Selected: {selectedNode.label}
                  <button
                    className="ml-2 hover:text-red-500"
                    onClick={() => setSelectedNode(null)}
                  >
                    ×
                  </button>
                </Badge>
              )}
            </div>
          </CardHeader>
          <CardContent>
            <canvas
              ref={canvasRef}
              width={800}
              height={500}
              className="border rounded-lg bg-slate-50 cursor-grab active:cursor-grabbing"
              onClick={handleCanvasClick}
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
              onMouseLeave={handleMouseUp}
              onWheel={handleWheel}
            />

            {/* Legend */}
            <div className="flex flex-wrap gap-4 mt-4">
              <div className="text-sm font-medium">Edge Types:</div>
              {Object.entries(edgeTypeColors).map(([type, color]) => (
                <div key={type} className="flex items-center gap-1 text-xs">
                  <div className="w-4 h-1 rounded" style={{ backgroundColor: color }} />
                  <span>{type.replace(/_/g, " ")}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Node Details */}
      {selectedNode && (
        <Card>
          <CardHeader>
            <CardTitle>
              {selectedNode.label}
              <Badge className="ml-2" style={{ backgroundColor: nodeColors[selectedNode.type] }}>
                {selectedNode.type}
              </Badge>
            </CardTitle>
            <CardDescription>
              {selectedNode.vocabulary} - {selectedNode.conceptCode}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <h4 className="font-medium mb-2">Connected Concepts ({connectedNodes.length})</h4>
            <ScrollArea className="h-[200px]">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Concept</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Relationship</TableHead>
                    <TableHead>Strength</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {connectedNodes.map(({ node, edge }) => (
                    <TableRow
                      key={edge.id}
                      className="cursor-pointer hover:bg-slate-50"
                      onClick={() => setSelectedNode(node!)}
                    >
                      <TableCell className="font-medium">{node?.label}</TableCell>
                      <TableCell>
                        <Badge
                          variant="outline"
                          style={{ borderColor: nodeColors[node?.type || "concept"] }}
                        >
                          {node?.type}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant="secondary"
                          style={{ backgroundColor: edgeTypeColors[edge.type] + "30" }}
                        >
                          {edge.type.replace(/_/g, " ")}
                        </Badge>
                      </TableCell>
                      <TableCell>{(edge.weight * 100).toFixed(0)}%</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </ScrollArea>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
