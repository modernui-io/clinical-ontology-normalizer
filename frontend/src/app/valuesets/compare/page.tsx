"use client";

import { useState, useMemo } from "react";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  ArrowLeft,
  GitCompare,
  Plus,
  Minus,
  Equal,
  RefreshCw,
  Download,
  Search,
  ArrowRight,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Copy,
  List,
  Layers,
} from "lucide-react";

// Types
interface ValueSetCode {
  system: string;
  code: string;
  display: string;
  version?: string;
}

interface ValueSet {
  id: string;
  name: string;
  title: string;
  version: string;
  status: "draft" | "active" | "retired";
  codeCount: number;
  codes: ValueSetCode[];
}

interface ComparisonResult {
  onlyInLeft: ValueSetCode[];
  onlyInRight: ValueSetCode[];
  inBoth: ValueSetCode[];
  statistics: {
    leftTotal: number;
    rightTotal: number;
    commonCount: number;
    leftOnlyCount: number;
    rightOnlyCount: number;
    similarity: number;
  };
}

// Mock Value Sets
const mockValueSets: ValueSet[] = [
  {
    id: "vs-001",
    name: "diabetes-dx",
    title: "Diabetes Mellitus Diagnoses",
    version: "2024.01",
    status: "active",
    codeCount: 45,
    codes: [
      { system: "ICD-10-CM", code: "E11.9", display: "Type 2 diabetes mellitus without complications" },
      { system: "ICD-10-CM", code: "E11.65", display: "Type 2 diabetes mellitus with hyperglycemia" },
      { system: "ICD-10-CM", code: "E11.21", display: "Type 2 diabetes mellitus with diabetic nephropathy" },
      { system: "ICD-10-CM", code: "E11.22", display: "Type 2 diabetes mellitus with diabetic chronic kidney disease" },
      { system: "ICD-10-CM", code: "E11.40", display: "Type 2 diabetes mellitus with diabetic neuropathy" },
      { system: "ICD-10-CM", code: "E11.41", display: "Type 2 diabetes mellitus with diabetic mononeuropathy" },
      { system: "ICD-10-CM", code: "E11.42", display: "Type 2 diabetes mellitus with diabetic polyneuropathy" },
      { system: "ICD-10-CM", code: "E11.51", display: "Type 2 diabetes mellitus with diabetic peripheral angiopathy" },
      { system: "ICD-10-CM", code: "E10.9", display: "Type 1 diabetes mellitus without complications" },
      { system: "ICD-10-CM", code: "E10.65", display: "Type 1 diabetes mellitus with hyperglycemia" },
      { system: "SNOMED", code: "44054006", display: "Type 2 diabetes mellitus" },
      { system: "SNOMED", code: "46635009", display: "Type 1 diabetes mellitus" },
    ],
  },
  {
    id: "vs-002",
    name: "diabetes-dx-v2",
    title: "Diabetes Mellitus Diagnoses v2",
    version: "2024.06",
    status: "active",
    codeCount: 52,
    codes: [
      { system: "ICD-10-CM", code: "E11.9", display: "Type 2 diabetes mellitus without complications" },
      { system: "ICD-10-CM", code: "E11.65", display: "Type 2 diabetes mellitus with hyperglycemia" },
      { system: "ICD-10-CM", code: "E11.21", display: "Type 2 diabetes mellitus with diabetic nephropathy" },
      { system: "ICD-10-CM", code: "E11.22", display: "Type 2 diabetes mellitus with diabetic chronic kidney disease" },
      { system: "ICD-10-CM", code: "E11.40", display: "Type 2 diabetes mellitus with diabetic neuropathy" },
      { system: "ICD-10-CM", code: "E11.52", display: "Type 2 diabetes mellitus with diabetic peripheral angiopathy with gangrene" },
      { system: "ICD-10-CM", code: "E11.610", display: "Type 2 diabetes mellitus with diabetic neuropathic arthropathy" },
      { system: "ICD-10-CM", code: "E11.620", display: "Type 2 diabetes mellitus with diabetic dermatitis" },
      { system: "ICD-10-CM", code: "E10.9", display: "Type 1 diabetes mellitus without complications" },
      { system: "ICD-10-CM", code: "E10.65", display: "Type 1 diabetes mellitus with hyperglycemia" },
      { system: "ICD-10-CM", code: "E13.9", display: "Other specified diabetes mellitus without complications" },
      { system: "SNOMED", code: "44054006", display: "Type 2 diabetes mellitus" },
      { system: "SNOMED", code: "46635009", display: "Type 1 diabetes mellitus" },
      { system: "SNOMED", code: "73211009", display: "Diabetes mellitus" },
    ],
  },
  {
    id: "vs-003",
    name: "hypertension-dx",
    title: "Hypertension Diagnoses",
    version: "2024.03",
    status: "active",
    codeCount: 28,
    codes: [
      { system: "ICD-10-CM", code: "I10", display: "Essential (primary) hypertension" },
      { system: "ICD-10-CM", code: "I11.0", display: "Hypertensive heart disease with heart failure" },
      { system: "ICD-10-CM", code: "I11.9", display: "Hypertensive heart disease without heart failure" },
      { system: "ICD-10-CM", code: "I12.0", display: "Hypertensive chronic kidney disease with stage 5 CKD" },
      { system: "ICD-10-CM", code: "I12.9", display: "Hypertensive chronic kidney disease with stage 1-4 CKD" },
      { system: "SNOMED", code: "38341003", display: "Hypertensive disorder, systemic arterial" },
    ],
  },
];

// Compute comparison
function compareValueSets(left: ValueSet, right: ValueSet): ComparisonResult {
  const leftCodes = new Map(left.codes.map((c) => [`${c.system}|${c.code}`, c]));
  const rightCodes = new Map(right.codes.map((c) => [`${c.system}|${c.code}`, c]));

  const onlyInLeft: ValueSetCode[] = [];
  const onlyInRight: ValueSetCode[] = [];
  const inBoth: ValueSetCode[] = [];

  for (const [key, code] of leftCodes) {
    if (rightCodes.has(key)) {
      inBoth.push(code);
    } else {
      onlyInLeft.push(code);
    }
  }

  for (const [key, code] of rightCodes) {
    if (!leftCodes.has(key)) {
      onlyInRight.push(code);
    }
  }

  const totalUnique = leftCodes.size + rightCodes.size - inBoth.length;
  const similarity = totalUnique > 0 ? (inBoth.length / totalUnique) * 100 : 0;

  return {
    onlyInLeft,
    onlyInRight,
    inBoth,
    statistics: {
      leftTotal: left.codes.length,
      rightTotal: right.codes.length,
      commonCount: inBoth.length,
      leftOnlyCount: onlyInLeft.length,
      rightOnlyCount: onlyInRight.length,
      similarity,
    },
  };
}

const STATUS_COLORS = {
  draft: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200",
  active: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  retired: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
};

export default function ValueSetComparePage() {
  const [leftValueSetId, setLeftValueSetId] = useState<string>("");
  const [rightValueSetId, setRightValueSetId] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  // Get selected value sets
  const leftValueSet = mockValueSets.find((vs) => vs.id === leftValueSetId);
  const rightValueSet = mockValueSets.find((vs) => vs.id === rightValueSetId);

  // Compute comparison if both are selected
  const comparison = useMemo(() => {
    if (!leftValueSet || !rightValueSet) return null;
    return compareValueSets(leftValueSet, rightValueSet);
  }, [leftValueSet, rightValueSet]);

  // Filter codes by search
  const filterCodes = (codes: ValueSetCode[]) => {
    if (!searchQuery) return codes;
    const query = searchQuery.toLowerCase();
    return codes.filter(
      (c) =>
        c.code.toLowerCase().includes(query) ||
        c.display.toLowerCase().includes(query) ||
        c.system.toLowerCase().includes(query)
    );
  };

  const handleSwap = () => {
    const temp = leftValueSetId;
    setLeftValueSetId(rightValueSetId);
    setRightValueSetId(temp);
  };

  const handleExport = () => {
    console.log("Exporting comparison results...");
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <Link
            href="/valuesets"
            className="text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100"
          >
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
              <GitCompare className="h-6 w-6 text-purple-600" />
              Value Set Comparison
            </h1>
            <p className="text-muted-foreground">
              Compare codes between two value sets to identify differences
            </p>
          </div>
        </div>
        {comparison && (
          <Button variant="outline" size="sm" onClick={handleExport}>
            <Download className="mr-2 h-4 w-4" />
            Export Comparison
          </Button>
        )}
      </div>

      {/* Selection */}
      <Card>
        <CardHeader>
          <CardTitle>Select Value Sets to Compare</CardTitle>
          <CardDescription>
            Choose two value sets to analyze their differences
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-[1fr,auto,1fr]">
            {/* Left Value Set */}
            <div className="space-y-2">
              <Label>Source Value Set (Left)</Label>
              <Select value={leftValueSetId} onValueChange={setLeftValueSetId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select value set" />
                </SelectTrigger>
                <SelectContent>
                  {mockValueSets.map((vs) => (
                    <SelectItem
                      key={vs.id}
                      value={vs.id}
                      disabled={vs.id === rightValueSetId}
                    >
                      <div className="flex items-center gap-2">
                        <span>{vs.title}</span>
                        <Badge variant="outline" className="text-xs">
                          v{vs.version}
                        </Badge>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {leftValueSet && (
                <div className="text-sm text-muted-foreground">
                  {leftValueSet.codeCount} codes •{" "}
                  <Badge className={STATUS_COLORS[leftValueSet.status]} variant="outline">
                    {leftValueSet.status}
                  </Badge>
                </div>
              )}
            </div>

            {/* Swap Button */}
            <div className="flex items-center justify-center">
              <Button
                variant="outline"
                size="icon"
                onClick={handleSwap}
                disabled={!leftValueSetId || !rightValueSetId}
              >
                <ArrowRight className="h-4 w-4" />
              </Button>
            </div>

            {/* Right Value Set */}
            <div className="space-y-2">
              <Label>Target Value Set (Right)</Label>
              <Select value={rightValueSetId} onValueChange={setRightValueSetId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select value set" />
                </SelectTrigger>
                <SelectContent>
                  {mockValueSets.map((vs) => (
                    <SelectItem
                      key={vs.id}
                      value={vs.id}
                      disabled={vs.id === leftValueSetId}
                    >
                      <div className="flex items-center gap-2">
                        <span>{vs.title}</span>
                        <Badge variant="outline" className="text-xs">
                          v{vs.version}
                        </Badge>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {rightValueSet && (
                <div className="text-sm text-muted-foreground">
                  {rightValueSet.codeCount} codes •{" "}
                  <Badge className={STATUS_COLORS[rightValueSet.status]} variant="outline">
                    {rightValueSet.status}
                  </Badge>
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Comparison Results */}
      {comparison && (
        <>
          {/* Statistics */}
          <div className="grid gap-4 md:grid-cols-5">
            <Card>
              <CardContent className="pt-4">
                <div className="flex items-center gap-2">
                  <div className="p-2 rounded-full bg-blue-100">
                    <List className="h-4 w-4 text-blue-600" />
                  </div>
                  <div>
                    <div className="text-2xl font-bold">{comparison.statistics.leftTotal}</div>
                    <p className="text-xs text-muted-foreground">Left Total</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-4">
                <div className="flex items-center gap-2">
                  <div className="p-2 rounded-full bg-purple-100">
                    <List className="h-4 w-4 text-purple-600" />
                  </div>
                  <div>
                    <div className="text-2xl font-bold">{comparison.statistics.rightTotal}</div>
                    <p className="text-xs text-muted-foreground">Right Total</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-4">
                <div className="flex items-center gap-2">
                  <div className="p-2 rounded-full bg-green-100">
                    <Equal className="h-4 w-4 text-green-600" />
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-green-600">
                      {comparison.statistics.commonCount}
                    </div>
                    <p className="text-xs text-muted-foreground">In Both</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-4">
                <div className="flex items-center gap-2">
                  <div className="p-2 rounded-full bg-amber-100">
                    <Minus className="h-4 w-4 text-amber-600" />
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-amber-600">
                      {comparison.statistics.leftOnlyCount}
                    </div>
                    <p className="text-xs text-muted-foreground">Left Only</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-4">
                <div className="flex items-center gap-2">
                  <div className="p-2 rounded-full bg-cyan-100">
                    <Plus className="h-4 w-4 text-cyan-600" />
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-cyan-600">
                      {comparison.statistics.rightOnlyCount}
                    </div>
                    <p className="text-xs text-muted-foreground">Right Only</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Similarity Score */}
          <Card>
            <CardContent className="pt-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <Layers className="h-6 w-6 text-muted-foreground" />
                  <div>
                    <div className="text-lg font-semibold">Jaccard Similarity Index</div>
                    <p className="text-sm text-muted-foreground">
                      Overlap coefficient between the two value sets
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-4xl font-bold">
                    {comparison.statistics.similarity.toFixed(1)}%
                  </div>
                  <Badge
                    className={
                      comparison.statistics.similarity >= 80
                        ? "bg-green-100 text-green-800"
                        : comparison.statistics.similarity >= 50
                        ? "bg-amber-100 text-amber-800"
                        : "bg-red-100 text-red-800"
                    }
                  >
                    {comparison.statistics.similarity >= 80
                      ? "High Overlap"
                      : comparison.statistics.similarity >= 50
                      ? "Moderate Overlap"
                      : "Low Overlap"}
                  </Badge>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Detail Tabs */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Code Differences</CardTitle>
                  <CardDescription>
                    Detailed view of code differences between value sets
                  </CardDescription>
                </div>
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search codes..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-9 w-64"
                  />
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="left-only" className="space-y-4">
                <TabsList className="grid w-full grid-cols-3">
                  <TabsTrigger value="left-only" className="flex items-center gap-2">
                    <Minus className="h-4 w-4 text-amber-600" />
                    Left Only ({comparison.onlyInLeft.length})
                  </TabsTrigger>
                  <TabsTrigger value="common" className="flex items-center gap-2">
                    <Equal className="h-4 w-4 text-green-600" />
                    Common ({comparison.inBoth.length})
                  </TabsTrigger>
                  <TabsTrigger value="right-only" className="flex items-center gap-2">
                    <Plus className="h-4 w-4 text-cyan-600" />
                    Right Only ({comparison.onlyInRight.length})
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="left-only">
                  <div className="border rounded-lg">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-12"></TableHead>
                          <TableHead>System</TableHead>
                          <TableHead>Code</TableHead>
                          <TableHead>Display</TableHead>
                          <TableHead className="w-12"></TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {filterCodes(comparison.onlyInLeft).length === 0 ? (
                          <TableRow>
                            <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                              No codes found only in the left value set
                            </TableCell>
                          </TableRow>
                        ) : (
                          filterCodes(comparison.onlyInLeft).map((code, idx) => (
                            <TableRow key={`${code.system}-${code.code}-${idx}`}>
                              <TableCell>
                                <Minus className="h-4 w-4 text-amber-600" />
                              </TableCell>
                              <TableCell>
                                <Badge variant="outline">{code.system}</Badge>
                              </TableCell>
                              <TableCell className="font-mono">{code.code}</TableCell>
                              <TableCell>{code.display}</TableCell>
                              <TableCell>
                                <Button variant="ghost" size="sm">
                                  <Copy className="h-4 w-4" />
                                </Button>
                              </TableCell>
                            </TableRow>
                          ))
                        )}
                      </TableBody>
                    </Table>
                  </div>
                </TabsContent>

                <TabsContent value="common">
                  <div className="border rounded-lg">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-12"></TableHead>
                          <TableHead>System</TableHead>
                          <TableHead>Code</TableHead>
                          <TableHead>Display</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {filterCodes(comparison.inBoth).length === 0 ? (
                          <TableRow>
                            <TableCell colSpan={4} className="text-center py-8 text-muted-foreground">
                              No common codes found
                            </TableCell>
                          </TableRow>
                        ) : (
                          filterCodes(comparison.inBoth).map((code, idx) => (
                            <TableRow key={`${code.system}-${code.code}-${idx}`}>
                              <TableCell>
                                <CheckCircle className="h-4 w-4 text-green-600" />
                              </TableCell>
                              <TableCell>
                                <Badge variant="outline">{code.system}</Badge>
                              </TableCell>
                              <TableCell className="font-mono">{code.code}</TableCell>
                              <TableCell>{code.display}</TableCell>
                            </TableRow>
                          ))
                        )}
                      </TableBody>
                    </Table>
                  </div>
                </TabsContent>

                <TabsContent value="right-only">
                  <div className="border rounded-lg">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-12"></TableHead>
                          <TableHead>System</TableHead>
                          <TableHead>Code</TableHead>
                          <TableHead>Display</TableHead>
                          <TableHead className="w-12"></TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {filterCodes(comparison.onlyInRight).length === 0 ? (
                          <TableRow>
                            <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                              No codes found only in the right value set
                            </TableCell>
                          </TableRow>
                        ) : (
                          filterCodes(comparison.onlyInRight).map((code, idx) => (
                            <TableRow key={`${code.system}-${code.code}-${idx}`}>
                              <TableCell>
                                <Plus className="h-4 w-4 text-cyan-600" />
                              </TableCell>
                              <TableCell>
                                <Badge variant="outline">{code.system}</Badge>
                              </TableCell>
                              <TableCell className="font-mono">{code.code}</TableCell>
                              <TableCell>{code.display}</TableCell>
                              <TableCell>
                                <Button variant="ghost" size="sm">
                                  <Copy className="h-4 w-4" />
                                </Button>
                              </TableCell>
                            </TableRow>
                          ))
                        )}
                      </TableBody>
                    </Table>
                  </div>
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        </>
      )}

      {/* Empty State */}
      {!comparison && (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-12">
            <GitCompare className="h-12 w-12 text-muted-foreground/50 mb-4" />
            <h3 className="text-lg font-medium">Select Value Sets to Compare</h3>
            <p className="text-sm text-muted-foreground text-center max-w-md mt-2">
              Choose two value sets from the dropdowns above to see a detailed
              comparison of their codes, including additions, removals, and common codes.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
