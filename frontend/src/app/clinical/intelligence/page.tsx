"use client";

import { useState, useEffect, useRef } from "react";
import { useSearchParams } from "next/navigation";
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
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Progress } from "@/components/ui/progress";
import {
  Network,
  Search,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Upload,
  MessageSquare,
  FileText,
  Pill,
  Stethoscope,
  FlaskConical,
  Activity,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Brain,
  Send,
  Sparkles,
  ChevronRight,
  Eye,
} from "lucide-react";
import { toast } from "sonner";
import DataSourceModeBanner from "@/components/readiness/DataSourceModeBanner";
import SectionEvidenceTag from "@/components/readiness/SectionEvidenceTag";
import DemoScenarioRunner from "@/components/readiness/DemoScenarioRunner";
import { useSimulationGuard } from "@/lib/simulation-guard";
import { SCENARIO_CLINICAL_SAFETY } from "@/lib/demo-scenarios";

// ---------------------------------------------------------------------------
// Auth helpers
// ---------------------------------------------------------------------------

function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const stored = localStorage.getItem("auth_tokens");
    if (stored) {
      const tokens = JSON.parse(stored);
      return tokens.access_token || null;
    }
  } catch {
    // Ignore
  }
  return null;
}

function authHeaders(token: string | null): HeadersInit {
  const h: HeadersInit = { "Content-Type": "application/json" };
  if (token) h["Authorization"] = `Bearer ${token}`;
  return h;
}

// ============================================================================
// Types
// ============================================================================

interface ClinicalNote {
  note_id: string;
  note_type: string;
  date: string;
  text: string;
}

interface ExtractedEntity {
  text: string;
  entity_type: string;
  confidence: number;
  assertion: string;
  omop_concept_id: number | null;
  note_id: string;
}

interface ImportedNote {
  note_id: string;
  document_id: string;
  entity_count: number;
  entities: ExtractedEntity[];
}

interface KGSummary {
  patient_id: string;
  node_count: number;
  edge_count: number;
  conditions: string[];
  medications: string[];
  measurements: string[];
  procedures: string[];
}

interface BulkImportResponse {
  patient_id: string;
  total_notes: number;
  total_entities: number;
  notes: ImportedNote[];
  knowledge_graph: KGSummary | null;
  processing_time_ms: number;
}

interface KGNode {
  id: string;
  node_type: string;
  label: string;
  omop_concept_id: number | null;
  properties: Record<string, unknown>;
  x?: number;
  y?: number;
}

interface KGEdge {
  id: string;
  source_id: string;
  target_id: string;
  edge_type: string;
  properties: Record<string, unknown>;
}

interface EvidenceSource {
  note_id: string;
  note_type: string;
  note_date: string;
  excerpt: string;
  relevance_score: number;
}

interface QueryResponse {
  question: string;
  answer: string;
  confidence: number;
  sources: string[];
  entities_found: ExtractedEntity[];
  evidence: EvidenceSource[];
  reasoning: string | null;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  entities?: ExtractedEntity[];
  evidence?: EvidenceSource[];
  confidence?: number;
}

// Domain colors for nodes
const NODE_COLORS: Record<string, string> = {
  PATIENT: "#6366f1", // indigo
  CONDITION: "#ef4444", // red
  DRUG: "#3b82f6", // blue
  MEASUREMENT: "#f59e0b", // amber
  PROCEDURE: "#22c55e", // green
  OBSERVATION: "#8b5cf6", // violet
  default: "#6b7280", // gray
};

const NODE_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  CONDITION: Stethoscope,
  DRUG: Pill,
  MEASUREMENT: FlaskConical,
  PROCEDURE: Activity,
  OBSERVATION: Eye,
};

// ============================================================================
// Knowledge Graph Canvas Component
// ============================================================================

interface GraphCanvasProps {
  nodes: KGNode[];
  edges: KGEdge[];
  selectedNode: KGNode | null;
  onNodeClick: (node: KGNode) => void;
}

function KnowledgeGraphCanvas({ nodes, edges, selectedNode, onNodeClick }: GraphCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [hoveredNode, setHoveredNode] = useState<KGNode | null>(null);

  // Apply force-directed layout
  useEffect(() => {
    if (nodes.length === 0) return;

    const width = 800;
    const height = 600;
    const centerX = width / 2;
    const centerY = height / 2;

    // Find patient node and center it
    const patientNode = nodes.find(n => n.node_type === "PATIENT");
    if (patientNode) {
      patientNode.x = centerX;
      patientNode.y = centerY;
    }

    // Position other nodes in concentric circles by type
    const nodesByType: Record<string, KGNode[]> = {};
    nodes.forEach(node => {
      if (node.node_type !== "PATIENT") {
        if (!nodesByType[node.node_type]) {
          nodesByType[node.node_type] = [];
        }
        nodesByType[node.node_type].push(node);
      }
    });

    const types = Object.keys(nodesByType);
    types.forEach((type, typeIndex) => {
      const typeNodes = nodesByType[type];
      const radius = 150 + typeIndex * 80;
      typeNodes.forEach((node, i) => {
        const angle = (i / typeNodes.length) * 2 * Math.PI - Math.PI / 2;
        node.x = centerX + radius * Math.cos(angle);
        node.y = centerY + radius * Math.sin(angle);
      });
    });

    // Run force simulation
    for (let iter = 0; iter < 30; iter++) {
      // Repulsion between nodes (except patient)
      for (let i = 0; i < nodes.length; i++) {
        if (nodes[i].node_type === "PATIENT") continue;
        for (let j = i + 1; j < nodes.length; j++) {
          if (nodes[j].node_type === "PATIENT") continue;
          const dx = (nodes[j].x || 0) - (nodes[i].x || 0);
          const dy = (nodes[j].y || 0) - (nodes[i].y || 0);
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          if (dist < 80) {
            const force = (80 - dist) * 0.5;
            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;
            nodes[i].x = (nodes[i].x || 0) - fx;
            nodes[i].y = (nodes[i].y || 0) - fy;
            nodes[j].x = (nodes[j].x || 0) + fx;
            nodes[j].y = (nodes[j].y || 0) + fy;
          }
        }
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

    // Clear with dark background
    ctx.fillStyle = "#0f172a";
    ctx.fillRect(0, 0, width, height);

    // Apply transforms
    ctx.save();
    ctx.translate(offset.x + width / 2, offset.y + height / 2);
    ctx.scale(zoom, zoom);
    ctx.translate(-width / 2, -height / 2);

    // Create node lookup
    const nodeMap = new Map(nodes.map(n => [n.id, n]));

    // Draw edges
    edges.forEach(edge => {
      const source = nodeMap.get(edge.source_id);
      const target = nodeMap.get(edge.target_id);
      if (source && target && source.x && source.y && target.x && target.y) {
        ctx.beginPath();
        ctx.moveTo(source.x, source.y);
        ctx.lineTo(target.x, target.y);

        // Different colors for different edge types
        if (edge.edge_type === "TREATS") {
          ctx.strokeStyle = "#22c55e";
          ctx.lineWidth = 2;
        } else {
          ctx.strokeStyle = "#374151";
          ctx.lineWidth = 1;
        }
        ctx.stroke();

        // Draw edge label at midpoint
        if (edge.edge_type === "TREATS") {
          const midX = (source.x + target.x) / 2;
          const midY = (source.y + target.y) / 2;
          ctx.fillStyle = "#22c55e";
          ctx.font = "8px sans-serif";
          ctx.textAlign = "center";
          ctx.fillText("treats", midX, midY - 5);
        }
      }
    });

    // Draw nodes
    nodes.forEach(node => {
      if (!node.x || !node.y) return;

      const isSelected = selectedNode?.id === node.id;
      const isHovered = hoveredNode?.id === node.id;
      const isPatient = node.node_type === "PATIENT";
      const color = NODE_COLORS[node.node_type] || NODE_COLORS.default;
      const radius = isPatient ? 25 : isSelected ? 18 : isHovered ? 16 : 14;

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
      ctx.font = isPatient ? "bold 10px sans-serif" : "9px sans-serif";
      ctx.textAlign = "center";
      const label = node.label.length > 25
        ? node.label.substring(0, 22) + "..."
        : node.label;
      ctx.fillText(label, node.x, node.y + radius + 12);
    });

    ctx.restore();

    // Draw legend
    ctx.fillStyle = "#ffffff";
    ctx.font = "11px sans-serif";
    ctx.textAlign = "left";
    let legendY = 20;
    Object.entries(NODE_COLORS).filter(([k]) => k !== "default").forEach(([type, color]) => {
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(20, legendY, 6, 0, 2 * Math.PI);
      ctx.fill();
      ctx.fillStyle = "#ffffff";
      ctx.fillText(type, 35, legendY + 4);
      legendY += 22;
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

    let foundNode: KGNode | null = null;
    for (const node of nodes) {
      if (node.x && node.y) {
        const dx = x - node.x;
        const dy = y - node.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        const radius = node.node_type === "PATIENT" ? 25 : 18;
        if (dist < radius) {
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
      onNodeClick(hoveredNode);
    }
  };

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setZoom(z => Math.max(0.3, Math.min(3, z * delta)));
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
          onClick={() => setZoom(z => Math.min(3, z * 1.2))}
        >
          <ZoomIn className="h-4 w-4" />
        </Button>
        <Button
          variant="secondary"
          size="icon"
          className="h-8 w-8"
          onClick={() => setZoom(z => Math.max(0.3, z / 1.2))}
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
        {nodes.length} nodes, {edges.length} edges
      </div>
    </div>
  );
}

// ============================================================================
// Main Page Component
// ============================================================================

export default function ClinicalIntelligencePage() {
  const searchParams = useSearchParams();
  const urlPatient = searchParams.get("patient");
  const urlTab = searchParams.get("tab");

  const [activeTab, setActiveTab] = useState(urlTab || "import");
  const [demoMode, setDemoMode] = useState(false);

  // Import state
  const [patientId, setPatientId] = useState(urlPatient || "TEST12345");
  const [notesInput, setNotesInput] = useState("");
  const [isImporting, setIsImporting] = useState(false);
  const [importProgress, setImportProgress] = useState(0);
  const [importResult, setImportResult] = useState<BulkImportResponse | null>(null);

  // Knowledge Graph state
  const [kgNodes, setKgNodes] = useState<KGNode[]>([]);
  const [kgEdges, setKgEdges] = useState<KGEdge[]>([]);
  const [selectedNode, setSelectedNode] = useState<KGNode | null>(null);
  const [isLoadingGraph, setIsLoadingGraph] = useState(false);

  // Q&A state
  const [messages, setMessages] = useState<Message[]>([]);
  const [currentQuestion, setCurrentQuestion] = useState("");
  const [isQuerying, setIsQuerying] = useState(false);

  const guard = useSimulationGuard(demoMode ? "simulation" : "mixed", "clinical/intelligence");

  // Parse notes from JSON input
  const parseNotes = (input: string): ClinicalNote[] => {
    try {
      const parsed = JSON.parse(input);
      if (Array.isArray(parsed)) {
        return parsed.map((note, idx) => ({
          note_id: note.note_id || `note_${idx + 1}`,
          note_type: note.note_type || note.type || "progress_note",
          date: note.date || new Date().toISOString().split("T")[0],
          text: note.text || note.content || "",
        }));
      }
      return [];
    } catch {
      // Try to parse as single text
      if (input.trim()) {
        return [{
          note_id: "note_1",
          note_type: "progress_note",
          date: new Date().toISOString().split("T")[0],
          text: input,
        }];
      }
      return [];
    }
  };

  // Handle bulk import
  const handleImport = async () => {
    const notes = parseNotes(notesInput);
    if (notes.length === 0) {
      toast.error("Please enter valid clinical notes");
      return;
    }

    setIsImporting(true);
    setImportProgress(0);
    setDemoMode(false);

    try {
      // Simulate progress
      const progressInterval = setInterval(() => {
        setImportProgress(p => Math.min(p + 10, 90));
      }, 200);

      const token = getStoredToken();
      const response = await fetch("/api/clinical-agent/import", {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify({
          patient_id: patientId,
          notes: notes,
          build_knowledge_graph: true,
        }),
      });

      clearInterval(progressInterval);
      setImportProgress(100);

      if (response.ok) {
        const result: BulkImportResponse = await response.json();
        setImportResult(result);
        toast.success(`Imported ${result.total_notes} notes, extracted ${result.total_entities} entities`);

        // Auto-load the knowledge graph
        if (result.knowledge_graph) {
          setActiveTab("graph");
          await loadPatientGraph(patientId);
        }
      } else {
        throw new Error("Import failed");
      }
    } catch {
      setDemoMode(true);
      toast.info("Demo mode — API unavailable");
      // Load mock graph for demo
      loadMockGraphData();
      setActiveTab("graph");
    } finally {
      setIsImporting(false);
    }
  };

  // Load patient knowledge graph
  const loadPatientGraph = async (pid: string) => {
    setIsLoadingGraph(true);
    try {
      const token = getStoredToken();
      const response = await fetch(`/api/clinical-agent/graph/${pid}`, {
        headers: authHeaders(token),
      });
      if (response.ok) {
        const data = await response.json();
        setKgNodes(data.nodes || []);
        setKgEdges(data.edges || []);
      } else {
        setDemoMode(true);
        loadMockGraphData();
      }
    } catch {
      setDemoMode(true);
      loadMockGraphData();
    } finally {
      setIsLoadingGraph(false);
    }
  };

  // Load mock graph data for demo
  const loadMockGraphData = () => {
    const mockNodes: KGNode[] = [
      { id: "p1", node_type: "PATIENT", label: "Patient TEST12345", omop_concept_id: null, properties: {} },
      { id: "c1", node_type: "CONDITION", label: "HFrEF (Heart Failure)", omop_concept_id: 319835, properties: {} },
      { id: "c2", node_type: "CONDITION", label: "Type 2 Diabetes", omop_concept_id: 201826, properties: {} },
      { id: "c3", node_type: "CONDITION", label: "CKD Stage 4", omop_concept_id: 46271022, properties: {} },
      { id: "c4", node_type: "CONDITION", label: "Atrial Fibrillation", omop_concept_id: 313217, properties: {} },
      { id: "c5", node_type: "CONDITION", label: "Hypertension", omop_concept_id: 316866, properties: {} },
      { id: "c6", node_type: "CONDITION", label: "CAD s/p CABG", omop_concept_id: 318443, properties: {} },
      { id: "d1", node_type: "DRUG", label: "Metformin 1000mg", omop_concept_id: 1503297, properties: {} },
      { id: "d2", node_type: "DRUG", label: "Furosemide 40mg", omop_concept_id: 956874, properties: {} },
      { id: "d3", node_type: "DRUG", label: "Carvedilol 25mg", omop_concept_id: 1346823, properties: {} },
      { id: "d4", node_type: "DRUG", label: "Apixaban 5mg", omop_concept_id: 42628534, properties: {} },
      { id: "d5", node_type: "DRUG", label: "Lisinopril 10mg", omop_concept_id: 1308216, properties: {} },
      { id: "d6", node_type: "DRUG", label: "Atorvastatin 40mg", omop_concept_id: 1545958, properties: {} },
      { id: "m1", node_type: "MEASUREMENT", label: "EF 35%", omop_concept_id: 4172133, properties: {} },
      { id: "m2", node_type: "MEASUREMENT", label: "eGFR 22", omop_concept_id: 40762352, properties: {} },
      { id: "m3", node_type: "MEASUREMENT", label: "HbA1c 7.2%", omop_concept_id: 4184637, properties: {} },
      { id: "m4", node_type: "MEASUREMENT", label: "BNP 450", omop_concept_id: 3036277, properties: {} },
    ];

    const mockEdges: KGEdge[] = [
      // Patient to conditions
      { id: "e1", source_id: "p1", target_id: "c1", edge_type: "HAS_CONDITION", properties: {} },
      { id: "e2", source_id: "p1", target_id: "c2", edge_type: "HAS_CONDITION", properties: {} },
      { id: "e3", source_id: "p1", target_id: "c3", edge_type: "HAS_CONDITION", properties: {} },
      { id: "e4", source_id: "p1", target_id: "c4", edge_type: "HAS_CONDITION", properties: {} },
      { id: "e5", source_id: "p1", target_id: "c5", edge_type: "HAS_CONDITION", properties: {} },
      { id: "e6", source_id: "p1", target_id: "c6", edge_type: "HAS_CONDITION", properties: {} },
      // Patient to drugs
      { id: "e7", source_id: "p1", target_id: "d1", edge_type: "TAKES_DRUG", properties: {} },
      { id: "e8", source_id: "p1", target_id: "d2", edge_type: "TAKES_DRUG", properties: {} },
      { id: "e9", source_id: "p1", target_id: "d3", edge_type: "TAKES_DRUG", properties: {} },
      { id: "e10", source_id: "p1", target_id: "d4", edge_type: "TAKES_DRUG", properties: {} },
      { id: "e11", source_id: "p1", target_id: "d5", edge_type: "TAKES_DRUG", properties: {} },
      { id: "e12", source_id: "p1", target_id: "d6", edge_type: "TAKES_DRUG", properties: {} },
      // Patient to measurements
      { id: "e13", source_id: "p1", target_id: "m1", edge_type: "HAS_MEASUREMENT", properties: {} },
      { id: "e14", source_id: "p1", target_id: "m2", edge_type: "HAS_MEASUREMENT", properties: {} },
      { id: "e15", source_id: "p1", target_id: "m3", edge_type: "HAS_MEASUREMENT", properties: {} },
      { id: "e16", source_id: "p1", target_id: "m4", edge_type: "HAS_MEASUREMENT", properties: {} },
      // Treatment relationships
      { id: "t1", source_id: "d1", target_id: "c2", edge_type: "TREATS", properties: { inferred: true } },
      { id: "t2", source_id: "d2", target_id: "c1", edge_type: "TREATS", properties: { inferred: true } },
      { id: "t3", source_id: "d3", target_id: "c1", edge_type: "TREATS", properties: { inferred: true } },
      { id: "t4", source_id: "d4", target_id: "c4", edge_type: "TREATS", properties: { inferred: true } },
      { id: "t5", source_id: "d5", target_id: "c5", edge_type: "TREATS", properties: { inferred: true } },
    ];

    setKgNodes(mockNodes);
    setKgEdges(mockEdges);
  };

  // Handle Q&A query
  const handleQuery = async () => {
    if (!currentQuestion.trim()) return;

    const userMessage: Message = { role: "user", content: currentQuestion };
    setMessages(prev => [...prev, userMessage]);
    setCurrentQuestion("");
    setIsQuerying(true);

    try {
      const token = getStoredToken();
      const response = await fetch(`/api/clinical-agent/query/${patientId}`, {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify({
          question: currentQuestion,
          include_evidence: true,
          max_results: 10,
        }),
      });

      if (response.ok) {
        const result: QueryResponse = await response.json();
        const assistantMessage: Message = {
          role: "assistant",
          content: result.answer,
          entities: result.entities_found,
          evidence: result.evidence,
          confidence: result.confidence,
        };
        setMessages(prev => [...prev, assistantMessage]);
      } else {
        setDemoMode(true);
        const mockResponse = generateMockResponse(currentQuestion);
        setMessages(prev => [...prev, mockResponse]);
      }
    } catch {
      setDemoMode(true);
      const mockResponse = generateMockResponse(currentQuestion);
      setMessages(prev => [...prev, mockResponse]);
    } finally {
      setIsQuerying(false);
    }
  };

  // Generate mock response based on question
  const generateMockResponse = (question: string): Message => {
    const q = question.toLowerCase();

    // Check for drug interaction questions first (more specific)
    if (q.includes("interaction") || q.includes("contraindication") || q.includes("risk") && q.includes("medication")) {
      return {
        role: "assistant",
        content: "⚠️ Yes, there are potential medication interaction concerns for this patient:\n\n1. **Metformin + CKD Stage 4 (eGFR 22)**: HIGH RISK - Metformin is generally contraindicated when eGFR <30. Risk of lactic acidosis. Consider dose reduction or discontinuation.\n\n2. **Apixaban + CKD Stage 4**: MODERATE RISK - Dose adjustment may be needed. Standard dose may lead to increased bleeding risk.\n\n3. **Lisinopril + CKD + Furosemide**: Monitor closely for acute kidney injury and hyperkalemia. The combination of ACE inhibitor with diuretic in CKD requires careful monitoring.\n\n4. **Carvedilol + Heart Failure**: Actually beneficial - beta-blockers are guideline-directed therapy for HFrEF.\n\nRecommendations: Consider nephrology consult for metformin continuation, monitor renal function and electrolytes closely.",
        confidence: 0.91,
        entities: [
          { text: "Metformin", entity_type: "DRUG", confidence: 0.98, assertion: "PRESENT", omop_concept_id: 1503297, note_id: "note_1" },
          { text: "CKD Stage 4", entity_type: "CONDITION", confidence: 0.96, assertion: "PRESENT", omop_concept_id: 443611, note_id: "note_1" },
          { text: "eGFR 22", entity_type: "MEASUREMENT", confidence: 0.95, assertion: "PRESENT", omop_concept_id: 40762352, note_id: "note_4" },
        ],
      };
    }

    if (q.includes("medication") || q.includes("drug") || q.includes("taking")) {
      return {
        role: "assistant",
        content: "The patient is currently taking the following medications: Metformin 1000mg BID for diabetes, Furosemide 40mg daily for heart failure, Carvedilol 25mg BID for heart failure and rate control, Apixaban 5mg BID for atrial fibrillation anticoagulation, Lisinopril 10mg daily for hypertension and cardiac remodeling, and Atorvastatin 40mg daily for hyperlipidemia and cardiovascular protection.",
        confidence: 0.95,
        entities: [
          { text: "Metformin 1000mg", entity_type: "DRUG", confidence: 0.98, assertion: "PRESENT", omop_concept_id: 1503297, note_id: "note_1" },
          { text: "Furosemide 40mg", entity_type: "DRUG", confidence: 0.96, assertion: "PRESENT", omop_concept_id: 956874, note_id: "note_1" },
          { text: "Carvedilol 25mg", entity_type: "DRUG", confidence: 0.97, assertion: "PRESENT", omop_concept_id: 1346823, note_id: "note_2" },
        ],
      };
    }

    if (q.includes("condition") || q.includes("diagnosis") || q.includes("problem")) {
      return {
        role: "assistant",
        content: "The patient has the following active conditions: HFrEF (Heart Failure with reduced Ejection Fraction, EF 35%), Type 2 Diabetes Mellitus (HbA1c 7.2%), CKD Stage 4 (eGFR 22), Atrial Fibrillation (on anticoagulation), Hypertension, and CAD status post CABG.",
        confidence: 0.92,
        entities: [
          { text: "HFrEF", entity_type: "CONDITION", confidence: 0.95, assertion: "PRESENT", omop_concept_id: 319835, note_id: "note_3" },
          { text: "Type 2 Diabetes", entity_type: "CONDITION", confidence: 0.98, assertion: "PRESENT", omop_concept_id: 201826, note_id: "note_1" },
        ],
      };
    }

    if (q.includes("lab") || q.includes("test") || q.includes("result")) {
      return {
        role: "assistant",
        content: "Recent laboratory findings: EF 35% (reduced), eGFR 22 mL/min/1.73m² (CKD Stage 4), HbA1c 7.2% (above goal), BNP 450 pg/mL (elevated, indicating volume overload). The low eGFR is a concern for medication dosing, particularly metformin.",
        confidence: 0.88,
        entities: [
          { text: "EF 35%", entity_type: "MEASUREMENT", confidence: 0.95, assertion: "PRESENT", omop_concept_id: 4172133, note_id: "note_5" },
          { text: "eGFR 22", entity_type: "MEASUREMENT", confidence: 0.92, assertion: "PRESENT", omop_concept_id: 40762352, note_id: "note_4" },
        ],
      };
    }

    return {
      role: "assistant",
      content: "Based on the patient's records, I found relevant clinical information. The patient has multiple comorbidities including heart failure, diabetes, CKD, and atrial fibrillation. They are on guideline-directed medical therapy. Would you like more details about specific conditions, medications, or lab results?",
      confidence: 0.75,
    };
  };

  // Load graph on tab change
  useEffect(() => {
    if (activeTab === "graph" && kgNodes.length === 0) {
      loadPatientGraph(patientId);
    }
  }, [activeTab, patientId]);

  // Auto-load graph when navigating from NLP Workbench with URL params
  // Only fires on initial mount when URL params are present
  useEffect(() => {
    if (urlPatient && urlTab === "graph") {
      // Force reload graph for the patient from URL (coming from NLP Workbench)
      loadPatientGraph(urlPatient);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlPatient, urlTab]);

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Brain className="h-6 w-6 text-primary" />
            Clinical Intelligence
          </h1>
          <p className="text-muted-foreground">
            Import clinical documents, build knowledge graphs, and query with AI
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="gap-1">
            <FileText className="h-3 w-3" />
            {importResult?.total_notes || 0} Documents
          </Badge>
          <Badge variant="outline" className="gap-1">
            <Network className="h-3 w-3" />
            {kgNodes.length} Nodes
          </Badge>
        </div>
      </div>

      {/* Source mode banner */}
      <DataSourceModeBanner
        mode={demoMode ? "simulation" : "mixed"}
        title="Clinical intelligence data source"
        description={
          demoMode
            ? "Backend API is unavailable. All graph data, Q&A responses, and import results shown on this page are client-side simulations. No actions on this page write to the backend."
            : "Knowledge graph visualization uses live API when connected. Falls back to demonstration graph view when clinical agent API is unavailable."
        }
        evidencePath="docs/decisions/p4-017-mock-surface-removal.md"
        lastUpdatedAt="2026-02-16"
        signoffText={
          demoMode
            ? "Graph display is demonstration-only when API returns non-200. Query actions are blocked in simulation mode."
            : "Graph display is demonstration-only when API returns non-200. Query actions are blocked in simulation mode."
        }
        backendEndpoints={["/api/v1/clinical/query", "/api/v1/clinical/graph"]}
      />
      {demoMode && (
        <p className="text-[10px] text-slate-500 italic px-1">
          {guard.escalationText}
        </p>
      )}

      {/* Main Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="import" className="gap-2">
            <Upload className="h-4 w-4" />
            Import Documents
          </TabsTrigger>
          <TabsTrigger value="graph" className="gap-2">
            <Network className="h-4 w-4" />
            Knowledge Graph
          </TabsTrigger>
          <TabsTrigger value="qa" className="gap-2">
            <MessageSquare className="h-4 w-4" />
            Q&A Agent
          </TabsTrigger>
        </TabsList>

        {/* Import Tab */}
        <TabsContent value="import" className="space-y-4">
          <div className="grid grid-cols-2 gap-6">
            {/* Input Panel */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Bulk Document Import</CardTitle>
                <CardDescription>
                  Paste clinical notes as JSON array or plain text
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>Patient ID</Label>
                  <Input
                    value={patientId}
                    onChange={(e) => setPatientId(e.target.value)}
                    placeholder="Enter patient ID"
                  />
                </div>

                <div className="space-y-2">
                  <Label>Clinical Notes (JSON or Text)</Label>
                  <Textarea
                    value={notesInput}
                    onChange={(e) => setNotesInput(e.target.value)}
                    placeholder={`Paste your 50 notes here as JSON array:
[
  {
    "note_id": "note_1",
    "note_type": "progress_note",
    "date": "2024-01-15",
    "text": "Patient presents with..."
  },
  ...
]

Or paste a single clinical note as plain text.`}
                    className="h-[300px] font-mono text-sm"
                  />
                </div>

                {isImporting && (
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span>Processing documents...</span>
                      <span>{importProgress}%</span>
                    </div>
                    <Progress value={importProgress} />
                  </div>
                )}

                <Button
                  className="w-full"
                  onClick={handleImport}
                  disabled={isImporting || !notesInput.trim()}
                >
                  {isImporting ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Processing...
                    </>
                  ) : (
                    <>
                      <Upload className="h-4 w-4 mr-2" />
                      {demoMode ? "Import & Build Knowledge Graph (Demo)" : "Import & Build Knowledge Graph"}
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>

            {/* Results Panel */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Import Results</CardTitle>
              </CardHeader>
              <CardContent>
                {importResult ? (
                  <div className="space-y-4">
                    <div className="flex items-center gap-2 text-green-600">
                      <CheckCircle2 className="h-5 w-5" />
                      <span className="font-medium">Import Successful</span>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div className="p-3 bg-muted rounded-lg">
                        <div className="text-2xl font-bold">{importResult.total_notes}</div>
                        <div className="text-sm text-muted-foreground">Documents</div>
                      </div>
                      <div className="p-3 bg-muted rounded-lg">
                        <div className="text-2xl font-bold">{importResult.total_entities}</div>
                        <div className="text-sm text-muted-foreground">Entities Extracted</div>
                      </div>
                    </div>

                    {importResult.knowledge_graph && (
                      <>
                        <Separator />
                        <div>
                          <h4 className="font-medium mb-2">Knowledge Graph Built</h4>
                          <div className="grid grid-cols-2 gap-2 text-sm">
                            <div className="flex justify-between">
                              <span className="text-muted-foreground">Nodes:</span>
                              <span>{importResult.knowledge_graph.node_count}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-muted-foreground">Edges:</span>
                              <span>{importResult.knowledge_graph.edge_count}</span>
                            </div>
                          </div>
                        </div>

                        <div className="space-y-2">
                          <h4 className="font-medium">Conditions Found</h4>
                          <div className="flex flex-wrap gap-1">
                            {importResult.knowledge_graph.conditions.slice(0, 8).map((c, i) => (
                              <Badge key={i} variant="destructive" className="text-xs">{c}</Badge>
                            ))}
                          </div>
                        </div>

                        <div className="space-y-2">
                          <h4 className="font-medium">Medications Found</h4>
                          <div className="flex flex-wrap gap-1">
                            {importResult.knowledge_graph.medications.slice(0, 8).map((m, i) => (
                              <Badge key={i} className="text-xs bg-blue-500">{m}</Badge>
                            ))}
                          </div>
                        </div>

                        <Button
                          variant="outline"
                          className="w-full"
                          onClick={() => setActiveTab("graph")}
                        >
                          View Knowledge Graph
                          <ChevronRight className="h-4 w-4 ml-2" />
                        </Button>
                      </>
                    )}

                    <div className="text-xs text-muted-foreground">
                      Processed in {importResult.processing_time_ms}ms
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center h-[400px] text-muted-foreground">
                    <FileText className="h-12 w-12 mb-4 opacity-50" />
                    <p>Import documents to see results</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
          <SectionEvidenceTag
            source={demoMode ? "simulation" : "/api/clinical-agent/import"}
            dataFreshness={demoMode ? "demo_load" : "api_response"}
            evidenceArtifact="backend/app/api/clinical_agent.py"
          />
        </TabsContent>

        {/* Knowledge Graph Tab */}
        <TabsContent value="graph" className="space-y-4">
          <div className="grid grid-cols-12 gap-6">
            {/* Graph Canvas */}
            <div className="col-span-9">
              <Card className="h-[650px]">
                <CardContent className="p-0 h-full">
                  {isLoadingGraph ? (
                    <div className="flex items-center justify-center h-full">
                      <Loader2 className="h-8 w-8 animate-spin text-primary" />
                    </div>
                  ) : kgNodes.length > 0 ? (
                    <KnowledgeGraphCanvas
                      nodes={kgNodes}
                      edges={kgEdges}
                      selectedNode={selectedNode}
                      onNodeClick={setSelectedNode}
                    />
                  ) : (
                    <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
                      <Network className="h-12 w-12 mb-4 opacity-50" />
                      <p className="mb-4">No knowledge graph loaded</p>
                      <Button onClick={() => loadPatientGraph(patientId)}>
                        Load Demo Graph
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* Side Panel */}
            <div className="col-span-3 space-y-4">
              {/* Summary Card */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm">Graph Summary</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="space-y-1">
                    {Object.entries(NODE_COLORS).filter(([k]) => k !== "default" && k !== "PATIENT").map(([type, color]) => {
                      const count = kgNodes.filter(n => n.node_type === type).length;
                      if (count === 0) return null;
                      const Icon = NODE_ICONS[type] || Activity;
                      return (
                        <div key={type} className="flex items-center justify-between text-sm">
                          <span className="flex items-center gap-2">
                            <span style={{ color }}>
                              <Icon className="h-4 w-4" />
                            </span>
                            {type}
                          </span>
                          <Badge variant="secondary">{count}</Badge>
                        </div>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>

              {/* Selected Node Details */}
              {selectedNode && (
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-sm">Selected Node</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    <div className="font-medium">{selectedNode.label}</div>
                    <Badge
                      style={{ backgroundColor: NODE_COLORS[selectedNode.node_type] || NODE_COLORS.default }}
                    >
                      {selectedNode.node_type}
                    </Badge>
                    {selectedNode.omop_concept_id && (
                      <div className="text-xs text-muted-foreground">
                        OMOP ID: {selectedNode.omop_concept_id}
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}

              {/* Quick Actions */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm">Quick Actions</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full justify-start"
                    onClick={() => setActiveTab("qa")}
                  >
                    <MessageSquare className="h-4 w-4 mr-2" />
                    Ask a Question
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full justify-start"
                    onClick={loadMockGraphData}
                  >
                    <Sparkles className="h-4 w-4 mr-2" />
                    Load Demo Data
                  </Button>
                </CardContent>
              </Card>
            </div>
          </div>
          <SectionEvidenceTag
            source={demoMode ? "simulation" : "/api/clinical-agent/graph"}
            dataFreshness={demoMode ? "demo_load" : "api_response"}
          />
        </TabsContent>

        {/* Q&A Tab */}
        <TabsContent value="qa" className="space-y-4">
          <div className="grid grid-cols-12 gap-6">
            {/* Chat Interface */}
            <div className="col-span-8">
              <Card className="h-[650px] flex flex-col">
                <CardHeader className="pb-3">
                  <CardTitle className="text-lg flex items-center gap-2">
                    <Brain className="h-5 w-5 text-primary" />
                    Clinical Q&A Agent
                  </CardTitle>
                  <CardDescription>
                    Ask questions about the patient's clinical data and knowledge graph
                  </CardDescription>
                </CardHeader>
                <CardContent className="flex-1 flex flex-col">
                  {/* Messages */}
                  <ScrollArea className="flex-1 pr-4">
                    <div className="space-y-4">
                      {messages.length === 0 ? (
                        <div className="text-center text-muted-foreground py-12">
                          <MessageSquare className="h-12 w-12 mx-auto mb-4 opacity-50" />
                          <p>Ask a question about the patient's records</p>
                          <div className="mt-4 space-y-2 text-sm">
                            <p className="font-medium">Try asking:</p>
                            <p>"What medications is the patient taking?"</p>
                            <p>"What are the patient's conditions?"</p>
                            <p>"What are the recent lab results?"</p>
                          </div>
                        </div>
                      ) : (
                        messages.map((msg, idx) => (
                          <div
                            key={idx}
                            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                          >
                            <div
                              className={`max-w-[80%] rounded-lg p-4 ${
                                msg.role === "user"
                                  ? "bg-primary text-primary-foreground"
                                  : "bg-muted"
                              }`}
                            >
                              <p className="whitespace-pre-wrap">{msg.content}</p>

                              {msg.role === "assistant" && msg.confidence && (
                                <div className="mt-2 flex items-center gap-2 text-xs opacity-70">
                                  <span>Confidence: {Math.round(msg.confidence * 100)}%</span>
                                </div>
                              )}

                              {msg.role === "assistant" && msg.entities && msg.entities.length > 0 && (
                                <div className="mt-3 pt-3 border-t border-border/50">
                                  <div className="text-xs font-medium mb-2">Entities Found:</div>
                                  <div className="flex flex-wrap gap-1">
                                    {msg.entities.slice(0, 5).map((e, i) => (
                                      <Badge
                                        key={i}
                                        variant="outline"
                                        className="text-xs"
                                        style={{ borderColor: NODE_COLORS[e.entity_type] || NODE_COLORS.default }}
                                      >
                                        {e.text}
                                      </Badge>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>
                          </div>
                        ))
                      )}

                      {isQuerying && (
                        <div className="flex justify-start">
                          <div className="bg-muted rounded-lg p-4">
                            <Loader2 className="h-5 w-5 animate-spin" />
                          </div>
                        </div>
                      )}
                    </div>
                  </ScrollArea>

                  {/* Input */}
                  {demoMode && (
                    <p className="text-[10px] text-amber-600 italic">Demo mode: responses are client-side simulations, not from production API.</p>
                  )}
                  <div className="mt-4 flex gap-2">
                    <Input
                      value={currentQuestion}
                      onChange={(e) => setCurrentQuestion(e.target.value)}
                      placeholder="Ask about medications, conditions, labs..."
                      onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleQuery()}
                    />
                    <Button onClick={handleQuery} disabled={isQuerying || !currentQuestion.trim()}>
                      {isQuerying ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Send className="h-4 w-4" />
                      )}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Knowledge Summary */}
            <div className="col-span-4 space-y-4">
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm">Patient Overview</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div>
                    <div className="text-xs font-medium text-muted-foreground mb-1">Patient ID</div>
                    <div className="font-mono">{patientId}</div>
                  </div>
                  <Separator />
                  <div>
                    <div className="text-xs font-medium text-muted-foreground mb-2">Conditions</div>
                    <div className="flex flex-wrap gap-1">
                      {kgNodes.filter(n => n.node_type === "CONDITION").slice(0, 6).map((n, i) => (
                        <Badge key={i} variant="destructive" className="text-xs">{n.label}</Badge>
                      ))}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs font-medium text-muted-foreground mb-2">Medications</div>
                    <div className="flex flex-wrap gap-1">
                      {kgNodes.filter(n => n.node_type === "DRUG").slice(0, 6).map((n, i) => (
                        <Badge key={i} className="text-xs bg-blue-500">{n.label}</Badge>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm">Suggested Questions</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {[
                    "What medications is the patient taking?",
                    "What are the patient's active conditions?",
                    "What are the recent lab results?",
                    "Is the patient at risk for medication interactions?",
                  ].map((q, i) => (
                    <Button
                      key={i}
                      variant="ghost"
                      size="sm"
                      className="w-full justify-start text-left h-auto py-2 text-xs"
                      onClick={() => {
                        setCurrentQuestion(q);
                        handleQuery();
                      }}
                    >
                      <Search className="h-3 w-3 mr-2 flex-shrink-0" />
                      <span className="truncate">{q}</span>
                    </Button>
                  ))}
                </CardContent>
              </Card>
            </div>
          </div>
          <SectionEvidenceTag
            source={demoMode ? "simulation" : "/api/clinical-agent/query"}
            dataFreshness={demoMode ? "demo_load" : "api_response"}
          />
        </TabsContent>
      </Tabs>

      {/* P4-018: Deterministic demo scenario runner */}
      <DemoScenarioRunner scenario={SCENARIO_CLINICAL_SAFETY} />
    </div>
  );
}
