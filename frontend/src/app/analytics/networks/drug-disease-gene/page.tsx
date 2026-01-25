"use client";

import { useState, useEffect, useRef, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
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
  Filter,
  Download,
  ExternalLink,
  Pill,
  Bug,
  Dna,
  Layers,
  Target,
  Link2,
  BookOpen,
} from "lucide-react";

// Types
interface NetworkNode {
  id: string;
  label: string;
  type: "drug" | "disease" | "gene" | "pathway";
  x: number;
  y: number;
  vx: number;
  vy: number;
  description?: string;
  externalId?: string;
  metadata?: Record<string, string | number>;
}

interface NetworkEdge {
  id: string;
  source: string;
  target: string;
  type: "treats" | "causes" | "associated" | "targets" | "regulates" | "inhibits" | "activates";
  confidence: number;
  evidence?: string[];
  pubmedIds?: string[];
}

interface LiteratureReference {
  pmid: string;
  title: string;
  journal: string;
  year: number;
  doi?: string;
}

// Mock network data
const mockNodes: NetworkNode[] = [
  // Drugs
  { id: "drug-1", label: "Metformin", type: "drug", x: 0, y: 0, vx: 0, vy: 0, externalId: "DB00331", description: "Biguanide antidiabetic agent" },
  { id: "drug-2", label: "Empagliflozin", type: "drug", x: 0, y: 0, vx: 0, vy: 0, externalId: "DB09038", description: "SGLT2 inhibitor" },
  { id: "drug-3", label: "Lisinopril", type: "drug", x: 0, y: 0, vx: 0, vy: 0, externalId: "DB00722", description: "ACE inhibitor" },
  { id: "drug-4", label: "Semaglutide", type: "drug", x: 0, y: 0, vx: 0, vy: 0, externalId: "DB13928", description: "GLP-1 receptor agonist" },
  { id: "drug-5", label: "Atorvastatin", type: "drug", x: 0, y: 0, vx: 0, vy: 0, externalId: "DB01076", description: "HMG-CoA reductase inhibitor" },

  // Diseases
  { id: "disease-1", label: "Type 2 Diabetes", type: "disease", x: 0, y: 0, vx: 0, vy: 0, externalId: "DOID:9352", description: "Metabolic disorder" },
  { id: "disease-2", label: "Hypertension", type: "disease", x: 0, y: 0, vx: 0, vy: 0, externalId: "DOID:10763", description: "Cardiovascular disease" },
  { id: "disease-3", label: "CKD", type: "disease", x: 0, y: 0, vx: 0, vy: 0, externalId: "DOID:784", description: "Chronic kidney disease" },
  { id: "disease-4", label: "Heart Failure", type: "disease", x: 0, y: 0, vx: 0, vy: 0, externalId: "DOID:6000", description: "Cardiac insufficiency" },
  { id: "disease-5", label: "Dyslipidemia", type: "disease", x: 0, y: 0, vx: 0, vy: 0, externalId: "DOID:1168", description: "Lipid metabolism disorder" },
  { id: "disease-6", label: "Obesity", type: "disease", x: 0, y: 0, vx: 0, vy: 0, externalId: "DOID:9970", description: "Metabolic disorder" },

  // Genes
  { id: "gene-1", label: "AMPK", type: "gene", x: 0, y: 0, vx: 0, vy: 0, externalId: "HGNC:386", description: "AMP-activated protein kinase" },
  { id: "gene-2", label: "SGLT2", type: "gene", x: 0, y: 0, vx: 0, vy: 0, externalId: "HGNC:11036", description: "Sodium-glucose cotransporter 2" },
  { id: "gene-3", label: "ACE", type: "gene", x: 0, y: 0, vx: 0, vy: 0, externalId: "HGNC:2707", description: "Angiotensin-converting enzyme" },
  { id: "gene-4", label: "GLP1R", type: "gene", x: 0, y: 0, vx: 0, vy: 0, externalId: "HGNC:4324", description: "GLP-1 receptor" },
  { id: "gene-5", label: "HMGCR", type: "gene", x: 0, y: 0, vx: 0, vy: 0, externalId: "HGNC:5006", description: "HMG-CoA reductase" },
  { id: "gene-6", label: "INS", type: "gene", x: 0, y: 0, vx: 0, vy: 0, externalId: "HGNC:6081", description: "Insulin" },
  { id: "gene-7", label: "PPARG", type: "gene", x: 0, y: 0, vx: 0, vy: 0, externalId: "HGNC:9236", description: "Peroxisome proliferator-activated receptor gamma" },
  { id: "gene-8", label: "RAAS", type: "gene", x: 0, y: 0, vx: 0, vy: 0, externalId: "HGNC:9958", description: "Renin-angiotensin-aldosterone system" },

  // Pathways
  { id: "pathway-1", label: "Insulin Signaling", type: "pathway", x: 0, y: 0, vx: 0, vy: 0, externalId: "KEGG:hsa04910", description: "Insulin signal transduction" },
  { id: "pathway-2", label: "Glucose Metabolism", type: "pathway", x: 0, y: 0, vx: 0, vy: 0, externalId: "KEGG:hsa00010", description: "Glycolysis/Gluconeogenesis" },
  { id: "pathway-3", label: "Lipid Metabolism", type: "pathway", x: 0, y: 0, vx: 0, vy: 0, externalId: "KEGG:hsa00061", description: "Fatty acid biosynthesis" },
];

const mockEdges: NetworkEdge[] = [
  // Drug-Gene interactions (targets)
  { id: "e1", source: "drug-1", target: "gene-1", type: "targets", confidence: 0.95, pubmedIds: ["28245765", "31965140"] },
  { id: "e2", source: "drug-2", target: "gene-2", type: "inhibits", confidence: 0.98, pubmedIds: ["25794345"] },
  { id: "e3", source: "drug-3", target: "gene-3", type: "inhibits", confidence: 0.99, pubmedIds: ["12364326"] },
  { id: "e4", source: "drug-4", target: "gene-4", type: "activates", confidence: 0.97, pubmedIds: ["33567185"] },
  { id: "e5", source: "drug-5", target: "gene-5", type: "inhibits", confidence: 0.99, pubmedIds: ["10196273"] },

  // Drug-Disease interactions (treats)
  { id: "e6", source: "drug-1", target: "disease-1", type: "treats", confidence: 0.95, pubmedIds: ["28245765"] },
  { id: "e7", source: "drug-2", target: "disease-1", type: "treats", confidence: 0.90, pubmedIds: ["25794345"] },
  { id: "e8", source: "drug-2", target: "disease-3", type: "treats", confidence: 0.85, pubmedIds: ["30990260"] },
  { id: "e9", source: "drug-2", target: "disease-4", type: "treats", confidence: 0.88, pubmedIds: ["31535829"] },
  { id: "e10", source: "drug-3", target: "disease-2", type: "treats", confidence: 0.93, pubmedIds: ["12364326"] },
  { id: "e11", source: "drug-3", target: "disease-3", type: "treats", confidence: 0.82, pubmedIds: ["29678534"] },
  { id: "e12", source: "drug-4", target: "disease-1", type: "treats", confidence: 0.92, pubmedIds: ["33567185"] },
  { id: "e13", source: "drug-4", target: "disease-6", type: "treats", confidence: 0.89, pubmedIds: ["34170647"] },
  { id: "e14", source: "drug-5", target: "disease-5", type: "treats", confidence: 0.94, pubmedIds: ["10196273"] },

  // Gene-Disease associations
  { id: "e15", source: "gene-1", target: "disease-1", type: "associated", confidence: 0.85, pubmedIds: ["28245765"] },
  { id: "e16", source: "gene-2", target: "disease-1", type: "associated", confidence: 0.78, pubmedIds: ["25794345"] },
  { id: "e17", source: "gene-3", target: "disease-2", type: "associated", confidence: 0.92, pubmedIds: ["12364326"] },
  { id: "e18", source: "gene-6", target: "disease-1", type: "associated", confidence: 0.95, pubmedIds: ["18421287"] },
  { id: "e19", source: "gene-7", target: "disease-1", type: "associated", confidence: 0.80, pubmedIds: ["15314609"] },
  { id: "e20", source: "gene-8", target: "disease-2", type: "regulates", confidence: 0.88, pubmedIds: ["27716549"] },

  // Gene-Pathway interactions
  { id: "e21", source: "gene-1", target: "pathway-2", type: "regulates", confidence: 0.90 },
  { id: "e22", source: "gene-6", target: "pathway-1", type: "regulates", confidence: 0.95 },
  { id: "e23", source: "gene-7", target: "pathway-3", type: "regulates", confidence: 0.85 },
  { id: "e24", source: "gene-5", target: "pathway-3", type: "regulates", confidence: 0.92 },

  // Disease-Disease comorbidities
  { id: "e25", source: "disease-1", target: "disease-2", type: "associated", confidence: 0.75 },
  { id: "e26", source: "disease-1", target: "disease-3", type: "causes", confidence: 0.65 },
  { id: "e27", source: "disease-1", target: "disease-5", type: "associated", confidence: 0.70 },
  { id: "e28", source: "disease-2", target: "disease-4", type: "causes", confidence: 0.60 },
  { id: "e29", source: "disease-6", target: "disease-1", type: "causes", confidence: 0.72 },
];

const mockReferences: LiteratureReference[] = [
  { pmid: "28245765", title: "Metformin: An Update on Mechanisms of Action and Therapeutic Uses", journal: "J Clin Invest", year: 2017 },
  { pmid: "25794345", title: "Empagliflozin and Cardiovascular Outcomes in Type 2 Diabetes", journal: "N Engl J Med", year: 2015 },
  { pmid: "33567185", title: "Semaglutide Effects on Cardiovascular Outcomes in Diabetes", journal: "NEJM", year: 2021 },
  { pmid: "30990260", title: "Dapagliflozin and Kidney Disease Progression", journal: "N Engl J Med", year: 2019 },
  { pmid: "31535829", title: "SGLT2 Inhibitors in Heart Failure", journal: "Circulation", year: 2019 },
];

const nodeColors: Record<string, string> = {
  drug: "#22c55e",
  disease: "#ef4444",
  gene: "#3b82f6",
  pathway: "#f59e0b",
};

const edgeTypeColors: Record<string, string> = {
  treats: "#22c55e",
  causes: "#ef4444",
  associated: "#8b5cf6",
  targets: "#06b6d4",
  regulates: "#f59e0b",
  inhibits: "#dc2626",
  activates: "#16a34a",
};

export default function DrugDiseaseGenePage() {
  const [nodes, setNodes] = useState<NetworkNode[]>(() => {
    // Initialize random positions
    return mockNodes.map((node) => ({
      ...node,
      x: (Math.random() - 0.5) * 600,
      y: (Math.random() - 0.5) * 400,
    }));
  });
  const [edges] = useState<NetworkEdge[]>(mockEdges);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedNode, setSelectedNode] = useState<NetworkNode | null>(null);
  const [highlightedPath, setHighlightedPath] = useState<Set<string>>(new Set());
  const [visibleLayers, setVisibleLayers] = useState<Set<string>>(
    new Set(["drug", "disease", "gene", "pathway"])
  );
  const [showLabels, setShowLabels] = useState(true);
  const [minConfidence, setMinConfidence] = useState(0.5);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Force simulation
  useEffect(() => {
    const simulate = () => {
      setNodes((prevNodes) => {
        const newNodes = prevNodes.map((node) => ({ ...node }));

        newNodes.forEach((node, i) => {
          if (!visibleLayers.has(node.type)) return;

          // Repulsion
          newNodes.forEach((other, j) => {
            if (i === j || !visibleLayers.has(other.type)) return;
            const dx = node.x - other.x;
            const dy = node.y - other.y;
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;
            const force = -150 / dist;
            node.vx += (dx / dist) * force * 0.1;
            node.vy += (dy / dist) * force * 0.1;
          });

          // Attraction along edges
          edges.forEach((edge) => {
            if (edge.confidence < minConfidence) return;
            if (edge.source === node.id || edge.target === node.id) {
              const otherId = edge.source === node.id ? edge.target : edge.source;
              const other = newNodes.find((n) => n.id === otherId);
              if (!other || !visibleLayers.has(other.type)) return;

              const dx = other.x - node.x;
              const dy = other.y - node.y;
              node.vx += dx * 0.003;
              node.vy += dy * 0.003;
            }
          });

          // Center gravity
          node.vx -= node.x * 0.001;
          node.vy -= node.y * 0.001;

          // Damping and update
          node.vx *= 0.9;
          node.vy *= 0.9;
          node.x += node.vx;
          node.y += node.vy;
        });

        return newNodes;
      });

      requestAnimationFrame(simulate);
    };

    const animationId = requestAnimationFrame(simulate);
    return () => cancelAnimationFrame(animationId);
  }, [edges, visibleLayers, minConfidence]);

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

      const filteredEdges = edges.filter((e) => e.confidence >= minConfidence);

      // Draw edges
      filteredEdges.forEach((edge) => {
        const source = nodes.find((n) => n.id === edge.source);
        const target = nodes.find((n) => n.id === edge.target);
        if (!source || !target) return;
        if (!visibleLayers.has(source.type) || !visibleLayers.has(target.type)) return;

        const isHighlighted = highlightedPath.has(edge.id);

        ctx.beginPath();
        ctx.moveTo(source.x, source.y);
        ctx.lineTo(target.x, target.y);
        ctx.strokeStyle = edgeTypeColors[edge.type] || "#94a3b8";
        ctx.globalAlpha = isHighlighted || highlightedPath.size === 0 ? 0.6 : 0.1;
        ctx.lineWidth = edge.confidence * 3;
        ctx.stroke();

        // Draw arrow
        const angle = Math.atan2(target.y - source.y, target.x - source.x);
        const midX = (source.x + target.x) / 2;
        const midY = (source.y + target.y) / 2;
        ctx.save();
        ctx.translate(midX, midY);
        ctx.rotate(angle);
        ctx.beginPath();
        ctx.moveTo(5, 0);
        ctx.lineTo(-5, -4);
        ctx.lineTo(-5, 4);
        ctx.closePath();
        ctx.fillStyle = edgeTypeColors[edge.type] || "#94a3b8";
        ctx.fill();
        ctx.restore();
      });

      ctx.globalAlpha = 1;

      // Draw nodes
      nodes.forEach((node) => {
        if (!visibleLayers.has(node.type)) return;

        const matchesSearch =
          searchQuery === "" || node.label.toLowerCase().includes(searchQuery.toLowerCase());

        const isHighlighted =
          highlightedPath.size === 0 ||
          highlightedPath.has(node.id) ||
          edges.some(
            (e) =>
              highlightedPath.has(e.id) && (e.source === node.id || e.target === node.id)
          );

        const radius = node.type === "pathway" ? 15 : 12;

        ctx.globalAlpha = matchesSearch && isHighlighted ? 1 : 0.2;

        // Node shape based on type
        ctx.beginPath();
        if (node.type === "pathway") {
          // Hexagon for pathways
          for (let i = 0; i < 6; i++) {
            const angle = (Math.PI / 3) * i - Math.PI / 2;
            const x = node.x + radius * Math.cos(angle);
            const y = node.y + radius * Math.sin(angle);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          }
          ctx.closePath();
        } else if (node.type === "gene") {
          // Diamond for genes
          ctx.moveTo(node.x, node.y - radius);
          ctx.lineTo(node.x + radius, node.y);
          ctx.lineTo(node.x, node.y + radius);
          ctx.lineTo(node.x - radius, node.y);
          ctx.closePath();
        } else {
          // Circle for drugs and diseases
          ctx.arc(node.x, node.y, radius, 0, Math.PI * 2);
        }

        ctx.fillStyle = nodeColors[node.type];
        ctx.fill();

        // Selection ring
        if (node.id === selectedNode?.id) {
          ctx.strokeStyle = "#000";
          ctx.lineWidth = 3;
          ctx.stroke();
        }

        // Label
        if (showLabels && matchesSearch) {
          ctx.font = "10px sans-serif";
          ctx.fillStyle = "#1f2937";
          ctx.textAlign = "center";
          ctx.globalAlpha = 1;
          ctx.fillText(node.label, node.x, node.y + radius + 12);
        }
      });

      ctx.restore();
      requestAnimationFrame(render);
    };

    render();
  }, [nodes, edges, zoom, pan, selectedNode, highlightedPath, visibleLayers, showLabels, searchQuery, minConfidence]);

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left - canvas.width / 2 - pan.x) / zoom;
    const y = (e.clientY - rect.top - canvas.height / 2 - pan.y) / zoom;

    const clickedNode = nodes.find((node) => {
      if (!visibleLayers.has(node.type)) return false;
      const radius = node.type === "pathway" ? 15 : 12;
      const dx = node.x - x;
      const dy = node.y - y;
      return Math.sqrt(dx * dx + dy * dy) < radius;
    });

    if (clickedNode) {
      setSelectedNode(clickedNode);
      // Highlight connected path
      const connectedEdges = new Set<string>();
      const connectedNodes = new Set<string>([clickedNode.id]);
      edges.forEach((e) => {
        if (e.source === clickedNode.id || e.target === clickedNode.id) {
          connectedEdges.add(e.id);
          connectedNodes.add(e.source);
          connectedNodes.add(e.target);
        }
      });
      setHighlightedPath(new Set([...connectedEdges, ...connectedNodes]));
    } else {
      setSelectedNode(null);
      setHighlightedPath(new Set());
    }
  };

  const toggleLayer = (layer: string) => {
    setVisibleLayers((prev) => {
      const next = new Set(prev);
      if (next.has(layer)) next.delete(layer);
      else next.add(layer);
      return next;
    });
  };

  const getConnectedEdges = (node: NetworkNode) => {
    return edges
      .filter((e) => e.source === node.id || e.target === node.id)
      .filter((e) => e.confidence >= minConfidence);
  };

  const getNodeIcon = (type: string) => {
    switch (type) {
      case "drug":
        return <Pill className="h-4 w-4" />;
      case "disease":
        return <Bug className="h-4 w-4" />;
      case "gene":
        return <Dna className="h-4 w-4" />;
      case "pathway":
        return <Target className="h-4 w-4" />;
      default:
        return null;
    }
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Drug-Disease-Gene Network</h1>
          <p className="text-muted-foreground">
            Multi-layer network visualization with pathway highlighting
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
              <Pill className="h-5 w-5 text-green-500" />
              <div>
                <p className="text-sm text-muted-foreground">Drugs</p>
                <p className="text-2xl font-bold">{nodes.filter((n) => n.type === "drug").length}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Bug className="h-5 w-5 text-red-500" />
              <div>
                <p className="text-sm text-muted-foreground">Diseases</p>
                <p className="text-2xl font-bold">{nodes.filter((n) => n.type === "disease").length}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Dna className="h-5 w-5 text-blue-500" />
              <div>
                <p className="text-sm text-muted-foreground">Genes</p>
                <p className="text-2xl font-bold">{nodes.filter((n) => n.type === "gene").length}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Target className="h-5 w-5 text-orange-500" />
              <div>
                <p className="text-sm text-muted-foreground">Pathways</p>
                <p className="text-2xl font-bold">{nodes.filter((n) => n.type === "pathway").length}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Link2 className="h-5 w-5 text-purple-500" />
              <div>
                <p className="text-sm text-muted-foreground">Interactions</p>
                <p className="text-2xl font-bold">{edges.filter((e) => e.confidence >= minConfidence).length}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-4 gap-6">
        {/* Controls */}
        <Card className="col-span-1">
          <CardHeader>
            <CardTitle className="text-lg">Controls</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Search */}
            <div className="space-y-2">
              <Label>Search</Label>
              <div className="relative">
                <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search nodes..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-8"
                />
              </div>
            </div>

            {/* Layer Toggles */}
            <div className="space-y-2">
              <Label>Visible Layers</Label>
              <div className="space-y-2">
                {Object.entries(nodeColors).map(([type, color]) => (
                  <label key={type} className="flex items-center gap-2 cursor-pointer">
                    <Switch
                      checked={visibleLayers.has(type)}
                      onCheckedChange={() => toggleLayer(type)}
                    />
                    <div className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
                    <span className="text-sm capitalize">{type}s</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Confidence Filter */}
            <div className="space-y-2">
              <Label>Min Confidence: {(minConfidence * 100).toFixed(0)}%</Label>
              <input
                type="range"
                min={0}
                max={100}
                value={minConfidence * 100}
                onChange={(e) => setMinConfidence(parseInt(e.target.value) / 100)}
                className="w-full"
              />
            </div>

            {/* Display Options */}
            <div className="space-y-2">
              <label className="flex items-center gap-2">
                <Switch checked={showLabels} onCheckedChange={setShowLabels} />
                <span className="text-sm">Show Labels</span>
              </label>
            </div>

            {/* Zoom */}
            <div className="space-y-2">
              <Label>Zoom</Label>
              <div className="flex gap-2">
                <Button variant="outline" size="icon" onClick={() => setZoom((z) => z * 1.2)}>
                  <ZoomIn className="h-4 w-4" />
                </Button>
                <Button variant="outline" size="icon" onClick={() => setZoom((z) => z / 1.2)}>
                  <ZoomOut className="h-4 w-4" />
                </Button>
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => {
                    setZoom(1);
                    setPan({ x: 0, y: 0 });
                    setHighlightedPath(new Set());
                    setSelectedNode(null);
                  }}
                >
                  <RotateCcw className="h-4 w-4" />
                </Button>
              </div>
            </div>

            {/* Legend */}
            <div className="space-y-2">
              <Label>Edge Types</Label>
              <div className="space-y-1">
                {Object.entries(edgeTypeColors).map(([type, color]) => (
                  <div key={type} className="flex items-center gap-2 text-xs">
                    <div className="w-4 h-1" style={{ backgroundColor: color }} />
                    <span className="capitalize">{type}</span>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Canvas */}
        <Card className="col-span-3">
          <CardHeader className="pb-2">
            <CardTitle>Network Visualization</CardTitle>
          </CardHeader>
          <CardContent>
            <canvas
              ref={canvasRef}
              width={800}
              height={500}
              className="border rounded-lg bg-slate-50 cursor-pointer"
              onClick={handleCanvasClick}
            />
          </CardContent>
        </Card>
      </div>

      {/* Node Details */}
      {selectedNode && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              {getNodeIcon(selectedNode.type)}
              {selectedNode.label}
              <Badge style={{ backgroundColor: nodeColors[selectedNode.type] }}>
                {selectedNode.type}
              </Badge>
            </CardTitle>
            <CardDescription>
              {selectedNode.description} • {selectedNode.externalId}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="connections">
              <TabsList>
                <TabsTrigger value="connections">Connections</TabsTrigger>
                <TabsTrigger value="literature">Literature</TabsTrigger>
              </TabsList>

              <TabsContent value="connections">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Connected Entity</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Relationship</TableHead>
                      <TableHead>Confidence</TableHead>
                      <TableHead>Evidence</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {getConnectedEdges(selectedNode).map((edge) => {
                      const otherId = edge.source === selectedNode.id ? edge.target : edge.source;
                      const other = nodes.find((n) => n.id === otherId);
                      if (!other) return null;

                      return (
                        <TableRow
                          key={edge.id}
                          className="cursor-pointer hover:bg-slate-50"
                          onClick={() => setSelectedNode(other)}
                        >
                          <TableCell className="font-medium">{other.label}</TableCell>
                          <TableCell>
                            <Badge
                              variant="outline"
                              style={{ borderColor: nodeColors[other.type] }}
                            >
                              {other.type}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <Badge
                              variant="secondary"
                              style={{ backgroundColor: edgeTypeColors[edge.type] + "30" }}
                            >
                              {edge.type}
                            </Badge>
                          </TableCell>
                          <TableCell>{(edge.confidence * 100).toFixed(0)}%</TableCell>
                          <TableCell>
                            {edge.pubmedIds?.map((pmid) => (
                              <a
                                key={pmid}
                                href={`https://pubmed.ncbi.nlm.nih.gov/${pmid}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-blue-600 hover:underline mr-2 text-sm"
                              >
                                PMID:{pmid}
                                <ExternalLink className="inline h-3 w-3 ml-1" />
                              </a>
                            ))}
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </TabsContent>

              <TabsContent value="literature">
                <ScrollArea className="h-[200px]">
                  <div className="space-y-4">
                    {mockReferences.slice(0, 3).map((ref) => (
                      <div key={ref.pmid} className="p-3 border rounded-lg">
                        <div className="flex items-start justify-between">
                          <div>
                            <p className="font-medium text-sm">{ref.title}</p>
                            <p className="text-xs text-muted-foreground">
                              {ref.journal} ({ref.year})
                            </p>
                          </div>
                          <a
                            href={`https://pubmed.ncbi.nlm.nih.gov/${ref.pmid}`}
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            <Button variant="ghost" size="sm">
                              <BookOpen className="h-4 w-4 mr-1" />
                              PubMed
                            </Button>
                          </a>
                        </div>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
