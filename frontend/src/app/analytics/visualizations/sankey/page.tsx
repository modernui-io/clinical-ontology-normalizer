"use client";

import { useState, useMemo, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Download,
  Filter,
  ZoomIn,
  ZoomOut,
  RefreshCw,
  Share2,
  Layers,
  GitBranch,
  ArrowRight,
} from "lucide-react";

// Types
interface SankeyNode {
  id: string;
  name: string;
  category: string;
  value: number;
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  color?: string;
}

interface SankeyLink {
  source: string;
  target: string;
  value: number;
  sourceName?: string;
  targetName?: string;
}

interface TreatmentPathway {
  id: string;
  path: string[];
  patientCount: number;
  avgDuration: number;
  outcomeRate: number;
}

// Mock treatment pathway data
const mockNodes: SankeyNode[] = [
  // Diagnosis stage
  { id: "diag-dm2", name: "Type 2 Diabetes", category: "diagnosis", value: 5000 },
  { id: "diag-htn", name: "Hypertension", category: "diagnosis", value: 3500 },
  { id: "diag-ckd", name: "CKD Stage 3+", category: "diagnosis", value: 2200 },

  // First-line treatment
  { id: "tx1-metformin", name: "Metformin", category: "first-line", value: 4200 },
  { id: "tx1-lifestyle", name: "Lifestyle Only", category: "first-line", value: 800 },
  { id: "tx1-ace", name: "ACE Inhibitor", category: "first-line", value: 2800 },
  { id: "tx1-arb", name: "ARB", category: "first-line", value: 700 },

  // Second-line treatment
  { id: "tx2-sglt2", name: "SGLT2 Inhibitor", category: "second-line", value: 2100 },
  { id: "tx2-glp1", name: "GLP-1 Agonist", category: "second-line", value: 1500 },
  { id: "tx2-insulin", name: "Insulin", category: "second-line", value: 900 },
  { id: "tx2-combo-bp", name: "Combo BP Med", category: "second-line", value: 1800 },

  // Third-line / Intensification
  { id: "tx3-triple", name: "Triple Therapy", category: "third-line", value: 1200 },
  { id: "tx3-insulin-int", name: "Insulin Intensification", category: "third-line", value: 800 },
  { id: "tx3-dialysis", name: "Dialysis Referral", category: "third-line", value: 400 },

  // Outcomes
  { id: "out-controlled", name: "Well Controlled", category: "outcome", value: 3200 },
  { id: "out-partial", name: "Partial Response", category: "outcome", value: 2100 },
  { id: "out-uncontrolled", name: "Uncontrolled", category: "outcome", value: 1500 },
  { id: "out-adverse", name: "Adverse Event", category: "outcome", value: 400 },
];

const mockLinks: SankeyLink[] = [
  // Diagnosis to First-line
  { source: "diag-dm2", target: "tx1-metformin", value: 4200 },
  { source: "diag-dm2", target: "tx1-lifestyle", value: 800 },
  { source: "diag-htn", target: "tx1-ace", value: 2800 },
  { source: "diag-htn", target: "tx1-arb", value: 700 },
  { source: "diag-ckd", target: "tx1-ace", value: 1400 },
  { source: "diag-ckd", target: "tx1-arb", value: 800 },

  // First-line to Second-line
  { source: "tx1-metformin", target: "tx2-sglt2", value: 1800 },
  { source: "tx1-metformin", target: "tx2-glp1", value: 1200 },
  { source: "tx1-metformin", target: "tx2-insulin", value: 700 },
  { source: "tx1-metformin", target: "out-controlled", value: 500 },
  { source: "tx1-lifestyle", target: "tx1-metformin", value: 600 },
  { source: "tx1-lifestyle", target: "out-controlled", value: 200 },
  { source: "tx1-ace", target: "tx2-combo-bp", value: 1600 },
  { source: "tx1-ace", target: "out-controlled", value: 1200 },
  { source: "tx1-arb", target: "tx2-combo-bp", value: 500 },
  { source: "tx1-arb", target: "out-controlled", value: 200 },

  // Second-line to Third-line/Outcomes
  { source: "tx2-sglt2", target: "tx3-triple", value: 800 },
  { source: "tx2-sglt2", target: "out-controlled", value: 900 },
  { source: "tx2-sglt2", target: "out-partial", value: 400 },
  { source: "tx2-glp1", target: "tx3-triple", value: 400 },
  { source: "tx2-glp1", target: "out-controlled", value: 700 },
  { source: "tx2-glp1", target: "out-partial", value: 400 },
  { source: "tx2-insulin", target: "tx3-insulin-int", value: 500 },
  { source: "tx2-insulin", target: "out-partial", value: 300 },
  { source: "tx2-insulin", target: "out-adverse", value: 100 },
  { source: "tx2-combo-bp", target: "out-controlled", value: 1000 },
  { source: "tx2-combo-bp", target: "out-partial", value: 600 },
  { source: "tx2-combo-bp", target: "tx3-dialysis", value: 200 },

  // Third-line to Outcomes
  { source: "tx3-triple", target: "out-controlled", value: 500 },
  { source: "tx3-triple", target: "out-partial", value: 400 },
  { source: "tx3-triple", target: "out-uncontrolled", value: 200 },
  { source: "tx3-triple", target: "out-adverse", value: 100 },
  { source: "tx3-insulin-int", target: "out-partial", value: 400 },
  { source: "tx3-insulin-int", target: "out-uncontrolled", value: 300 },
  { source: "tx3-insulin-int", target: "out-adverse", value: 100 },
  { source: "tx3-dialysis", target: "out-uncontrolled", value: 300 },
  { source: "tx3-dialysis", target: "out-adverse", value: 100 },
];

const mockPathways: TreatmentPathway[] = [
  { id: "1", path: ["Type 2 Diabetes", "Metformin", "SGLT2 Inhibitor", "Well Controlled"], patientCount: 900, avgDuration: 18, outcomeRate: 0.85 },
  { id: "2", path: ["Hypertension", "ACE Inhibitor", "Well Controlled"], patientCount: 1200, avgDuration: 12, outcomeRate: 0.78 },
  { id: "3", path: ["Type 2 Diabetes", "Metformin", "GLP-1 Agonist", "Well Controlled"], patientCount: 700, avgDuration: 24, outcomeRate: 0.82 },
  { id: "4", path: ["CKD Stage 3+", "ACE Inhibitor", "Combo BP Med", "Well Controlled"], patientCount: 600, avgDuration: 20, outcomeRate: 0.72 },
  { id: "5", path: ["Type 2 Diabetes", "Metformin", "Insulin", "Insulin Intensification", "Partial Response"], patientCount: 400, avgDuration: 36, outcomeRate: 0.55 },
];

const categoryColors: Record<string, string> = {
  diagnosis: "#6366f1",
  "first-line": "#22c55e",
  "second-line": "#f59e0b",
  "third-line": "#ef4444",
  outcome: "#8b5cf6",
};

const categoryOrder = ["diagnosis", "first-line", "second-line", "third-line", "outcome"];

export default function SankeyDiagramPage() {
  const [selectedCohort, setSelectedCohort] = useState("all");
  const [minFlowSize, setMinFlowSize] = useState([50]);
  const [showLabels, setShowLabels] = useState(true);
  const [highlightedNode, setHighlightedNode] = useState<string | null>(null);
  const [highlightedLink, setHighlightedLink] = useState<SankeyLink | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  // Calculate Sankey layout
  const { nodes, links, width, height } = useMemo(() => {
    const width = 1000;
    const height = 600;
    const nodeWidth = 20;
    const nodePadding = 15;
    const columnWidth = (width - nodeWidth) / (categoryOrder.length - 1);

    // Filter links by minimum flow size
    const filteredLinks = mockLinks.filter(l => l.value >= minFlowSize[0]);

    // Get nodes that have connections
    const connectedNodeIds = new Set<string>();
    filteredLinks.forEach(l => {
      connectedNodeIds.add(l.source);
      connectedNodeIds.add(l.target);
    });

    // Calculate node positions by category
    const nodesByCategory: Record<string, SankeyNode[]> = {};
    mockNodes
      .filter(n => connectedNodeIds.has(n.id))
      .forEach(node => {
        if (!nodesByCategory[node.category]) {
          nodesByCategory[node.category] = [];
        }
        nodesByCategory[node.category].push({ ...node });
      });

    // Position nodes
    const positionedNodes: SankeyNode[] = [];
    categoryOrder.forEach((category, colIndex) => {
      const categoryNodes = nodesByCategory[category] || [];
      const totalValue = categoryNodes.reduce((sum, n) => sum + n.value, 0);
      const availableHeight = height - (categoryNodes.length - 1) * nodePadding;

      let currentY = 0;
      categoryNodes.forEach(node => {
        const nodeHeight = Math.max(20, (node.value / totalValue) * availableHeight);
        positionedNodes.push({
          ...node,
          x: colIndex * columnWidth,
          y: currentY,
          width: nodeWidth,
          height: nodeHeight,
          color: categoryColors[category],
        });
        currentY += nodeHeight + nodePadding;
      });
    });

    // Create node lookup
    const nodeMap = new Map(positionedNodes.map(n => [n.id, n]));

    // Enrich links with node info
    const enrichedLinks = filteredLinks.map(link => {
      const sourceNode = nodeMap.get(link.source);
      const targetNode = nodeMap.get(link.target);
      return {
        ...link,
        sourceName: sourceNode?.name,
        targetName: targetNode?.name,
      };
    }).filter(l => nodeMap.has(l.source) && nodeMap.has(l.target));

    return { nodes: positionedNodes, links: enrichedLinks, width, height };
  }, [minFlowSize]);

  // Generate link paths
  const generateLinkPath = (link: SankeyLink): string => {
    const sourceNode = nodes.find(n => n.id === link.source);
    const targetNode = nodes.find(n => n.id === link.target);

    if (!sourceNode || !targetNode) return "";

    const sourceX = (sourceNode.x || 0) + (sourceNode.width || 0);
    const sourceY = (sourceNode.y || 0) + (sourceNode.height || 0) / 2;
    const targetX = targetNode.x || 0;
    const targetY = (targetNode.y || 0) + (targetNode.height || 0) / 2;

    const curvature = 0.5;
    const xi = sourceX + (targetX - sourceX) * curvature;

    return `M${sourceX},${sourceY} C${xi},${sourceY} ${xi},${targetY} ${targetX},${targetY}`;
  };

  const getLinkOpacity = (link: SankeyLink): number => {
    if (highlightedNode) {
      if (link.source === highlightedNode || link.target === highlightedNode) {
        return 0.8;
      }
      return 0.1;
    }
    if (highlightedLink) {
      return link === highlightedLink ? 0.8 : 0.1;
    }
    return 0.4;
  };

  const getLinkStrokeWidth = (link: SankeyLink): number => {
    // Scale stroke width based on value
    const maxValue = Math.max(...links.map(l => l.value));
    return Math.max(2, (link.value / maxValue) * 30);
  };

  const exportSVG = () => {
    if (!svgRef.current) return;

    const svgData = new XMLSerializer().serializeToString(svgRef.current);
    const svgBlob = new Blob([svgData], { type: "image/svg+xml;charset=utf-8" });
    const svgUrl = URL.createObjectURL(svgBlob);

    const downloadLink = document.createElement("a");
    downloadLink.href = svgUrl;
    downloadLink.download = "treatment-pathway-sankey.svg";
    document.body.appendChild(downloadLink);
    downloadLink.click();
    document.body.removeChild(downloadLink);
  };

  const totalPatients = mockNodes
    .filter(n => n.category === "diagnosis")
    .reduce((sum, n) => sum + n.value, 0);

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Treatment Pathway Analysis</h1>
          <p className="text-muted-foreground">
            Interactive Sankey diagram showing patient flow through treatment pathways
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={exportSVG}>
            <Download className="h-4 w-4 mr-2" />
            Export SVG
          </Button>
          <Button variant="outline">
            <Share2 className="h-4 w-4 mr-2" />
            Share
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <GitBranch className="h-5 w-5 text-blue-500" />
              <div>
                <p className="text-sm text-muted-foreground">Total Patients</p>
                <p className="text-2xl font-bold">{totalPatients.toLocaleString()}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Layers className="h-5 w-5 text-green-500" />
              <div>
                <p className="text-sm text-muted-foreground">Treatment Stages</p>
                <p className="text-2xl font-bold">{categoryOrder.length}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <ArrowRight className="h-5 w-5 text-orange-500" />
              <div>
                <p className="text-sm text-muted-foreground">Unique Pathways</p>
                <p className="text-2xl font-bold">{mockPathways.length}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Filter className="h-5 w-5 text-purple-500" />
              <div>
                <p className="text-sm text-muted-foreground">Well Controlled</p>
                <p className="text-2xl font-bold">
                  {((mockNodes.find(n => n.id === "out-controlled")?.value || 0) / totalPatients * 100).toFixed(0)}%
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Controls */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-wrap gap-6 items-end">
            <div className="space-y-2">
              <Label>Cohort Filter</Label>
              <Select value={selectedCohort} onValueChange={setSelectedCohort}>
                <SelectTrigger className="w-[200px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Patients</SelectItem>
                  <SelectItem value="diabetes">Diabetes Only</SelectItem>
                  <SelectItem value="hypertension">Hypertension Only</SelectItem>
                  <SelectItem value="ckd">CKD Patients</SelectItem>
                  <SelectItem value="elderly">Age 65+</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2 w-[200px]">
              <Label>Minimum Flow Size: {minFlowSize[0]}</Label>
              <Slider
                value={minFlowSize}
                onValueChange={setMinFlowSize}
                min={0}
                max={500}
                step={50}
              />
            </div>
            <div className="flex items-center gap-2">
              <Switch checked={showLabels} onCheckedChange={setShowLabels} />
              <Label>Show Labels</Label>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setHighlightedNode(null);
                setHighlightedLink(null);
              }}
            >
              <RefreshCw className="h-4 w-4 mr-2" />
              Reset View
            </Button>
          </div>
        </CardContent>
      </Card>

      <Tabs defaultValue="diagram">
        <TabsList>
          <TabsTrigger value="diagram">Sankey Diagram</TabsTrigger>
          <TabsTrigger value="pathways">Top Pathways</TabsTrigger>
          <TabsTrigger value="statistics">Flow Statistics</TabsTrigger>
        </TabsList>

        <TabsContent value="diagram">
          <Card>
            <CardHeader>
              <CardTitle>Treatment Flow Visualization</CardTitle>
              <CardDescription>
                Click on nodes or links to highlight specific pathways
              </CardDescription>
            </CardHeader>
            <CardContent>
              {/* Legend */}
              <div className="flex gap-4 mb-4">
                {categoryOrder.map(category => (
                  <div key={category} className="flex items-center gap-2">
                    <div
                      className="w-4 h-4 rounded"
                      style={{ backgroundColor: categoryColors[category] }}
                    />
                    <span className="text-sm capitalize">{category.replace("-", " ")}</span>
                  </div>
                ))}
              </div>

              {/* SVG Sankey */}
              <div className="overflow-x-auto">
                <svg
                  ref={svgRef}
                  width={width + 150}
                  height={height + 40}
                  className="border rounded-lg bg-white"
                >
                  <g transform="translate(75, 20)">
                    {/* Links */}
                    {links.map((link, i) => (
                      <path
                        key={i}
                        d={generateLinkPath(link)}
                        fill="none"
                        stroke="#94a3b8"
                        strokeWidth={getLinkStrokeWidth(link)}
                        strokeOpacity={getLinkOpacity(link)}
                        className="cursor-pointer transition-opacity duration-200"
                        onMouseEnter={() => setHighlightedLink(link)}
                        onMouseLeave={() => setHighlightedLink(null)}
                      >
                        <title>
                          {link.sourceName} → {link.targetName}: {link.value.toLocaleString()} patients
                        </title>
                      </path>
                    ))}

                    {/* Nodes */}
                    {nodes.map((node) => (
                      <g
                        key={node.id}
                        transform={`translate(${node.x}, ${node.y})`}
                        className="cursor-pointer"
                        onMouseEnter={() => setHighlightedNode(node.id)}
                        onMouseLeave={() => setHighlightedNode(null)}
                        opacity={
                          highlightedNode
                            ? highlightedNode === node.id ||
                              links.some(
                                (l) =>
                                  (l.source === highlightedNode && l.target === node.id) ||
                                  (l.target === highlightedNode && l.source === node.id)
                              )
                              ? 1
                              : 0.3
                            : 1
                        }
                      >
                        <rect
                          width={node.width}
                          height={node.height}
                          fill={node.color}
                          rx={4}
                          className="transition-opacity duration-200"
                        />
                        {showLabels && (
                          <text
                            x={node.category === "outcome" ? -5 : (node.width || 0) + 5}
                            y={(node.height || 0) / 2}
                            textAnchor={node.category === "outcome" ? "end" : "start"}
                            dominantBaseline="middle"
                            className="text-xs fill-slate-700"
                          >
                            {node.name} ({node.value.toLocaleString()})
                          </text>
                        )}
                        <title>
                          {node.name}: {node.value.toLocaleString()} patients
                        </title>
                      </g>
                    ))}
                  </g>
                </svg>
              </div>

              {/* Highlighted info */}
              {(highlightedLink || highlightedNode) && (
                <div className="mt-4 p-4 bg-slate-50 rounded-lg">
                  {highlightedLink && (
                    <p className="text-sm">
                      <span className="font-medium">{highlightedLink.sourceName}</span>
                      {" → "}
                      <span className="font-medium">{highlightedLink.targetName}</span>
                      {": "}
                      <Badge variant="secondary">{highlightedLink.value.toLocaleString()} patients</Badge>
                      {" ("}
                      {((highlightedLink.value / totalPatients) * 100).toFixed(1)}% of total)
                    </p>
                  )}
                  {highlightedNode && !highlightedLink && (
                    <p className="text-sm">
                      <span className="font-medium">
                        {nodes.find(n => n.id === highlightedNode)?.name}
                      </span>
                      {": "}
                      <Badge variant="secondary">
                        {nodes.find(n => n.id === highlightedNode)?.value.toLocaleString()} patients
                      </Badge>
                    </p>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="pathways">
          <Card>
            <CardHeader>
              <CardTitle>Most Common Treatment Pathways</CardTitle>
              <CardDescription>
                Ranked by patient volume through each complete pathway
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Rank</TableHead>
                    <TableHead>Treatment Pathway</TableHead>
                    <TableHead>Patients</TableHead>
                    <TableHead>Avg Duration</TableHead>
                    <TableHead>Success Rate</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {mockPathways.map((pathway, index) => (
                    <TableRow key={pathway.id}>
                      <TableCell className="font-medium">#{index + 1}</TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1 items-center">
                          {pathway.path.map((step, i) => (
                            <span key={i} className="flex items-center gap-1">
                              <Badge variant="outline" className="text-xs">
                                {step}
                              </Badge>
                              {i < pathway.path.length - 1 && (
                                <ArrowRight className="h-3 w-3 text-muted-foreground" />
                              )}
                            </span>
                          ))}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge>{pathway.patientCount.toLocaleString()}</Badge>
                      </TableCell>
                      <TableCell>{pathway.avgDuration} months</TableCell>
                      <TableCell>
                        <Badge
                          className={
                            pathway.outcomeRate >= 0.8
                              ? "bg-green-100 text-green-800"
                              : pathway.outcomeRate >= 0.6
                              ? "bg-yellow-100 text-yellow-800"
                              : "bg-red-100 text-red-800"
                          }
                        >
                          {(pathway.outcomeRate * 100).toFixed(0)}%
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="statistics">
          <Card>
            <CardHeader>
              <CardTitle>Flow Statistics by Stage</CardTitle>
              <CardDescription>
                Patient counts and transition rates at each treatment stage
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-5 gap-4">
                {categoryOrder.map(category => {
                  const categoryNodes = nodes.filter(n => n.category === category);
                  const totalValue = categoryNodes.reduce((sum, n) => sum + n.value, 0);

                  return (
                    <Card key={category}>
                      <CardHeader className="pb-2">
                        <div className="flex items-center gap-2">
                          <div
                            className="w-3 h-3 rounded"
                            style={{ backgroundColor: categoryColors[category] }}
                          />
                          <CardTitle className="text-sm capitalize">
                            {category.replace("-", " ")}
                          </CardTitle>
                        </div>
                      </CardHeader>
                      <CardContent className="space-y-2">
                        <p className="text-2xl font-bold">{totalValue.toLocaleString()}</p>
                        <p className="text-xs text-muted-foreground">
                          {categoryNodes.length} treatment options
                        </p>
                        <div className="space-y-1">
                          {categoryNodes.slice(0, 3).map(node => (
                            <div key={node.id} className="flex justify-between text-xs">
                              <span className="truncate">{node.name}</span>
                              <span className="text-muted-foreground">
                                {((node.value / totalValue) * 100).toFixed(0)}%
                              </span>
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
