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
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Search,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Filter,
  Download,
  Users,
  Activity,
  Heart,
  Brain,
  Target,
  GitBranch,
  Eye,
  ArrowRight,
} from "lucide-react";

// Types
interface PatientNode {
  id: string;
  patientId: string;
  age: number;
  gender: "M" | "F";
  riskTier: "low" | "medium" | "high" | "critical";
  cluster: number;
  conditions: string[];
  primaryDiagnosis: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
}

interface SimilarityEdge {
  source: string;
  target: string;
  similarity: number;
  sharedConditions: string[];
}

interface ClusterInfo {
  id: number;
  name: string;
  color: string;
  patientCount: number;
  avgAge: number;
  commonConditions: string[];
  avgRiskScore: number;
}

// Generate mock patient data
const generatePatients = (): PatientNode[] => {
  const conditions = [
    "Type 2 Diabetes",
    "Hypertension",
    "CKD",
    "Heart Failure",
    "COPD",
    "Obesity",
    "Depression",
    "Osteoarthritis",
    "Atrial Fibrillation",
    "Dyslipidemia",
  ];

  const clusters: { conditions: string[]; ageRange: [number, number] }[] = [
    { conditions: ["Type 2 Diabetes", "Hypertension", "Obesity"], ageRange: [45, 65] },
    { conditions: ["Heart Failure", "Atrial Fibrillation", "CKD"], ageRange: [65, 85] },
    { conditions: ["COPD", "Hypertension", "Depression"], ageRange: [55, 75] },
    { conditions: ["Type 2 Diabetes", "CKD", "Dyslipidemia"], ageRange: [50, 70] },
    { conditions: ["Osteoarthritis", "Obesity", "Depression"], ageRange: [55, 75] },
  ];

  const patients: PatientNode[] = [];
  const riskTiers: PatientNode["riskTier"][] = ["low", "medium", "high", "critical"];

  for (let i = 0; i < 80; i++) {
    const cluster = i % clusters.length;
    const clusterInfo = clusters[cluster];
    const age = Math.floor(
      clusterInfo.ageRange[0] +
        Math.random() * (clusterInfo.ageRange[1] - clusterInfo.ageRange[0])
    );

    // Select 2-4 conditions, preferring cluster conditions
    const numConditions = 2 + Math.floor(Math.random() * 3);
    const patientConditions: string[] = [];
    clusterInfo.conditions.forEach((c) => {
      if (Math.random() > 0.3 && patientConditions.length < numConditions) {
        patientConditions.push(c);
      }
    });
    while (patientConditions.length < numConditions) {
      const randomCondition = conditions[Math.floor(Math.random() * conditions.length)];
      if (!patientConditions.includes(randomCondition)) {
        patientConditions.push(randomCondition);
      }
    }

    const riskIndex = Math.min(
      3,
      Math.floor(patientConditions.length / 2 + (age > 70 ? 1 : 0) + Math.random())
    );

    patients.push({
      id: `p-${i}`,
      patientId: `P-${10000 + i}`,
      age,
      gender: Math.random() > 0.5 ? "M" : "F",
      riskTier: riskTiers[riskIndex],
      cluster,
      conditions: patientConditions,
      primaryDiagnosis: patientConditions[0],
      x: (Math.random() - 0.5) * 600,
      y: (Math.random() - 0.5) * 400,
      vx: 0,
      vy: 0,
    });
  }

  return patients;
};

// Calculate similarity edges
const calculateSimilarity = (patients: PatientNode[]): SimilarityEdge[] => {
  const edges: SimilarityEdge[] = [];

  for (let i = 0; i < patients.length; i++) {
    for (let j = i + 1; j < patients.length; j++) {
      const p1 = patients[i];
      const p2 = patients[j];

      const sharedConditions = p1.conditions.filter((c) => p2.conditions.includes(c));
      const unionConditions = new Set([...p1.conditions, ...p2.conditions]);

      const jaccardSimilarity = sharedConditions.length / unionConditions.size;

      // Age similarity bonus
      const ageDiff = Math.abs(p1.age - p2.age);
      const ageSimilarity = Math.max(0, 1 - ageDiff / 30);

      // Combined similarity
      const similarity = jaccardSimilarity * 0.8 + ageSimilarity * 0.2;

      // Only keep edges with high enough similarity
      if (similarity > 0.4 && sharedConditions.length >= 2) {
        edges.push({
          source: p1.id,
          target: p2.id,
          similarity,
          sharedConditions,
        });
      }
    }
  }

  // Keep only top edges per patient to avoid clutter
  const patientEdgeCounts: Record<string, number> = {};
  return edges
    .sort((a, b) => b.similarity - a.similarity)
    .filter((edge) => {
      patientEdgeCounts[edge.source] = (patientEdgeCounts[edge.source] || 0) + 1;
      patientEdgeCounts[edge.target] = (patientEdgeCounts[edge.target] || 0) + 1;
      return patientEdgeCounts[edge.source] <= 5 && patientEdgeCounts[edge.target] <= 5;
    });
};

const clusterColors = [
  "#3b82f6", // blue
  "#22c55e", // green
  "#f59e0b", // amber
  "#8b5cf6", // purple
  "#ef4444", // red
];

const riskColors: Record<string, string> = {
  low: "#22c55e",
  medium: "#f59e0b",
  high: "#f97316",
  critical: "#ef4444",
};

export default function PatientSimilarityPage() {
  const initialPatients = useMemo(() => generatePatients(), []);
  const [patients, setPatients] = useState<PatientNode[]>(initialPatients);
  const [edges] = useState<SimilarityEdge[]>(() => calculateSimilarity(initialPatients));
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedPatient, setSelectedPatient] = useState<PatientNode | null>(null);
  const [colorBy, setColorBy] = useState<"cluster" | "risk">("cluster");
  const [minSimilarity, setMinSimilarity] = useState(0.5);
  const [showLabels, setShowLabels] = useState(false);
  const [focusedCluster, setFocusedCluster] = useState<number | null>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Cluster info
  const clusterInfo: ClusterInfo[] = useMemo(() => {
    const clusters: ClusterInfo[] = [];
    for (let i = 0; i < 5; i++) {
      const clusterPatients = patients.filter((p) => p.cluster === i);
      const avgAge =
        clusterPatients.reduce((sum, p) => sum + p.age, 0) / clusterPatients.length || 0;

      // Count conditions
      const conditionCounts: Record<string, number> = {};
      clusterPatients.forEach((p) => {
        p.conditions.forEach((c) => {
          conditionCounts[c] = (conditionCounts[c] || 0) + 1;
        });
      });
      const topConditions = Object.entries(conditionCounts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 3)
        .map(([c]) => c);

      const riskScores = { low: 1, medium: 2, high: 3, critical: 4 };
      const avgRiskScore =
        clusterPatients.reduce((sum, p) => sum + riskScores[p.riskTier], 0) /
          clusterPatients.length || 0;

      clusters.push({
        id: i,
        name: `Cluster ${i + 1}`,
        color: clusterColors[i],
        patientCount: clusterPatients.length,
        avgAge: Math.round(avgAge),
        commonConditions: topConditions,
        avgRiskScore,
      });
    }
    return clusters;
  }, [patients]);

  // Force simulation
  useEffect(() => {
    const simulate = () => {
      setPatients((prevPatients) => {
        const newPatients = prevPatients.map((p) => ({ ...p }));

        newPatients.forEach((patient, i) => {
          // Cluster center attraction
          const clusterCenterX = (patient.cluster - 2) * 150;
          const clusterCenterY = Math.sin(patient.cluster * 1.2) * 100;
          patient.vx += (clusterCenterX - patient.x) * 0.01;
          patient.vy += (clusterCenterY - patient.y) * 0.01;

          // Repulsion from other patients
          newPatients.forEach((other, j) => {
            if (i === j) return;
            const dx = patient.x - other.x;
            const dy = patient.y - other.y;
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;
            const force = -80 / dist;
            patient.vx += (dx / dist) * force * 0.1;
            patient.vy += (dy / dist) * force * 0.1;
          });

          // Attraction along similarity edges
          edges.forEach((edge) => {
            if (edge.similarity < minSimilarity) return;
            if (edge.source === patient.id || edge.target === patient.id) {
              const otherId = edge.source === patient.id ? edge.target : edge.source;
              const other = newPatients.find((p) => p.id === otherId);
              if (!other) return;

              const dx = other.x - patient.x;
              const dy = other.y - patient.y;
              patient.vx += dx * edge.similarity * 0.005;
              patient.vy += dy * edge.similarity * 0.005;
            }
          });

          // Damping
          patient.vx *= 0.9;
          patient.vy *= 0.9;
          patient.x += patient.vx;
          patient.y += patient.vy;
        });

        return newPatients;
      });

      requestAnimationFrame(simulate);
    };

    const animationId = requestAnimationFrame(simulate);
    return () => cancelAnimationFrame(animationId);
  }, [edges, minSimilarity]);

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

      // Filter edges
      const visibleEdges = edges.filter((e) => e.similarity >= minSimilarity);

      // Draw edges
      visibleEdges.forEach((edge) => {
        const source = patients.find((p) => p.id === edge.source);
        const target = patients.find((p) => p.id === edge.target);
        if (!source || !target) return;

        const isHighlighted =
          selectedPatient &&
          (edge.source === selectedPatient.id || edge.target === selectedPatient.id);

        ctx.beginPath();
        ctx.moveTo(source.x, source.y);
        ctx.lineTo(target.x, target.y);
        ctx.strokeStyle = "#94a3b8";
        ctx.globalAlpha = isHighlighted ? 0.6 : selectedPatient ? 0.05 : 0.15;
        ctx.lineWidth = edge.similarity * 3;
        ctx.stroke();
      });

      ctx.globalAlpha = 1;

      // Draw patients
      patients.forEach((patient) => {
        const matchesSearch =
          searchQuery === "" ||
          patient.patientId.toLowerCase().includes(searchQuery.toLowerCase()) ||
          patient.conditions.some((c) => c.toLowerCase().includes(searchQuery.toLowerCase()));

        const isInFocusedCluster = focusedCluster === null || patient.cluster === focusedCluster;

        const isHighlighted =
          !selectedPatient ||
          patient.id === selectedPatient.id ||
          edges.some(
            (e) =>
              e.similarity >= minSimilarity &&
              ((e.source === selectedPatient.id && e.target === patient.id) ||
                (e.target === selectedPatient.id && e.source === patient.id))
          );

        const radius = 6 + (patient.conditions.length - 2) * 2;
        const color =
          colorBy === "cluster" ? clusterColors[patient.cluster] : riskColors[patient.riskTier];

        ctx.globalAlpha = matchesSearch && isHighlighted && isInFocusedCluster ? 1 : 0.15;

        // Draw node
        ctx.beginPath();
        ctx.arc(patient.x, patient.y, radius, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();

        // Selection ring
        if (patient.id === selectedPatient?.id) {
          ctx.strokeStyle = "#000";
          ctx.lineWidth = 2;
          ctx.stroke();
        }

        // Gender indicator
        ctx.beginPath();
        ctx.arc(patient.x, patient.y, radius * 0.5, 0, Math.PI * 2);
        ctx.fillStyle = patient.gender === "M" ? "#3b82f6" : "#ec4899";
        ctx.globalAlpha = ctx.globalAlpha * 0.5;
        ctx.fill();

        // Label
        if (showLabels && matchesSearch) {
          ctx.globalAlpha = 1;
          ctx.font = "9px sans-serif";
          ctx.fillStyle = "#1f2937";
          ctx.textAlign = "center";
          ctx.fillText(patient.patientId, patient.x, patient.y + radius + 10);
        }
      });

      ctx.restore();
      requestAnimationFrame(render);
    };

    render();
  }, [patients, edges, zoom, pan, selectedPatient, colorBy, minSimilarity, showLabels, searchQuery, focusedCluster]);

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left - canvas.width / 2 - pan.x) / zoom;
    const y = (e.clientY - rect.top - canvas.height / 2 - pan.y) / zoom;

    const clickedPatient = patients.find((p) => {
      const radius = 6 + (p.conditions.length - 2) * 2;
      const dx = p.x - x;
      const dy = p.y - y;
      return Math.sqrt(dx * dx + dy * dy) < radius;
    });

    setSelectedPatient(clickedPatient || null);
  };

  const getSimilarPatients = (patient: PatientNode) => {
    return edges
      .filter((e) => e.source === patient.id || e.target === patient.id)
      .filter((e) => e.similarity >= minSimilarity)
      .map((e) => {
        const otherId = e.source === patient.id ? e.target : e.source;
        const other = patients.find((p) => p.id === otherId);
        return { patient: other!, similarity: e.similarity, sharedConditions: e.sharedConditions };
      })
      .sort((a, b) => b.similarity - a.similarity);
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Patient Similarity Network</h1>
          <p className="text-muted-foreground">
            Cluster patients by clinical features and explore similar cases
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
              <Users className="h-5 w-5 text-blue-500" />
              <div>
                <p className="text-sm text-muted-foreground">Total Patients</p>
                <p className="text-2xl font-bold">{patients.length}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <GitBranch className="h-5 w-5 text-green-500" />
              <div>
                <p className="text-sm text-muted-foreground">Clusters</p>
                <p className="text-2xl font-bold">{clusterInfo.length}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Activity className="h-5 w-5 text-orange-500" />
              <div>
                <p className="text-sm text-muted-foreground">Similarity Edges</p>
                <p className="text-2xl font-bold">
                  {edges.filter((e) => e.similarity >= minSimilarity).length}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Heart className="h-5 w-5 text-red-500" />
              <div>
                <p className="text-sm text-muted-foreground">High Risk</p>
                <p className="text-2xl font-bold">
                  {patients.filter((p) => p.riskTier === "high" || p.riskTier === "critical").length}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Brain className="h-5 w-5 text-purple-500" />
              <div>
                <p className="text-sm text-muted-foreground">Avg Age</p>
                <p className="text-2xl font-bold">
                  {Math.round(patients.reduce((s, p) => s + p.age, 0) / patients.length)}
                </p>
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
                  placeholder="Patient ID or condition..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-8"
                />
              </div>
            </div>

            {/* Color By */}
            <div className="space-y-2">
              <Label>Color By</Label>
              <Select value={colorBy} onValueChange={(v) => setColorBy(v as "cluster" | "risk")}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="cluster">Cluster</SelectItem>
                  <SelectItem value="risk">Risk Level</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Similarity Threshold */}
            <div className="space-y-2">
              <Label>Min Similarity: {(minSimilarity * 100).toFixed(0)}%</Label>
              <input
                type="range"
                min={30}
                max={80}
                value={minSimilarity * 100}
                onChange={(e) => setMinSimilarity(parseInt(e.target.value) / 100)}
                className="w-full"
              />
            </div>

            {/* Cluster Focus */}
            <div className="space-y-2">
              <Label>Focus Cluster</Label>
              <Select
                value={focusedCluster?.toString() || "all"}
                onValueChange={(v) => setFocusedCluster(v === "all" ? null : parseInt(v))}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Clusters</SelectItem>
                  {clusterInfo.map((c) => (
                    <SelectItem key={c.id} value={c.id.toString()}>
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full" style={{ backgroundColor: c.color }} />
                        {c.name}
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Display Options */}
            <div className="space-y-2">
              <label className="flex items-center gap-2">
                <Switch checked={showLabels} onCheckedChange={setShowLabels} />
                <span className="text-sm">Show Patient IDs</span>
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
                    setSelectedPatient(null);
                    setFocusedCluster(null);
                  }}
                >
                  <RotateCcw className="h-4 w-4" />
                </Button>
              </div>
            </div>

            {/* Legend */}
            <div className="space-y-2">
              <Label>{colorBy === "cluster" ? "Clusters" : "Risk Levels"}</Label>
              <div className="space-y-1">
                {colorBy === "cluster"
                  ? clusterInfo.map((c) => (
                      <div
                        key={c.id}
                        className="flex items-center gap-2 text-xs cursor-pointer hover:bg-slate-100 p-1 rounded"
                        onClick={() =>
                          setFocusedCluster(focusedCluster === c.id ? null : c.id)
                        }
                      >
                        <div
                          className="w-3 h-3 rounded-full"
                          style={{ backgroundColor: c.color }}
                        />
                        <span>
                          {c.name} ({c.patientCount})
                        </span>
                      </div>
                    ))
                  : Object.entries(riskColors).map(([tier, color]) => (
                      <div key={tier} className="flex items-center gap-2 text-xs">
                        <div className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
                        <span className="capitalize">{tier}</span>
                      </div>
                    ))}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Canvas */}
        <Card className="col-span-3">
          <CardHeader className="pb-2">
            <div className="flex justify-between items-center">
              <CardTitle>Network Visualization</CardTitle>
              {selectedPatient && (
                <Badge variant="outline">
                  {selectedPatient.patientId}
                  <button
                    className="ml-2 hover:text-red-500"
                    onClick={() => setSelectedPatient(null)}
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
              className="border rounded-lg bg-slate-50 cursor-pointer"
              onClick={handleCanvasClick}
            />
          </CardContent>
        </Card>
      </div>

      {/* Cluster Overview & Patient Details */}
      <Tabs defaultValue={selectedPatient ? "patient" : "clusters"}>
        <TabsList>
          <TabsTrigger value="clusters">Cluster Overview</TabsTrigger>
          <TabsTrigger value="patient" disabled={!selectedPatient}>
            Patient Details
          </TabsTrigger>
        </TabsList>

        <TabsContent value="clusters">
          <div className="grid grid-cols-5 gap-4">
            {clusterInfo.map((cluster) => (
              <Card
                key={cluster.id}
                className={`cursor-pointer transition-all ${
                  focusedCluster === cluster.id ? "ring-2 ring-primary" : ""
                }`}
                onClick={() => setFocusedCluster(focusedCluster === cluster.id ? null : cluster.id)}
              >
                <CardHeader className="pb-2">
                  <div className="flex items-center gap-2">
                    <div
                      className="w-4 h-4 rounded-full"
                      style={{ backgroundColor: cluster.color }}
                    />
                    <CardTitle className="text-sm">{cluster.name}</CardTitle>
                  </div>
                </CardHeader>
                <CardContent className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Patients</span>
                    <span className="font-medium">{cluster.patientCount}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Avg Age</span>
                    <span className="font-medium">{cluster.avgAge}</span>
                  </div>
                  <div className="text-sm">
                    <span className="text-muted-foreground">Risk Score</span>
                    <Progress value={cluster.avgRiskScore * 25} className="mt-1 h-2" />
                  </div>
                  <div className="text-xs text-muted-foreground">
                    <span className="font-medium">Common:</span>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {cluster.commonConditions.map((c) => (
                        <Badge key={c} variant="secondary" className="text-xs">
                          {c.split(" ")[0]}
                        </Badge>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="patient">
          {selectedPatient && (
            <Card>
              <CardHeader>
                <div className="flex justify-between items-start">
                  <div>
                    <CardTitle>{selectedPatient.patientId}</CardTitle>
                    <CardDescription>
                      {selectedPatient.age} years • {selectedPatient.gender === "M" ? "Male" : "Female"} •{" "}
                      <Badge className={`${riskColors[selectedPatient.riskTier]} text-white`}>
                        {selectedPatient.riskTier} risk
                      </Badge>
                    </CardDescription>
                  </div>
                  <Badge
                    variant="outline"
                    style={{ borderColor: clusterColors[selectedPatient.cluster] }}
                  >
                    Cluster {selectedPatient.cluster + 1}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-6">
                  <div>
                    <h4 className="font-medium mb-2">Conditions</h4>
                    <div className="flex flex-wrap gap-2">
                      {selectedPatient.conditions.map((c) => (
                        <Badge key={c} variant="secondary">
                          {c}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  <div>
                    <h4 className="font-medium mb-2">Similar Patients</h4>
                    <ScrollArea className="h-[200px]">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Patient</TableHead>
                            <TableHead>Similarity</TableHead>
                            <TableHead>Shared</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {getSimilarPatients(selectedPatient)
                            .slice(0, 10)
                            .map(({ patient, similarity, sharedConditions }) => (
                              <TableRow
                                key={patient.id}
                                className="cursor-pointer hover:bg-slate-50"
                                onClick={() => setSelectedPatient(patient)}
                              >
                                <TableCell>{patient.patientId}</TableCell>
                                <TableCell>
                                  <Badge variant="outline">
                                    {(similarity * 100).toFixed(0)}%
                                  </Badge>
                                </TableCell>
                                <TableCell className="text-xs">
                                  {sharedConditions.slice(0, 2).join(", ")}
                                  {sharedConditions.length > 2 && "..."}
                                </TableCell>
                              </TableRow>
                            ))}
                        </TableBody>
                      </Table>
                    </ScrollArea>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
