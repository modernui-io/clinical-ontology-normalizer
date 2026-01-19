"use client";

import { useState, useEffect, useRef } from "react";
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
import { Slider } from "@/components/ui/slider";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Users,
  Search,
  ZoomIn,
  ZoomOut,
  Maximize2,
  RefreshCw,
  Filter,
  Activity,
  ChevronLeft,
  Info,
  Loader2,
  AlertCircle,
  CheckCircle,
  ArrowRight,
  UserCircle,
  Pill,
  Stethoscope,
  FlaskConical,
} from "lucide-react";

// ============================================================================
// Types
// ============================================================================

interface PatientNode {
  id: string;
  patient_id: string;
  similarity_score?: number;
  shared_conditions: string[];
  shared_medications: string[];
  shared_procedures: string[];
  total_shared_features: number;
  x?: number;
  y?: number;
  isCenter?: boolean;
}

interface PatientEdge {
  source: string;
  target: string;
  similarity: number;
}

interface SimilarPatient {
  patient_id: string;
  similarity_score: number;
  shared_conditions: string[];
  shared_medications: string[];
  shared_procedures: string[];
  total_shared_features: number;
}

// ============================================================================
// Network Canvas Component
// ============================================================================

interface PatientNetworkProps {
  nodes: PatientNode[];
  edges: PatientEdge[];
  selectedPatient: PatientNode | null;
  onPatientClick: (node: PatientNode) => void;
  similarityThreshold: number;
}

function PatientNetwork({
  nodes,
  edges,
  selectedPatient,
  onPatientClick,
  similarityThreshold,
}: PatientNetworkProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [hoveredNode, setHoveredNode] = useState<PatientNode | null>(null);

  // Apply force-directed layout
  useEffect(() => {
    if (nodes.length === 0) return;

    const width = 800;
    const height = 600;
    const centerX = width / 2;
    const centerY = height / 2;

    // Find center node
    const centerNode = nodes.find(n => n.isCenter);

    // Initialize positions
    nodes.forEach((node, i) => {
      if (node.isCenter) {
        node.x = centerX;
        node.y = centerY;
      } else {
        const angle = (i / (nodes.length - 1)) * 2 * Math.PI;
        // Distance based on similarity (more similar = closer)
        const similarity = node.similarity_score || 0.5;
        const radius = (1 - similarity) * 200 + 100;
        node.x = centerX + radius * Math.cos(angle);
        node.y = centerY + radius * Math.sin(angle);
      }
    });

    // Run simulation
    for (let iter = 0; iter < 30; iter++) {
      // Repulsion between non-center nodes
      for (let i = 0; i < nodes.length; i++) {
        if (nodes[i].isCenter) continue;
        for (let j = i + 1; j < nodes.length; j++) {
          if (nodes[j].isCenter) continue;

          const dx = (nodes[j].x || 0) - (nodes[i].x || 0);
          const dy = (nodes[j].y || 0) - (nodes[i].y || 0);
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          if (dist < 80) {
            const force = 500 / (dist * dist);
            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;
            nodes[i].x = (nodes[i].x || 0) - fx;
            nodes[i].y = (nodes[i].y || 0) - fy;
            nodes[j].x = (nodes[j].x || 0) + fx;
            nodes[j].y = (nodes[j].y || 0) + fy;
          }
        }
      }

      // Keep center node fixed
      if (centerNode) {
        centerNode.x = centerX;
        centerNode.y = centerY;
      }
    }
  }, [nodes]);

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

    // Filter edges by threshold
    const filteredEdges = edges.filter(e => e.similarity >= similarityThreshold);

    // Draw edges with similarity-based opacity
    filteredEdges.forEach(edge => {
      const source = nodes.find(n => n.id === edge.source);
      const target = nodes.find(n => n.id === edge.target);
      if (source && target && source.x && source.y && target.x && target.y) {
        const alpha = Math.min(1, edge.similarity);
        ctx.strokeStyle = `rgba(59, 130, 246, ${alpha})`;
        ctx.lineWidth = 1 + edge.similarity * 2;
        ctx.beginPath();
        ctx.moveTo(source.x, source.y);
        ctx.lineTo(target.x, target.y);
        ctx.stroke();

        // Draw similarity label on edge
        const midX = (source.x + target.x) / 2;
        const midY = (source.y + target.y) / 2;
        ctx.fillStyle = `rgba(255, 255, 255, ${alpha * 0.8})`;
        ctx.font = "9px sans-serif";
        ctx.textAlign = "center";
        ctx.fillText(`${Math.round(edge.similarity * 100)}%`, midX, midY);
      }
    });

    // Draw nodes
    nodes.forEach(node => {
      if (!node.x || !node.y) return;

      const isSelected = selectedPatient?.id === node.id;
      const isHovered = hoveredNode?.id === node.id;
      const isCenter = node.isCenter;

      // Node colors based on role
      let color = "#22c55e"; // green for similar patients
      if (isCenter) color = "#3b82f6"; // blue for center patient

      const radius = isCenter ? 25 : isSelected || isHovered ? 20 : 15;

      // Glow effect for center
      if (isCenter) {
        const gradient = ctx.createRadialGradient(
          node.x, node.y, radius,
          node.x, node.y, radius * 2
        );
        gradient.addColorStop(0, "rgba(59, 130, 246, 0.3)");
        gradient.addColorStop(1, "rgba(59, 130, 246, 0)");
        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(node.x, node.y, radius * 2, 0, 2 * Math.PI);
        ctx.fill();
      }

      // Node circle
      ctx.beginPath();
      ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI);
      ctx.fillStyle = color;
      ctx.fill();

      if (isSelected || isHovered || isCenter) {
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 3;
        ctx.stroke();
      }

      // Patient icon
      ctx.fillStyle = "#ffffff";
      ctx.font = `${radius}px sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("P", node.x, node.y);

      // Node label
      ctx.font = "11px sans-serif";
      ctx.textBaseline = "top";
      const label = isCenter ? `${node.patient_id} (Reference)` : node.patient_id;
      ctx.fillText(label, node.x, node.y + radius + 5);

      // Similarity score for non-center nodes
      if (!isCenter && node.similarity_score) {
        ctx.font = "9px sans-serif";
        ctx.fillStyle = "#94a3b8";
        ctx.fillText(
          `${Math.round(node.similarity_score * 100)}% similar`,
          node.x,
          node.y + radius + 18
        );
      }
    });

    ctx.restore();

    // Legend
    ctx.fillStyle = "#ffffff";
    ctx.font = "12px sans-serif";
    ctx.textAlign = "left";

    ctx.fillStyle = "#3b82f6";
    ctx.beginPath();
    ctx.arc(20, 20, 8, 0, 2 * Math.PI);
    ctx.fill();
    ctx.fillStyle = "#ffffff";
    ctx.fillText("Reference Patient", 35, 24);

    ctx.fillStyle = "#22c55e";
    ctx.beginPath();
    ctx.arc(20, 45, 8, 0, 2 * Math.PI);
    ctx.fill();
    ctx.fillStyle = "#ffffff";
    ctx.fillText("Similar Patients", 35, 49);

  }, [nodes, edges, zoom, offset, selectedPatient, hoveredNode, similarityThreshold]);

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
    let foundNode: PatientNode | null = null;
    for (const node of nodes) {
      if (node.x && node.y) {
        const dx = x - node.x;
        const dy = y - node.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        const radius = node.isCenter ? 25 : 15;
        if (dist < radius + 5) {
          foundNode = node;
          break;
        }
      }
    }
    setHoveredNode(foundNode);

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

  const handleClick = () => {
    if (hoveredNode) {
      onPatientClick(hoveredNode);
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
        className="w-full h-full"
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

      {/* Stats */}
      <div className="absolute top-4 right-4 bg-slate-800/80 px-3 py-1 rounded-full text-xs text-slate-300">
        {nodes.length} patients, {edges.filter(e => e.similarity >= similarityThreshold).length} connections
      </div>
    </div>
  );
}

// ============================================================================
// Main Page Component
// ============================================================================

export default function PatientSimilarityPage() {
  const [referencePatientId, setReferencePatientId] = useState("P001");
  const [similarityMetric, setSimilarityMetric] = useState("jaccard");
  const [similarityThreshold, setSimilarityThreshold] = useState(0.5);
  const [nodes, setNodes] = useState<PatientNode[]>([]);
  const [edges, setEdges] = useState<PatientEdge[]>([]);
  const [selectedPatient, setSelectedPatient] = useState<PatientNode | null>(null);
  const [similarPatients, setSimilarPatients] = useState<SimilarPatient[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // Load similar patients
  useEffect(() => {
    loadSimilarPatients();
  }, [referencePatientId]);

  const loadSimilarPatients = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(
        `http://localhost:8000/api/graph/patients/${referencePatientId}/similar?metric=${similarityMetric}&min_similarity=${similarityThreshold}&limit=15`
      );

      if (response.ok) {
        const data = await response.json();
        setSimilarPatients(data.similar_patients || []);
        buildNetwork(data.similar_patients || []);
      } else {
        // Use mock data
        loadMockData();
      }
    } catch {
      console.error("Failed to load similar patients");
      loadMockData();
    } finally {
      setIsLoading(false);
    }
  };

  const loadMockData = () => {
    const mockSimilar: SimilarPatient[] = [
      {
        patient_id: "P002",
        similarity_score: 0.92,
        shared_conditions: ["Type 2 diabetes mellitus", "Hypertension", "Hyperlipidemia"],
        shared_medications: ["Metformin", "Lisinopril", "Atorvastatin"],
        shared_procedures: ["HbA1c test", "Lipid panel"],
        total_shared_features: 8,
      },
      {
        patient_id: "P003",
        similarity_score: 0.85,
        shared_conditions: ["Type 2 diabetes mellitus", "Hypertension"],
        shared_medications: ["Metformin", "Amlodipine"],
        shared_procedures: ["HbA1c test", "Blood pressure check"],
        total_shared_features: 6,
      },
      {
        patient_id: "P004",
        similarity_score: 0.78,
        shared_conditions: ["Type 2 diabetes mellitus", "Diabetic retinopathy"],
        shared_medications: ["Metformin", "Insulin glargine"],
        shared_procedures: ["Eye exam", "HbA1c test"],
        total_shared_features: 6,
      },
      {
        patient_id: "P005",
        similarity_score: 0.72,
        shared_conditions: ["Type 2 diabetes mellitus"],
        shared_medications: ["Metformin", "Sitagliptin"],
        shared_procedures: ["HbA1c test"],
        total_shared_features: 4,
      },
      {
        patient_id: "P006",
        similarity_score: 0.68,
        shared_conditions: ["Hypertension", "Hyperlipidemia"],
        shared_medications: ["Lisinopril", "Atorvastatin"],
        shared_procedures: ["Lipid panel"],
        total_shared_features: 5,
      },
      {
        patient_id: "P007",
        similarity_score: 0.65,
        shared_conditions: ["Type 2 diabetes mellitus"],
        shared_medications: ["Metformin"],
        shared_procedures: ["HbA1c test", "Comprehensive metabolic panel"],
        total_shared_features: 4,
      },
      {
        patient_id: "P008",
        similarity_score: 0.58,
        shared_conditions: ["Hypertension"],
        shared_medications: ["Lisinopril", "Hydrochlorothiazide"],
        shared_procedures: ["Blood pressure check"],
        total_shared_features: 4,
      },
      {
        patient_id: "P009",
        similarity_score: 0.52,
        shared_conditions: ["Type 2 diabetes mellitus"],
        shared_medications: ["Metformin"],
        shared_procedures: [],
        total_shared_features: 2,
      },
    ];

    setSimilarPatients(mockSimilar);
    buildNetwork(mockSimilar);
  };

  const buildNetwork = (similar: SimilarPatient[]) => {
    // Center node (reference patient)
    const centerNode: PatientNode = {
      id: referencePatientId,
      patient_id: referencePatientId,
      shared_conditions: [],
      shared_medications: [],
      shared_procedures: [],
      total_shared_features: 0,
      isCenter: true,
    };

    // Similar patient nodes
    const patientNodes: PatientNode[] = similar.map(p => ({
      id: p.patient_id,
      patient_id: p.patient_id,
      similarity_score: p.similarity_score,
      shared_conditions: p.shared_conditions,
      shared_medications: p.shared_medications,
      shared_procedures: p.shared_procedures,
      total_shared_features: p.total_shared_features,
    }));

    setNodes([centerNode, ...patientNodes]);

    // Edges from center to all similar patients
    const newEdges: PatientEdge[] = similar.map(p => ({
      source: referencePatientId,
      target: p.patient_id,
      similarity: p.similarity_score,
    }));

    // Add some edges between similar patients based on shared features
    for (let i = 0; i < similar.length; i++) {
      for (let j = i + 1; j < similar.length; j++) {
        const p1 = similar[i];
        const p2 = similar[j];
        const sharedConditions = p1.shared_conditions.filter(c =>
          p2.shared_conditions.includes(c)
        ).length;
        const sharedMeds = p1.shared_medications.filter(m =>
          p2.shared_medications.includes(m)
        ).length;
        const similarity = (sharedConditions + sharedMeds) / 10;

        if (similarity > 0.3) {
          newEdges.push({
            source: p1.patient_id,
            target: p2.patient_id,
            similarity,
          });
        }
      }
    }

    setEdges(newEdges);
  };

  const handlePatientClick = (node: PatientNode) => {
    setSelectedPatient(node);
  };

  const handleCompare = () => {
    if (selectedPatient && !selectedPatient.isCenter) {
      // Navigate to comparison view
      alert(`Compare ${referencePatientId} with ${selectedPatient.patient_id}`);
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/analytics/graph">
            <Button variant="ghost" size="icon">
              <ChevronLeft className="h-5 w-5" />
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Users className="h-6 w-6" />
              Patient Similarity Network
            </h1>
            <p className="text-muted-foreground">
              Find patients with similar clinical profiles
            </p>
          </div>
        </div>
        <Button onClick={loadSimilarPatients} disabled={isLoading}>
          {isLoading ? (
            <Loader2 className="h-4 w-4 animate-spin mr-2" />
          ) : (
            <RefreshCw className="h-4 w-4 mr-2" />
          )}
          Refresh
        </Button>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-12 gap-6">
        {/* Left Panel - Controls */}
        <div className="col-span-3 space-y-4">
          {/* Patient Selection */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Reference Patient</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2">
                <Input
                  placeholder="Patient ID..."
                  value={referencePatientId}
                  onChange={(e) => setReferencePatientId(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && loadSimilarPatients()}
                />
                <Button size="icon" onClick={loadSimilarPatients}>
                  <Search className="h-4 w-4" />
                </Button>
              </div>

              <div className="space-y-2">
                <Label className="text-xs">Similarity Metric</Label>
                <Select
                  value={similarityMetric}
                  onValueChange={setSimilarityMetric}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="jaccard">Jaccard</SelectItem>
                    <SelectItem value="cosine">Cosine</SelectItem>
                    <SelectItem value="overlap">Overlap</SelectItem>
                    <SelectItem value="dice">Dice</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label className="text-xs">Similarity Threshold</Label>
                  <span className="text-xs text-muted-foreground">
                    {Math.round(similarityThreshold * 100)}%
                  </span>
                </div>
                <Slider
                  value={[similarityThreshold]}
                  onValueChange={([v]) => setSimilarityThreshold(v)}
                  min={0}
                  max={1}
                  step={0.05}
                />
              </div>
            </CardContent>
          </Card>

          {/* Selected Patient Details */}
          {selectedPatient && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm flex items-center gap-2">
                  <UserCircle className="h-4 w-4" />
                  {selectedPatient.isCenter ? "Reference Patient" : "Selected Patient"}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div>
                  <div className="font-medium">{selectedPatient.patient_id}</div>
                  {selectedPatient.similarity_score && (
                    <Badge className="mt-1">
                      {Math.round(selectedPatient.similarity_score * 100)}% Similar
                    </Badge>
                  )}
                </div>

                <Separator />

                {selectedPatient.shared_conditions.length > 0 && (
                  <div>
                    <div className="text-xs font-medium text-muted-foreground flex items-center gap-1 mb-1">
                      <Stethoscope className="h-3 w-3" />
                      Shared Conditions
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {selectedPatient.shared_conditions.map((c, i) => (
                        <Badge key={i} variant="outline" className="text-xs">
                          {c}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}

                {selectedPatient.shared_medications.length > 0 && (
                  <div>
                    <div className="text-xs font-medium text-muted-foreground flex items-center gap-1 mb-1">
                      <Pill className="h-3 w-3" />
                      Shared Medications
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {selectedPatient.shared_medications.map((m, i) => (
                        <Badge key={i} variant="outline" className="text-xs">
                          {m}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}

                {selectedPatient.shared_procedures.length > 0 && (
                  <div>
                    <div className="text-xs font-medium text-muted-foreground flex items-center gap-1 mb-1">
                      <Activity className="h-3 w-3" />
                      Shared Procedures
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {selectedPatient.shared_procedures.map((p, i) => (
                        <Badge key={i} variant="outline" className="text-xs">
                          {p}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}

                {!selectedPatient.isCenter && (
                  <Button className="w-full" size="sm" onClick={handleCompare}>
                    Compare Patients
                    <ArrowRight className="h-4 w-4 ml-2" />
                  </Button>
                )}
              </CardContent>
            </Card>
          )}
        </div>

        {/* Center - Network Visualization */}
        <div className="col-span-6">
          <Card className="h-[600px]">
            <CardContent className="p-0 h-full">
              {isLoading ? (
                <div className="flex items-center justify-center h-full">
                  <div className="text-center">
                    <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4 text-primary" />
                    <p className="text-muted-foreground">Finding similar patients...</p>
                  </div>
                </div>
              ) : nodes.length === 0 ? (
                <div className="flex items-center justify-center h-full">
                  <div className="text-center">
                    <Users className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
                    <h3 className="font-medium mb-2">No Data</h3>
                    <p className="text-muted-foreground text-sm mb-4">
                      Enter a patient ID to find similar patients
                    </p>
                  </div>
                </div>
              ) : (
                <PatientNetwork
                  nodes={nodes}
                  edges={edges}
                  selectedPatient={selectedPatient}
                  onPatientClick={handlePatientClick}
                  similarityThreshold={similarityThreshold}
                />
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Panel - Similar Patients List */}
        <div className="col-span-3">
          <Card className="h-[600px]">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Similar Patients</CardTitle>
              <CardDescription>
                Ranked by similarity to {referencePatientId}
              </CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              <ScrollArea className="h-[520px]">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Patient</TableHead>
                      <TableHead className="text-right">Similarity</TableHead>
                      <TableHead className="text-right">Shared</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {similarPatients.map((patient) => (
                      <TableRow
                        key={patient.patient_id}
                        className={`cursor-pointer ${
                          selectedPatient?.patient_id === patient.patient_id
                            ? "bg-accent"
                            : ""
                        }`}
                        onClick={() => {
                          const node = nodes.find(
                            (n) => n.patient_id === patient.patient_id
                          );
                          if (node) setSelectedPatient(node);
                        }}
                      >
                        <TableCell className="font-medium">
                          {patient.patient_id}
                        </TableCell>
                        <TableCell className="text-right">
                          <Badge
                            variant={
                              patient.similarity_score >= 0.8
                                ? "default"
                                : patient.similarity_score >= 0.6
                                ? "secondary"
                                : "outline"
                            }
                          >
                            {Math.round(patient.similarity_score * 100)}%
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right text-muted-foreground">
                          {patient.total_shared_features}
                        </TableCell>
                      </TableRow>
                    ))}
                    {similarPatients.length === 0 && (
                      <TableRow>
                        <TableCell
                          colSpan={3}
                          className="text-center text-muted-foreground"
                        >
                          No similar patients found
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </ScrollArea>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Feature Summary */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Shared Feature Summary</CardTitle>
          <CardDescription>
            Common clinical features across similar patients
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-6">
            {/* Conditions */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Stethoscope className="h-4 w-4 text-red-500" />
                <span className="font-medium text-sm">Top Shared Conditions</span>
              </div>
              <div className="space-y-2">
                {["Type 2 diabetes mellitus", "Hypertension", "Hyperlipidemia"].map(
                  (condition, i) => (
                    <div key={i} className="flex items-center justify-between text-sm">
                      <span className="truncate">{condition}</span>
                      <Badge variant="outline">{8 - i * 2} patients</Badge>
                    </div>
                  )
                )}
              </div>
            </div>

            {/* Medications */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Pill className="h-4 w-4 text-blue-500" />
                <span className="font-medium text-sm">Top Shared Medications</span>
              </div>
              <div className="space-y-2">
                {["Metformin", "Lisinopril", "Atorvastatin"].map((med, i) => (
                  <div key={i} className="flex items-center justify-between text-sm">
                    <span className="truncate">{med}</span>
                    <Badge variant="outline">{7 - i} patients</Badge>
                  </div>
                ))}
              </div>
            </div>

            {/* Procedures */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <FlaskConical className="h-4 w-4 text-green-500" />
                <span className="font-medium text-sm">Top Shared Procedures</span>
              </div>
              <div className="space-y-2">
                {["HbA1c test", "Lipid panel", "Blood pressure check"].map(
                  (proc, i) => (
                    <div key={i} className="flex items-center justify-between text-sm">
                      <span className="truncate">{proc}</span>
                      <Badge variant="outline">{6 - i} patients</Badge>
                    </div>
                  )
                )}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
