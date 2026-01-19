"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Search,
  RefreshCw,
  Download,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Info,
  Pill,
  Heart,
  Dna,
  ArrowRight,
  ExternalLink,
  Sparkles,
  Route,
  Layers,
  BookOpen,
} from "lucide-react";

// Types for the pathway visualization
interface PathwayNode {
  id: string;
  name: string;
  type: "drug" | "disease" | "gene" | "protein" | "pathway" | "mechanism";
  x: number;
  y: number;
  layer: number;
  details?: {
    code?: string;
    vocabulary?: string;
    description?: string;
    mechanism?: string;
    pubmedIds?: string[];
  };
}

interface PathwayEdge {
  source: string;
  target: string;
  type: "treats" | "targets" | "expresses" | "inhibits" | "activates" | "associated_with" | "modulates";
  evidence?: string;
  strength?: number;
}

interface DrugDiseasePathway {
  drugId: string;
  drugName: string;
  diseaseId: string;
  diseaseName: string;
  nodes: PathwayNode[];
  edges: PathwayEdge[];
  pathwayName?: string;
  confidence?: number;
}

// Mock data for drug-disease-gene pathways
const MOCK_DRUGS = [
  { id: "DRUG001", name: "Metformin", code: "RxNorm:6809" },
  { id: "DRUG002", name: "Lisinopril", code: "RxNorm:29046" },
  { id: "DRUG003", name: "Atorvastatin", code: "RxNorm:83367" },
  { id: "DRUG004", name: "Metoprolol", code: "RxNorm:6918" },
  { id: "DRUG005", name: "Amlodipine", code: "RxNorm:17767" },
];

const MOCK_DISEASES = [
  { id: "DIS001", name: "Type 2 Diabetes Mellitus", code: "SNOMED:44054006" },
  { id: "DIS002", name: "Essential Hypertension", code: "SNOMED:59621000" },
  { id: "DIS003", name: "Hyperlipidemia", code: "SNOMED:55822004" },
  { id: "DIS004", name: "Coronary Artery Disease", code: "SNOMED:53741008" },
  { id: "DIS005", name: "Heart Failure", code: "SNOMED:84114007" },
];

// Generate mock pathway data
function generateMockPathway(drugId: string, diseaseId: string): DrugDiseasePathway {
  const drug = MOCK_DRUGS.find(d => d.id === drugId) || MOCK_DRUGS[0];
  const disease = MOCK_DISEASES.find(d => d.id === diseaseId) || MOCK_DISEASES[0];

  // Generate pathway based on drug-disease combination
  const pathwayConfigs: Record<string, { genes: string[], proteins: string[], mechanisms: string[], pathway: string }> = {
    "DRUG001-DIS001": {
      genes: ["PRKAB1", "STK11", "AMPK"],
      proteins: ["AMP-activated protein kinase", "Liver kinase B1"],
      mechanisms: ["Gluconeogenesis inhibition", "Glucose uptake enhancement"],
      pathway: "AMPK Signaling Pathway",
    },
    "DRUG002-DIS002": {
      genes: ["ACE", "AGT", "REN"],
      proteins: ["Angiotensin-converting enzyme", "Angiotensinogen"],
      mechanisms: ["ACE inhibition", "Vasodilation"],
      pathway: "Renin-Angiotensin System",
    },
    "DRUG003-DIS003": {
      genes: ["HMGCR", "LDLR", "PCSK9"],
      proteins: ["HMG-CoA reductase", "LDL receptor"],
      mechanisms: ["Cholesterol synthesis inhibition", "LDL clearance"],
      pathway: "Cholesterol Metabolism",
    },
    "DRUG004-DIS004": {
      genes: ["ADRB1", "ADRB2", "GNB3"],
      proteins: ["Beta-1 adrenergic receptor", "G protein subunit beta 3"],
      mechanisms: ["Beta-blockade", "Heart rate reduction"],
      pathway: "Adrenergic Signaling",
    },
    "DRUG005-DIS002": {
      genes: ["CACNA1C", "CACNA1D", "CACNB2"],
      proteins: ["L-type calcium channel", "Calcium channel beta-2 subunit"],
      mechanisms: ["Calcium channel blockade", "Vasodilation"],
      pathway: "Calcium Channel Signaling",
    },
  };

  const key = `${drugId}-${diseaseId}`;
  const config = pathwayConfigs[key] || {
    genes: ["GENE1", "GENE2", "GENE3"],
    proteins: ["Protein A", "Protein B"],
    mechanisms: ["Mechanism 1", "Mechanism 2"],
    pathway: "General Pathway",
  };

  const nodes: PathwayNode[] = [];
  const edges: PathwayEdge[] = [];

  // Layer 0: Drug
  nodes.push({
    id: drug.id,
    name: drug.name,
    type: "drug",
    x: 100,
    y: 300,
    layer: 0,
    details: {
      code: drug.code,
      vocabulary: "RxNorm",
      description: `Pharmaceutical compound: ${drug.name}`,
    },
  });

  // Layer 1: Genes/Targets
  config.genes.forEach((gene, i) => {
    const geneId = `GENE_${gene}`;
    nodes.push({
      id: geneId,
      name: gene,
      type: "gene",
      x: 300,
      y: 150 + i * 150,
      layer: 1,
      details: {
        code: `HGNC:${1000 + i}`,
        vocabulary: "HGNC",
        description: `Gene target for ${drug.name}`,
        pubmedIds: [`PMID:${30000000 + i * 1000}`],
      },
    });
    edges.push({
      source: drug.id,
      target: geneId,
      type: "targets",
      evidence: "Clinical trial data",
      strength: 0.9 - i * 0.1,
    });
  });

  // Layer 2: Proteins
  config.proteins.forEach((protein, i) => {
    const proteinId = `PROT_${i}`;
    nodes.push({
      id: proteinId,
      name: protein,
      type: "protein",
      x: 500,
      y: 200 + i * 200,
      layer: 2,
      details: {
        code: `UniProt:P${10000 + i}`,
        vocabulary: "UniProt",
        description: protein,
      },
    });
    // Connect to genes
    if (i < config.genes.length) {
      edges.push({
        source: `GENE_${config.genes[i]}`,
        target: proteinId,
        type: "expresses",
        strength: 0.85,
      });
    }
  });

  // Layer 3: Mechanisms
  config.mechanisms.forEach((mechanism, i) => {
    const mechId = `MECH_${i}`;
    nodes.push({
      id: mechId,
      name: mechanism,
      type: "mechanism",
      x: 700,
      y: 200 + i * 200,
      layer: 3,
      details: {
        description: `${mechanism} - molecular mechanism of action`,
      },
    });
    // Connect to proteins
    if (i < config.proteins.length) {
      edges.push({
        source: `PROT_${i}`,
        target: mechId,
        type: i % 2 === 0 ? "inhibits" : "activates",
        strength: 0.8,
      });
    }
  });

  // Layer 4: Pathway
  const pathwayId = "PATHWAY_1";
  nodes.push({
    id: pathwayId,
    name: config.pathway,
    type: "pathway",
    x: 900,
    y: 300,
    layer: 4,
    details: {
      code: `KEGG:hsa${4000 + Math.floor(Math.random() * 1000)}`,
      vocabulary: "KEGG",
      description: `${config.pathway} - biological pathway`,
    },
  });

  // Connect mechanisms to pathway
  config.mechanisms.forEach((_, i) => {
    edges.push({
      source: `MECH_${i}`,
      target: pathwayId,
      type: "modulates",
      strength: 0.75,
    });
  });

  // Layer 5: Disease
  nodes.push({
    id: disease.id,
    name: disease.name,
    type: "disease",
    x: 1100,
    y: 300,
    layer: 5,
    details: {
      code: disease.code,
      vocabulary: "SNOMED-CT",
      description: disease.name,
    },
  });

  edges.push({
    source: pathwayId,
    target: disease.id,
    type: "associated_with",
    evidence: "GWAS studies",
    strength: 0.7,
  });

  // Add a direct treatment edge
  edges.push({
    source: drug.id,
    target: disease.id,
    type: "treats",
    evidence: "FDA approved indication",
    strength: 0.95,
  });

  return {
    drugId: drug.id,
    drugName: drug.name,
    diseaseId: disease.id,
    diseaseName: disease.name,
    nodes,
    edges,
    pathwayName: config.pathway,
    confidence: 0.85 + Math.random() * 0.1,
  };
}

// Mock literature references
const MOCK_LITERATURE = [
  {
    pmid: "30000001",
    title: "Metformin activates AMPK through inhibition of AMP deaminase",
    journal: "Nature Medicine",
    year: 2022,
    relevance: 0.95,
  },
  {
    pmid: "30000002",
    title: "Molecular mechanisms of drug-target interactions in diabetes treatment",
    journal: "Cell Metabolism",
    year: 2023,
    relevance: 0.88,
  },
  {
    pmid: "30000003",
    title: "Genetic variants affecting drug response in cardiovascular disease",
    journal: "NEJM",
    year: 2023,
    relevance: 0.82,
  },
  {
    pmid: "30000004",
    title: "Systems biology approach to understanding drug mechanisms",
    journal: "Science Translational Medicine",
    year: 2024,
    relevance: 0.79,
  },
];

// Node colors by type
const NODE_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  drug: { bg: "#3b82f6", border: "#1d4ed8", text: "#ffffff" },
  disease: { bg: "#ef4444", border: "#b91c1c", text: "#ffffff" },
  gene: { bg: "#10b981", border: "#047857", text: "#ffffff" },
  protein: { bg: "#8b5cf6", border: "#6d28d9", text: "#ffffff" },
  pathway: { bg: "#f59e0b", border: "#d97706", text: "#ffffff" },
  mechanism: { bg: "#06b6d4", border: "#0891b2", text: "#ffffff" },
};

// Edge colors by type
const EDGE_COLORS: Record<string, string> = {
  treats: "#22c55e",
  targets: "#3b82f6",
  expresses: "#8b5cf6",
  inhibits: "#ef4444",
  activates: "#10b981",
  associated_with: "#f59e0b",
  modulates: "#06b6d4",
};

export default function DrugDiseaseGenePathwaysPage() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [selectedDrug, setSelectedDrug] = useState<string>("DRUG001");
  const [selectedDisease, setSelectedDisease] = useState<string>("DIS001");
  const [pathway, setPathway] = useState<DrugDiseasePathway | null>(null);
  const [selectedNode, setSelectedNode] = useState<PathwayNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<PathwayEdge | null>(null);
  const [highlightedPath, setHighlightedPath] = useState<string[]>([]);
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [loading, setLoading] = useState(false);
  const [showLayers, setShowLayers] = useState(true);
  const [activeLayer, setActiveLayer] = useState<number | null>(null);

  // Load pathway data
  const loadPathway = useCallback(() => {
    setLoading(true);
    // Simulate API call
    setTimeout(() => {
      const data = generateMockPathway(selectedDrug, selectedDisease);
      setPathway(data);
      setSelectedNode(null);
      setSelectedEdge(null);
      setHighlightedPath([]);
      setLoading(false);
    }, 500);
  }, [selectedDrug, selectedDisease]);

  useEffect(() => {
    loadPathway();
  }, [loadPathway]);

  // Draw the pathway visualization
  useEffect(() => {
    if (!canvasRef.current || !pathway) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Set canvas size
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * window.devicePixelRatio;
    canvas.height = rect.height * window.devicePixelRatio;
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio);

    // Clear canvas
    ctx.fillStyle = "#0f172a";
    ctx.fillRect(0, 0, rect.width, rect.height);

    // Apply transformations
    ctx.save();
    ctx.translate(offset.x + rect.width / 2, offset.y + rect.height / 2);
    ctx.scale(zoom, zoom);
    ctx.translate(-600, -300);

    // Draw layer backgrounds if enabled
    if (showLayers) {
      const layerColors = ["rgba(59, 130, 246, 0.1)", "rgba(16, 185, 129, 0.1)", "rgba(139, 92, 246, 0.1)", "rgba(6, 182, 212, 0.1)", "rgba(245, 158, 11, 0.1)", "rgba(239, 68, 68, 0.1)"];
      const layerLabels = ["Drugs", "Genes", "Proteins", "Mechanisms", "Pathways", "Diseases"];

      for (let i = 0; i < 6; i++) {
        const x = 50 + i * 200;
        const isActive = activeLayer === null || activeLayer === i;
        ctx.fillStyle = isActive ? layerColors[i] : "rgba(30, 41, 59, 0.3)";
        ctx.fillRect(x, 50, 180, 500);

        // Layer label
        ctx.fillStyle = isActive ? "#94a3b8" : "#475569";
        ctx.font = "bold 12px Inter, sans-serif";
        ctx.textAlign = "center";
        ctx.fillText(layerLabels[i], x + 90, 40);
      }
    }

    // Draw edges
    pathway.edges.forEach((edge) => {
      const sourceNode = pathway.nodes.find((n) => n.id === edge.source);
      const targetNode = pathway.nodes.find((n) => n.id === edge.target);
      if (!sourceNode || !targetNode) return;

      const isHighlighted = highlightedPath.includes(edge.source) && highlightedPath.includes(edge.target);
      const isSelected = selectedEdge?.source === edge.source && selectedEdge?.target === edge.target;
      const isDimmed = activeLayer !== null && (sourceNode.layer !== activeLayer && targetNode.layer !== activeLayer);

      ctx.beginPath();
      ctx.moveTo(sourceNode.x, sourceNode.y);

      // Draw curved line for non-adjacent connections
      if (Math.abs(sourceNode.layer - targetNode.layer) > 1) {
        const midX = (sourceNode.x + targetNode.x) / 2;
        const midY = (sourceNode.y + targetNode.y) / 2 - 50;
        ctx.quadraticCurveTo(midX, midY, targetNode.x, targetNode.y);
      } else {
        ctx.lineTo(targetNode.x, targetNode.y);
      }

      ctx.strokeStyle = isDimmed ? "#334155" : isHighlighted || isSelected ? "#fbbf24" : EDGE_COLORS[edge.type] || "#64748b";
      ctx.lineWidth = isHighlighted || isSelected ? 3 : edge.strength ? edge.strength * 2 + 1 : 2;
      ctx.globalAlpha = isDimmed ? 0.3 : 1;
      ctx.stroke();
      ctx.globalAlpha = 1;

      // Draw arrow
      const angle = Math.atan2(targetNode.y - sourceNode.y, targetNode.x - sourceNode.x);
      const arrowX = targetNode.x - Math.cos(angle) * 25;
      const arrowY = targetNode.y - Math.sin(angle) * 25;

      ctx.beginPath();
      ctx.moveTo(arrowX, arrowY);
      ctx.lineTo(
        arrowX - 10 * Math.cos(angle - Math.PI / 6),
        arrowY - 10 * Math.sin(angle - Math.PI / 6)
      );
      ctx.lineTo(
        arrowX - 10 * Math.cos(angle + Math.PI / 6),
        arrowY - 10 * Math.sin(angle + Math.PI / 6)
      );
      ctx.closePath();
      ctx.fillStyle = isDimmed ? "#334155" : isHighlighted || isSelected ? "#fbbf24" : EDGE_COLORS[edge.type] || "#64748b";
      ctx.globalAlpha = isDimmed ? 0.3 : 1;
      ctx.fill();
      ctx.globalAlpha = 1;
    });

    // Draw nodes
    pathway.nodes.forEach((node) => {
      const isSelected = selectedNode?.id === node.id;
      const isHighlighted = highlightedPath.includes(node.id);
      const isDimmed = activeLayer !== null && node.layer !== activeLayer;
      const colors = NODE_COLORS[node.type] || NODE_COLORS.gene;

      // Node circle
      ctx.beginPath();
      ctx.arc(node.x, node.y, isSelected || isHighlighted ? 28 : 22, 0, Math.PI * 2);
      ctx.fillStyle = isDimmed ? "#1e293b" : colors.bg;
      ctx.globalAlpha = isDimmed ? 0.4 : 1;
      ctx.fill();

      // Border
      ctx.strokeStyle = isHighlighted ? "#fbbf24" : isSelected ? "#ffffff" : colors.border;
      ctx.lineWidth = isSelected || isHighlighted ? 3 : 2;
      ctx.stroke();
      ctx.globalAlpha = 1;

      // Icon based on type
      ctx.fillStyle = isDimmed ? "#475569" : colors.text;
      ctx.font = "14px sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";

      const icons: Record<string, string> = {
        drug: "\u{1F48A}", // pill emoji
        disease: "\u{2764}", // heart emoji
        gene: "\u{1F9EC}", // DNA emoji
        protein: "\u{1F300}", // cyclone emoji
        pathway: "\u{1F517}", // link emoji
        mechanism: "\u{2699}", // gear emoji
      };
      ctx.fillText(icons[node.type] || "\u{25CF}", node.x, node.y);

      // Node label
      ctx.fillStyle = isDimmed ? "#475569" : "#e2e8f0";
      ctx.font = "11px Inter, sans-serif";
      ctx.textAlign = "center";
      const maxWidth = 80;
      const name = node.name.length > 15 ? node.name.substring(0, 12) + "..." : node.name;
      ctx.fillText(name, node.x, node.y + 38);
    });

    ctx.restore();
  }, [pathway, selectedNode, selectedEdge, highlightedPath, zoom, offset, showLayers, activeLayer]);

  // Handle canvas click
  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!canvasRef.current || !pathway) return;

    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left - offset.x - rect.width / 2) / zoom + 600;
    const y = (e.clientY - rect.top - offset.y - rect.height / 2) / zoom + 300;

    // Check if clicked on a node
    for (const node of pathway.nodes) {
      const distance = Math.sqrt((x - node.x) ** 2 + (y - node.y) ** 2);
      if (distance < 25) {
        setSelectedNode(node);
        setSelectedEdge(null);
        // Highlight path from drug to this node
        highlightPathToNode(node.id);
        return;
      }
    }

    // Check if clicked on an edge
    for (const edge of pathway.edges) {
      const sourceNode = pathway.nodes.find((n) => n.id === edge.source);
      const targetNode = pathway.nodes.find((n) => n.id === edge.target);
      if (!sourceNode || !targetNode) continue;

      // Simple line-point distance check
      const lineLength = Math.sqrt(
        (targetNode.x - sourceNode.x) ** 2 + (targetNode.y - sourceNode.y) ** 2
      );
      const d1 = Math.sqrt((x - sourceNode.x) ** 2 + (y - sourceNode.y) ** 2);
      const d2 = Math.sqrt((x - targetNode.x) ** 2 + (y - targetNode.y) ** 2);

      if (Math.abs(d1 + d2 - lineLength) < 10) {
        setSelectedEdge(edge);
        setSelectedNode(null);
        setHighlightedPath([edge.source, edge.target]);
        return;
      }
    }

    // Clear selection
    setSelectedNode(null);
    setSelectedEdge(null);
    setHighlightedPath([]);
  };

  // Find and highlight path from drug to a node
  const highlightPathToNode = (targetId: string) => {
    if (!pathway) return;

    const drugNode = pathway.nodes.find((n) => n.type === "drug");
    if (!drugNode || drugNode.id === targetId) {
      setHighlightedPath([targetId]);
      return;
    }

    // BFS to find shortest path
    const visited = new Set<string>();
    const queue: { id: string; path: string[] }[] = [{ id: drugNode.id, path: [drugNode.id] }];
    visited.add(drugNode.id);

    while (queue.length > 0) {
      const { id, path } = queue.shift()!;

      if (id === targetId) {
        setHighlightedPath(path);
        return;
      }

      // Find all connected nodes
      for (const edge of pathway.edges) {
        let nextId: string | null = null;
        if (edge.source === id && !visited.has(edge.target)) {
          nextId = edge.target;
        } else if (edge.target === id && !visited.has(edge.source)) {
          nextId = edge.source;
        }

        if (nextId) {
          visited.add(nextId);
          queue.push({ id: nextId, path: [...path, nextId] });
        }
      }
    }

    setHighlightedPath([targetId]);
  };

  // Handle mouse events for panning
  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button === 0) {
      setIsDragging(true);
      setDragStart({ x: e.clientX - offset.x, y: e.clientY - offset.y });
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isDragging) {
      setOffset({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y,
      });
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  // Handle wheel for zoom
  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setZoom((prev) => Math.max(0.3, Math.min(3, prev * delta)));
  };

  // Reset view
  const resetView = () => {
    setZoom(1);
    setOffset({ x: 0, y: 0 });
    setActiveLayer(null);
  };

  // Export pathway as JSON
  const exportPathway = () => {
    if (!pathway) return;
    const dataStr = JSON.stringify(pathway, null, 2);
    const dataUri = "data:application/json;charset=utf-8," + encodeURIComponent(dataStr);
    const link = document.createElement("a");
    link.href = dataUri;
    link.download = `pathway_${pathway.drugName}_${pathway.diseaseName}.json`;
    link.click();
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b bg-card">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-purple-600">
                <Route className="h-5 w-5 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold">Drug-Disease-Gene Pathways</h1>
                <p className="text-sm text-muted-foreground">
                  Explore molecular mechanisms connecting drugs to diseases
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={exportPathway}>
                <Download className="mr-2 h-4 w-4" />
                Export
              </Button>
              <Button variant="outline" size="sm" onClick={loadPathway}>
                <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
                Refresh
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="container mx-auto px-6 py-6">
        <div className="grid grid-cols-12 gap-6">
          {/* Left Panel - Controls */}
          <div className="col-span-3 space-y-4">
            {/* Drug-Disease Selection */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Search className="h-4 w-4" />
                  Pathway Query
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label className="flex items-center gap-2">
                    <Pill className="h-4 w-4 text-blue-500" />
                    Drug
                  </Label>
                  <Select value={selectedDrug} onValueChange={setSelectedDrug}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select drug" />
                    </SelectTrigger>
                    <SelectContent>
                      {MOCK_DRUGS.map((drug) => (
                        <SelectItem key={drug.id} value={drug.id}>
                          {drug.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="flex items-center justify-center py-2">
                  <ArrowRight className="h-5 w-5 text-muted-foreground" />
                </div>

                <div className="space-y-2">
                  <Label className="flex items-center gap-2">
                    <Heart className="h-4 w-4 text-red-500" />
                    Disease
                  </Label>
                  <Select value={selectedDisease} onValueChange={setSelectedDisease}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select disease" />
                    </SelectTrigger>
                    <SelectContent>
                      {MOCK_DISEASES.map((disease) => (
                        <SelectItem key={disease.id} value={disease.id}>
                          {disease.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </CardContent>
            </Card>

            {/* View Controls */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Layers className="h-4 w-4" />
                  View Controls
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={() => setZoom((z) => Math.min(3, z * 1.2))}
                  >
                    <ZoomIn className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={() => setZoom((z) => Math.max(0.3, z / 1.2))}
                  >
                    <ZoomOut className="h-4 w-4" />
                  </Button>
                  <Button variant="outline" size="icon" onClick={resetView}>
                    <Maximize2 className="h-4 w-4" />
                  </Button>
                  <span className="ml-2 text-sm text-muted-foreground">
                    {Math.round(zoom * 100)}%
                  </span>
                </div>

                <div className="space-y-2">
                  <Label>Filter by Layer</Label>
                  <div className="flex flex-wrap gap-1">
                    {["Drug", "Gene", "Protein", "Mechanism", "Pathway", "Disease"].map((layer, i) => (
                      <Badge
                        key={layer}
                        variant={activeLayer === i ? "default" : "outline"}
                        className="cursor-pointer"
                        onClick={() => setActiveLayer(activeLayer === i ? null : i)}
                      >
                        {layer}
                      </Badge>
                    ))}
                  </div>
                </div>

                <div className="flex items-center justify-between">
                  <Label>Show Layers</Label>
                  <input
                    type="checkbox"
                    checked={showLayers}
                    onChange={(e) => setShowLayers(e.target.checked)}
                    className="h-4 w-4"
                  />
                </div>
              </CardContent>
            </Card>

            {/* Legend */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-lg">Legend</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-2">
                  <p className="text-xs font-medium text-muted-foreground">Node Types</p>
                  {Object.entries(NODE_COLORS).map(([type, colors]) => (
                    <div key={type} className="flex items-center gap-2">
                      <div
                        className="h-4 w-4 rounded-full"
                        style={{ backgroundColor: colors.bg }}
                      />
                      <span className="text-sm capitalize">{type}</span>
                    </div>
                  ))}
                </div>
                <div className="space-y-2">
                  <p className="text-xs font-medium text-muted-foreground">Edge Types</p>
                  {Object.entries(EDGE_COLORS).map(([type, color]) => (
                    <div key={type} className="flex items-center gap-2">
                      <div
                        className="h-0.5 w-4"
                        style={{ backgroundColor: color }}
                      />
                      <span className="text-sm capitalize">{type.replace("_", " ")}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Center - Visualization */}
          <div className="col-span-6">
            <Card className="h-[700px]">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <Sparkles className="h-5 w-5 text-amber-500" />
                      {pathway?.pathwayName || "Pathway Visualization"}
                    </CardTitle>
                    {pathway && (
                      <CardDescription>
                        {pathway.drugName} → {pathway.diseaseName}
                        {pathway.confidence && (
                          <Badge variant="secondary" className="ml-2">
                            Confidence: {Math.round(pathway.confidence * 100)}%
                          </Badge>
                        )}
                      </CardDescription>
                    )}
                  </div>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                <div className="relative h-[600px] overflow-hidden rounded-b-lg bg-slate-900">
                  {loading ? (
                    <div className="flex h-full items-center justify-center">
                      <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
                    </div>
                  ) : (
                    <canvas
                      ref={canvasRef}
                      className="h-full w-full cursor-grab active:cursor-grabbing"
                      onClick={handleCanvasClick}
                      onMouseDown={handleMouseDown}
                      onMouseMove={handleMouseMove}
                      onMouseUp={handleMouseUp}
                      onMouseLeave={handleMouseUp}
                      onWheel={handleWheel}
                    />
                  )}

                  {/* Pathway stats overlay */}
                  {pathway && (
                    <div className="absolute bottom-4 left-4 flex gap-2">
                      <Badge variant="secondary">
                        {pathway.nodes.length} nodes
                      </Badge>
                      <Badge variant="secondary">
                        {pathway.edges.length} edges
                      </Badge>
                      <Badge variant="secondary">
                        6 layers
                      </Badge>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Right Panel - Details */}
          <div className="col-span-3 space-y-4">
            {/* Selected Node/Edge Details */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Info className="h-4 w-4" />
                  Details
                </CardTitle>
              </CardHeader>
              <CardContent>
                {selectedNode ? (
                  <div className="space-y-4">
                    <div className="flex items-center gap-3">
                      <div
                        className="flex h-10 w-10 items-center justify-center rounded-full"
                        style={{ backgroundColor: NODE_COLORS[selectedNode.type]?.bg }}
                      >
                        {selectedNode.type === "drug" && <Pill className="h-5 w-5 text-white" />}
                        {selectedNode.type === "disease" && <Heart className="h-5 w-5 text-white" />}
                        {selectedNode.type === "gene" && <Dna className="h-5 w-5 text-white" />}
                        {!["drug", "disease", "gene"].includes(selectedNode.type) && (
                          <span className="text-white text-lg">
                            {selectedNode.type.charAt(0).toUpperCase()}
                          </span>
                        )}
                      </div>
                      <div>
                        <p className="font-semibold">{selectedNode.name}</p>
                        <Badge variant="outline" className="capitalize">
                          {selectedNode.type}
                        </Badge>
                      </div>
                    </div>

                    {selectedNode.details && (
                      <div className="space-y-2 text-sm">
                        {selectedNode.details.code && (
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Code</span>
                            <code className="text-xs">{selectedNode.details.code}</code>
                          </div>
                        )}
                        {selectedNode.details.vocabulary && (
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Vocabulary</span>
                            <span>{selectedNode.details.vocabulary}</span>
                          </div>
                        )}
                        {selectedNode.details.description && (
                          <div>
                            <span className="text-muted-foreground">Description</span>
                            <p className="mt-1 text-xs">{selectedNode.details.description}</p>
                          </div>
                        )}
                        {selectedNode.details.pubmedIds && selectedNode.details.pubmedIds.length > 0 && (
                          <div>
                            <span className="text-muted-foreground">References</span>
                            <div className="mt-1 flex flex-wrap gap-1">
                              {selectedNode.details.pubmedIds.map((pmid) => (
                                <Badge key={pmid} variant="secondary" className="text-xs">
                                  <ExternalLink className="mr-1 h-3 w-3" />
                                  {pmid}
                                </Badge>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {highlightedPath.length > 1 && (
                      <div className="rounded-lg border bg-muted/50 p-3">
                        <p className="text-xs font-medium text-muted-foreground mb-2">
                          Path from Drug
                        </p>
                        <div className="flex flex-wrap items-center gap-1">
                          {highlightedPath.map((nodeId, i) => {
                            const node = pathway?.nodes.find((n) => n.id === nodeId);
                            return (
                              <span key={nodeId} className="flex items-center">
                                <Badge
                                  variant="secondary"
                                  className="text-xs"
                                  style={{
                                    backgroundColor: NODE_COLORS[node?.type || "gene"]?.bg,
                                    color: "white",
                                  }}
                                >
                                  {node?.name.substring(0, 10) || nodeId}
                                </Badge>
                                {i < highlightedPath.length - 1 && (
                                  <ArrowRight className="mx-1 h-3 w-3 text-muted-foreground" />
                                )}
                              </span>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                ) : selectedEdge ? (
                  <div className="space-y-4">
                    <div className="flex items-center gap-2">
                      <div
                        className="h-1 w-8"
                        style={{ backgroundColor: EDGE_COLORS[selectedEdge.type] }}
                      />
                      <Badge className="capitalize">{selectedEdge.type.replace("_", " ")}</Badge>
                    </div>

                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">From</span>
                        <span>
                          {pathway?.nodes.find((n) => n.id === selectedEdge.source)?.name}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">To</span>
                        <span>
                          {pathway?.nodes.find((n) => n.id === selectedEdge.target)?.name}
                        </span>
                      </div>
                      {selectedEdge.evidence && (
                        <div>
                          <span className="text-muted-foreground">Evidence</span>
                          <p className="mt-1 text-xs">{selectedEdge.evidence}</p>
                        </div>
                      )}
                      {selectedEdge.strength && (
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Strength</span>
                          <span>{Math.round(selectedEdge.strength * 100)}%</span>
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    Click on a node or edge to view details
                  </p>
                )}
              </CardContent>
            </Card>

            {/* Literature References */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-lg">
                  <BookOpen className="h-4 w-4" />
                  Related Literature
                </CardTitle>
                <CardDescription>
                  Publications supporting this pathway
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[250px]">
                  <div className="space-y-3">
                    {MOCK_LITERATURE.map((paper) => (
                      <div
                        key={paper.pmid}
                        className="rounded-lg border p-3 hover:bg-muted/50 cursor-pointer transition-colors"
                      >
                        <p className="text-sm font-medium line-clamp-2">
                          {paper.title}
                        </p>
                        <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                          <span>{paper.journal}</span>
                          <span>|</span>
                          <span>{paper.year}</span>
                          <Badge variant="secondary" className="ml-auto">
                            {Math.round(paper.relevance * 100)}% relevant
                          </Badge>
                        </div>
                        <div className="mt-2">
                          <Badge variant="outline" className="text-xs">
                            <ExternalLink className="mr-1 h-3 w-3" />
                            PMID: {paper.pmid}
                          </Badge>
                        </div>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
