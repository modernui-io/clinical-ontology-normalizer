"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import dynamic from "next/dynamic";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { getPatientGraph, buildPatientGraph, PatientGraph, GraphNode, GraphEdge } from "@/lib/api";
import { toast } from "sonner";
import DataSourceModeBanner from "@/components/readiness/DataSourceModeBanner";
import { useAuth } from "@/hooks/use-auth";

// Dynamic import for D3 visualization (client-side only)
const KnowledgeGraph = dynamic(() => import("@/components/KnowledgeGraph"), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-[600px] bg-slate-950 rounded-xl">
      <div className="text-slate-400">Loading visualization...</div>
    </div>
  ),
});

const NODE_TYPE_COLORS: Record<string, string> = {
  patient: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-200",
  condition: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-200",
  drug: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-200",
  measurement: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-200",
  procedure: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-200",
  observation: "bg-gray-100 text-gray-800 dark:bg-gray-700/30 dark:text-gray-200",
};

const NODE_TYPE_ICONS: Record<string, string> = {
  patient: "👤",
  condition: "🩺",
  drug: "💊",
  measurement: "📊",
  procedure: "🔧",
  observation: "👁️",
};

const EDGE_TYPE_LABELS: Record<string, string> = {
  has_condition: "Has Condition",
  takes_drug: "Takes Drug",
  has_measurement: "Has Measurement",
  has_procedure: "Has Procedure",
  has_observation: "Has Observation",
  condition_treated_by: "Treated By",
  drug_treats: "Treats",
};

interface NodeStats {
  type: string;
  count: number;
  connections: number;
  avgConnections: number;
}

export default function PatientGraphPage() {
  const params = useParams();
  const { isDemo, isLoading: isAuthLoading } = useAuth();
  const patientId = params.patientId as string;
  const [graph, setGraph] = useState<PatientGraph | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isBuilding, setIsBuilding] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [dataMode, setDataMode] = useState<"live" | "simulation">("live");

  const fetchGraph = useCallback(async () => {
    // In demo mode, skip API calls and load demo data directly
    if (isDemo) {
      try {
        const { DEMO_PATIENT_GRAPHS } = await import("@/lib/demo-data");
        const demoGraph = DEMO_PATIENT_GRAPHS?.[patientId];
        if (demoGraph) {
          setGraph(demoGraph);
          return;
        }
      } catch {
        // Demo data module not available
      }
      setError("No demo graph data found for this patient.");
      return;
    }

    try {
      const patientGraph = await getPatientGraph(patientId);
      setGraph(patientGraph);
      setError(null);
    } catch (err) {
      console.error("Failed to fetch graph:", err);
      // Fall back to a demo graph for the patient
      try {
        const { DEMO_PATIENT_GRAPHS } = await import("@/lib/demo-data");
        const demoGraph = DEMO_PATIENT_GRAPHS?.[patientId];
        if (demoGraph) {
          setGraph(demoGraph);
          setDataMode("simulation");
          return;
        }
      } catch {
        // Demo data module not available yet
      }
      setError("No graph data found for this patient. Try building the graph.");
    }
  }, [patientId, isDemo]);

  useEffect(() => {
    if (!patientId || isAuthLoading) return;
    if (isDemo) setDataMode("simulation");
    fetchGraph();
  }, [patientId, fetchGraph, isAuthLoading, isDemo]);

  const handleBuildGraph = async () => {
    setIsBuilding(true);
    try {
      const newGraph = await buildPatientGraph(patientId);
      setGraph(newGraph);
      setError(null);
      toast.success("Graph built successfully");
    } catch (err) {
      console.error("Failed to build graph:", err);
      toast.error("Failed to build graph. Make sure patient has clinical facts.");
    } finally {
      setIsBuilding(false);
    }
  };

  // Group nodes by type for the visualization
  const nodesByType = useMemo(() => {
    if (!graph) return {};
    return graph.nodes.reduce(
      (acc, node) => {
        const type = node.node_type;
        if (!acc[type]) acc[type] = [];
        acc[type].push(node);
        return acc;
      },
      {} as Record<string, GraphNode[]>
    );
  }, [graph]);

  // Calculate node statistics
  const nodeStats = useMemo((): NodeStats[] => {
    if (!graph) return [];
    const stats: Record<string, NodeStats> = {};

    for (const node of graph.nodes) {
      if (!stats[node.node_type]) {
        stats[node.node_type] = {
          type: node.node_type,
          count: 0,
          connections: 0,
          avgConnections: 0,
        };
      }
      stats[node.node_type].count++;
    }

    for (const edge of graph.edges) {
      const sourceNode = graph.nodes.find((n) => n.id === edge.source_node_id);
      const targetNode = graph.nodes.find((n) => n.id === edge.target_node_id);
      if (sourceNode && stats[sourceNode.node_type]) {
        stats[sourceNode.node_type].connections++;
      }
      if (targetNode && stats[targetNode.node_type]) {
        stats[targetNode.node_type].connections++;
      }
    }

    for (const type in stats) {
      stats[type].avgConnections = stats[type].count > 0
        ? Math.round((stats[type].connections / stats[type].count) * 10) / 10
        : 0;
    }

    return Object.values(stats).sort((a, b) => b.count - a.count);
  }, [graph]);

  // Find highly connected nodes
  const hubNodes = useMemo(() => {
    if (!graph) return [];

    const connectionCounts = new Map<string, number>();
    for (const edge of graph.edges) {
      connectionCounts.set(
        edge.source_node_id,
        (connectionCounts.get(edge.source_node_id) || 0) + 1
      );
      connectionCounts.set(
        edge.target_node_id,
        (connectionCounts.get(edge.target_node_id) || 0) + 1
      );
    }

    return graph.nodes
      .map((node) => ({
        node,
        connections: connectionCounts.get(node.id) || 0,
      }))
      .sort((a, b) => b.connections - a.connections)
      .slice(0, 10);
  }, [graph]);

  // Filter nodes by search
  const filteredNodes = useMemo(() => {
    if (!graph) return [];
    let nodes = graph.nodes;

    if (selectedType) {
      nodes = nodes.filter((n) => n.node_type === selectedType);
    }

    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      nodes = nodes.filter(
        (n) =>
          n.label.toLowerCase().includes(query) ||
          n.omop_concept_id?.toString().includes(query)
      );
    }

    return nodes;
  }, [graph, selectedType, searchQuery]);

  // Find node label by ID
  const getNodeLabel = (nodeId: string) => {
    const node = graph?.nodes.find((n) => n.id === nodeId);
    return node?.label || nodeId;
  };

  // Get edge type distribution
  const edgeTypeDistribution = useMemo(() => {
    if (!graph) return [];
    const counts: Record<string, number> = {};
    for (const edge of graph.edges) {
      counts[edge.edge_type] = (counts[edge.edge_type] || 0) + 1;
    }
    return Object.entries(counts)
      .map(([type, count]) => ({ type, count }))
      .sort((a, b) => b.count - a.count);
  }, [graph]);

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900">
      <header className="border-b bg-white dark:bg-zinc-950">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link href="/patients" className="text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100">
                &larr; Patients
              </Link>
              <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
                Patient {patientId} - Knowledge Graph
              </h1>
            </div>
            <div className="flex gap-2">
              <Link href={`/patients/${patientId}/facts`}>
                <Button variant="outline">Clinical Facts</Button>
              </Link>
              <Link href={`/patients/${patientId}/timeline`}>
                <Button variant="outline">Timeline</Button>
              </Link>
              <Button onClick={handleBuildGraph} disabled={isBuilding}>
                {isBuilding ? "Building..." : "Rebuild Graph"}
              </Button>
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        {dataMode === "simulation" && (
          <div className="mb-6">
            <DataSourceModeBanner
              mode={dataMode}
              title="Patient graph data source"
              description="Backend API is unavailable. Graph visualization shows demonstration knowledge graph data."
              backendEndpoints={[`/api/v1/patients/${patientId}/graph`]}
            />
          </div>
        )}
        {error && !graph ? (
          <Card className="mx-auto max-w-2xl">
            <CardContent className="py-8 text-center">
              <p className="text-zinc-500 mb-4">{error}</p>
              <Button onClick={handleBuildGraph} disabled={isBuilding}>
                {isBuilding ? "Building Graph..." : "Build Graph"}
              </Button>
            </CardContent>
          </Card>
        ) : graph ? (
          <div className="space-y-6">
            {/* Summary Cards */}
            <div className="grid gap-4 grid-cols-2 md:grid-cols-4 lg:grid-cols-6">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-zinc-500">Total Nodes</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{graph.node_count}</div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-zinc-500">Total Edges</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{graph.edge_count}</div>
                </CardContent>
              </Card>
              {Object.entries(NODE_TYPE_ICONS).slice(1, 5).map(([type, icon]) => (
                <Card key={type} className="hidden md:block">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-zinc-500 flex items-center gap-1">
                      <span>{icon}</span>
                      <span className="capitalize">{type}s</span>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">{nodesByType[type]?.length || 0}</div>
                  </CardContent>
                </Card>
              ))}
            </div>

            {/* Tabs for different views */}
            <Tabs defaultValue="visual" className="w-full">
              <TabsList className="grid w-full grid-cols-4">
                <TabsTrigger value="visual">Visual Graph</TabsTrigger>
                <TabsTrigger value="nodes">Nodes ({graph.node_count})</TabsTrigger>
                <TabsTrigger value="edges">Edges ({graph.edge_count})</TabsTrigger>
                <TabsTrigger value="analysis">Analysis</TabsTrigger>
              </TabsList>

              {/* Visual Tab */}
              <TabsContent value="visual">
                <Card className="overflow-hidden">
                  <CardContent className="p-0">
                    <div className="h-[700px]">
                      <KnowledgeGraph
                        nodes={graph.nodes}
                        edges={graph.edges}
                        patientId={patientId}
                      />
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>

              {/* Nodes Tab */}
              <TabsContent value="nodes">
                <Card>
                  <CardHeader>
                    <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                      <div>
                        <CardTitle>Graph Nodes</CardTitle>
                        <CardDescription>
                          All clinical entities for this patient
                        </CardDescription>
                      </div>
                      <div className="flex gap-2 flex-wrap">
                        <Input
                          placeholder="Search nodes..."
                          value={searchQuery}
                          onChange={(e) => setSearchQuery(e.target.value)}
                          className="w-48"
                        />
                        <select
                          className="flex h-10 rounded-md border border-input bg-background px-3 py-2 text-sm"
                          value={selectedType || ""}
                          onChange={(e) => setSelectedType(e.target.value || null)}
                        >
                          <option value="">All Types</option>
                          {Object.keys(nodesByType).map((type) => (
                            <option key={type} value={type}>
                              {type.charAt(0).toUpperCase() + type.slice(1)} ({nodesByType[type].length})
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    {/* Type filter buttons */}
                    <div className="flex flex-wrap gap-2 mb-4">
                      <Button
                        variant={selectedType === null ? "default" : "outline"}
                        size="sm"
                        onClick={() => setSelectedType(null)}
                      >
                        All ({graph.nodes.length})
                      </Button>
                      {Object.entries(nodesByType).map(([type, nodes]) => (
                        <Button
                          key={type}
                          variant={selectedType === type ? "default" : "outline"}
                          size="sm"
                          onClick={() => setSelectedType(selectedType === type ? null : type)}
                          className="gap-1"
                        >
                          <span>{NODE_TYPE_ICONS[type] || "📋"}</span>
                          <span className="capitalize">{type}</span>
                          <Badge variant="secondary" className="ml-1">{nodes.length}</Badge>
                        </Button>
                      ))}
                    </div>

                    <div className="rounded-lg border overflow-auto max-h-[500px]">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead className="w-10"></TableHead>
                            <TableHead>Type</TableHead>
                            <TableHead>Label</TableHead>
                            <TableHead>OMOP ID</TableHead>
                            <TableHead>Properties</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {filteredNodes.map((node) => (
                            <TableRow key={node.id}>
                              <TableCell>{NODE_TYPE_ICONS[node.node_type] || "📋"}</TableCell>
                              <TableCell>
                                <Badge className={NODE_TYPE_COLORS[node.node_type] || "bg-gray-100"}>
                                  {node.node_type}
                                </Badge>
                              </TableCell>
                              <TableCell className="font-medium">{node.label}</TableCell>
                              <TableCell className="font-mono text-xs">{node.omop_concept_id || "-"}</TableCell>
                              <TableCell>
                                <div className="flex flex-wrap gap-1">
                                  {Object.entries(node.properties || {}).map(([key, value]) => (
                                    <Badge key={key} variant="outline" className="text-xs">
                                      {key}: {String(value)}
                                    </Badge>
                                  ))}
                                </div>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                    <div className="mt-2 text-sm text-zinc-500">
                      Showing {filteredNodes.length} of {graph.nodes.length} nodes
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>

              {/* Edges Tab */}
              <TabsContent value="edges">
                <Card>
                  <CardHeader>
                    <CardTitle>Graph Edges</CardTitle>
                    <CardDescription>
                      Relationships between entities
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {/* Edge type distribution */}
                    <div className="flex flex-wrap gap-2 mb-4">
                      {edgeTypeDistribution.map(({ type, count }) => (
                        <Badge key={type} variant="outline" className="text-sm">
                          {EDGE_TYPE_LABELS[type] || type}: {count}
                        </Badge>
                      ))}
                    </div>

                    <div className="rounded-lg border overflow-auto max-h-[500px]">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Source</TableHead>
                            <TableHead>Relationship</TableHead>
                            <TableHead>Target</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {graph.edges.map((edge) => (
                            <TableRow key={edge.id}>
                              <TableCell className="flex items-center gap-2">
                                <span>{NODE_TYPE_ICONS[graph.nodes.find((n) => n.id === edge.source_node_id)?.node_type || "observation"]}</span>
                                <span className="font-medium">{getNodeLabel(edge.source_node_id)}</span>
                              </TableCell>
                              <TableCell>
                                <Badge variant="outline">
                                  {EDGE_TYPE_LABELS[edge.edge_type] || edge.edge_type}
                                </Badge>
                              </TableCell>
                              <TableCell className="flex items-center gap-2">
                                <span>{NODE_TYPE_ICONS[graph.nodes.find((n) => n.id === edge.target_node_id)?.node_type || "observation"]}</span>
                                <span className="font-medium">{getNodeLabel(edge.target_node_id)}</span>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>

              {/* Analysis Tab */}
              <TabsContent value="analysis">
                <div className="grid gap-6 lg:grid-cols-2">
                  {/* Node Type Distribution */}
                  <Card>
                    <CardHeader>
                      <CardTitle>Node Type Distribution</CardTitle>
                      <CardDescription>
                        Breakdown of clinical entities by type
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-3">
                        {nodeStats.map((stat) => (
                          <div key={stat.type} className="flex items-center gap-3">
                            <span className="text-xl">{NODE_TYPE_ICONS[stat.type] || "📋"}</span>
                            <div className="flex-1">
                              <div className="flex items-center justify-between mb-1">
                                <span className="font-medium capitalize">{stat.type}</span>
                                <span className="text-sm text-zinc-500">{stat.count} nodes</span>
                              </div>
                              <div className="w-full bg-zinc-200 dark:bg-zinc-700 rounded-full h-2">
                                <div
                                  className={`h-2 rounded-full ${NODE_TYPE_COLORS[stat.type]?.includes("red") ? "bg-red-500" :
                                    NODE_TYPE_COLORS[stat.type]?.includes("blue") ? "bg-blue-500" :
                                    NODE_TYPE_COLORS[stat.type]?.includes("green") ? "bg-green-500" :
                                    NODE_TYPE_COLORS[stat.type]?.includes("orange") ? "bg-orange-500" :
                                    NODE_TYPE_COLORS[stat.type]?.includes("purple") ? "bg-purple-500" :
                                    "bg-gray-500"
                                  }`}
                                  style={{ width: `${(stat.count / graph.node_count) * 100}%` }}
                                />
                              </div>
                            </div>
                            <div className="text-right text-sm">
                              <div className="text-zinc-500">Avg connections</div>
                              <div className="font-medium">{stat.avgConnections}</div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>

                  {/* Hub Nodes */}
                  <Card>
                    <CardHeader>
                      <CardTitle>Hub Nodes</CardTitle>
                      <CardDescription>
                        Most connected entities in the graph
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-2">
                        {hubNodes.map(({ node, connections }, index) => (
                          <div
                            key={node.id}
                            className="flex items-center gap-3 p-2 rounded-lg border hover:bg-zinc-50 dark:hover:bg-zinc-800/50"
                          >
                            <span className="text-lg font-bold text-zinc-400 w-6">
                              #{index + 1}
                            </span>
                            <span className="text-xl">{NODE_TYPE_ICONS[node.node_type] || "📋"}</span>
                            <div className="flex-1 min-w-0">
                              <div className="font-medium truncate">{node.label}</div>
                              <div className="text-xs text-zinc-500 capitalize">{node.node_type}</div>
                            </div>
                            <Badge variant="secondary">{connections} connections</Badge>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>

                  {/* Edge Type Distribution */}
                  <Card>
                    <CardHeader>
                      <CardTitle>Relationship Types</CardTitle>
                      <CardDescription>
                        Distribution of edge types in the graph
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-3">
                        {edgeTypeDistribution.map(({ type, count }) => (
                          <div key={type} className="flex items-center justify-between">
                            <span className="text-sm">{EDGE_TYPE_LABELS[type] || type}</span>
                            <div className="flex items-center gap-2">
                              <div className="w-32 bg-zinc-200 dark:bg-zinc-700 rounded-full h-2">
                                <div
                                  className="h-2 rounded-full bg-blue-500"
                                  style={{ width: `${(count / graph.edge_count) * 100}%` }}
                                />
                              </div>
                              <span className="text-sm text-zinc-500 w-12 text-right">{count}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>

                  {/* Graph Metrics */}
                  <Card>
                    <CardHeader>
                      <CardTitle>Graph Metrics</CardTitle>
                      <CardDescription>
                        Overall graph statistics
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <dl className="grid grid-cols-2 gap-4">
                        <div className="p-3 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg">
                          <dt className="text-sm text-zinc-500">Total Nodes</dt>
                          <dd className="text-2xl font-bold">{graph.node_count}</dd>
                        </div>
                        <div className="p-3 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg">
                          <dt className="text-sm text-zinc-500">Total Edges</dt>
                          <dd className="text-2xl font-bold">{graph.edge_count}</dd>
                        </div>
                        <div className="p-3 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg">
                          <dt className="text-sm text-zinc-500">Avg. Degree</dt>
                          <dd className="text-2xl font-bold">
                            {graph.node_count > 0
                              ? ((graph.edge_count * 2) / graph.node_count).toFixed(1)
                              : 0}
                          </dd>
                        </div>
                        <div className="p-3 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg">
                          <dt className="text-sm text-zinc-500">Node Types</dt>
                          <dd className="text-2xl font-bold">{Object.keys(nodesByType).length}</dd>
                        </div>
                        <div className="p-3 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg">
                          <dt className="text-sm text-zinc-500">Edge Types</dt>
                          <dd className="text-2xl font-bold">{edgeTypeDistribution.length}</dd>
                        </div>
                        <div className="p-3 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg">
                          <dt className="text-sm text-zinc-500">Max Connections</dt>
                          <dd className="text-2xl font-bold">{hubNodes[0]?.connections || 0}</dd>
                        </div>
                      </dl>
                    </CardContent>
                  </Card>
                </div>
              </TabsContent>
            </Tabs>
          </div>
        ) : (
          <div className="flex items-center justify-center py-16">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-zinc-300 border-t-zinc-900" />
          </div>
        )}
      </main>
    </div>
  );
}
