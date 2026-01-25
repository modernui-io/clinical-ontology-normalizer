"use client";

import { useState, useMemo, useCallback } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useDocuments } from "@/hooks/use-api";
import { getDocument, Document } from "@/lib/api";

interface DiffLine {
  type: "unchanged" | "added" | "removed";
  content: string;
  lineNumber?: number;
}

function computeLineDiff(text1: string, text2: string): { left: DiffLine[]; right: DiffLine[] } {
  const lines1 = text1.split("\n");
  const lines2 = text2.split("\n");

  const left: DiffLine[] = [];
  const right: DiffLine[] = [];

  // Simple line-by-line diff algorithm
  const maxLen = Math.max(lines1.length, lines2.length);

  for (let i = 0; i < maxLen; i++) {
    const line1 = lines1[i];
    const line2 = lines2[i];

    if (line1 === undefined && line2 !== undefined) {
      // Line only in document 2 (added)
      left.push({ type: "unchanged", content: "", lineNumber: i + 1 });
      right.push({ type: "added", content: line2, lineNumber: i + 1 });
    } else if (line2 === undefined && line1 !== undefined) {
      // Line only in document 1 (removed)
      left.push({ type: "removed", content: line1, lineNumber: i + 1 });
      right.push({ type: "unchanged", content: "", lineNumber: i + 1 });
    } else if (line1 === line2) {
      // Lines are the same
      left.push({ type: "unchanged", content: line1, lineNumber: i + 1 });
      right.push({ type: "unchanged", content: line2, lineNumber: i + 1 });
    } else {
      // Lines are different
      left.push({ type: "removed", content: line1, lineNumber: i + 1 });
      right.push({ type: "added", content: line2, lineNumber: i + 1 });
    }
  }

  return { left, right };
}

function DiffView({ lines, side }: { lines: DiffLine[]; side: "left" | "right" }) {
  return (
    <div className="font-mono text-sm overflow-auto max-h-[600px]">
      {lines.map((line, idx) => (
        <div
          key={idx}
          className={`flex min-h-[24px] ${
            line.type === "added"
              ? "bg-green-100 dark:bg-green-900/30"
              : line.type === "removed"
              ? "bg-red-100 dark:bg-red-900/30"
              : ""
          }`}
        >
          <span className="w-10 flex-shrink-0 text-right pr-2 text-zinc-400 border-r border-zinc-200 dark:border-zinc-700 select-none">
            {line.lineNumber || ""}
          </span>
          <span className="w-6 flex-shrink-0 text-center select-none">
            {line.type === "added" ? (
              <span className="text-green-600">+</span>
            ) : line.type === "removed" ? (
              <span className="text-red-600">-</span>
            ) : (
              ""
            )}
          </span>
          <span className="px-2 whitespace-pre-wrap break-all">
            {line.content || "\u00A0"}
          </span>
        </div>
      ))}
    </div>
  );
}

function DocumentStats({ doc }: { doc: Document }) {
  const wordCount = doc.text.split(/\s+/).filter(Boolean).length;
  const lineCount = doc.text.split("\n").length;
  const charCount = doc.text.length;

  return (
    <div className="flex gap-4 text-sm text-zinc-500">
      <span>{wordCount} words</span>
      <span>{lineCount} lines</span>
      <span>{charCount} chars</span>
    </div>
  );
}

export default function DocumentComparePage() {
  const [leftDocId, setLeftDocId] = useState<string>("");
  const [rightDocId, setRightDocId] = useState<string>("");
  const [leftDoc, setLeftDoc] = useState<Document | null>(null);
  const [rightDoc, setRightDoc] = useState<Document | null>(null);
  const [isLoadingLeft, setIsLoadingLeft] = useState(false);
  const [isLoadingRight, setIsLoadingRight] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  // Fetch document list for selection
  const { data: documentsData, isLoading: isLoadingDocuments } = useDocuments({ page: 1, page_size: 100 });
  const documents = documentsData?.documents || [];

  // Filter documents by search
  const filteredDocuments = useMemo(() => {
    if (!searchQuery.trim()) return documents;
    const query = searchQuery.toLowerCase();
    return documents.filter(
      (doc) =>
        doc.patient_id.toLowerCase().includes(query) ||
        doc.note_type.toLowerCase().includes(query) ||
        doc.id.toLowerCase().includes(query)
    );
  }, [documents, searchQuery]);

  // Load left document
  const loadLeftDocument = useCallback(async (docId: string) => {
    if (!docId) {
      setLeftDoc(null);
      return;
    }
    setIsLoadingLeft(true);
    try {
      const doc = await getDocument(docId);
      setLeftDoc(doc);
    } catch (err) {
      console.error("Failed to load left document:", err);
      setLeftDoc(null);
    } finally {
      setIsLoadingLeft(false);
    }
  }, []);

  // Load right document
  const loadRightDocument = useCallback(async (docId: string) => {
    if (!docId) {
      setRightDoc(null);
      return;
    }
    setIsLoadingRight(true);
    try {
      const doc = await getDocument(docId);
      setRightDoc(doc);
    } catch (err) {
      console.error("Failed to load right document:", err);
      setRightDoc(null);
    } finally {
      setIsLoadingRight(false);
    }
  }, []);

  // Handle document selection
  const handleLeftSelect = (docId: string) => {
    setLeftDocId(docId);
    loadLeftDocument(docId);
  };

  const handleRightSelect = (docId: string) => {
    setRightDocId(docId);
    loadRightDocument(docId);
  };

  // Swap documents
  const handleSwap = () => {
    const tempId = leftDocId;
    const tempDoc = leftDoc;
    setLeftDocId(rightDocId);
    setLeftDoc(rightDoc);
    setRightDocId(tempId);
    setRightDoc(tempDoc);
  };

  // Compute diff
  const diff = useMemo(() => {
    if (!leftDoc || !rightDoc) return null;
    return computeLineDiff(leftDoc.text, rightDoc.text);
  }, [leftDoc, rightDoc]);

  // Compute diff statistics
  const diffStats = useMemo(() => {
    if (!diff) return null;
    const added = diff.right.filter((l) => l.type === "added").length;
    const removed = diff.left.filter((l) => l.type === "removed").length;
    const unchanged = diff.left.filter((l) => l.type === "unchanged" && l.content).length;
    return { added, removed, unchanged };
  }, [diff]);

  return (
    <div className="p-6">
      <div className="mb-6">
        <div className="flex items-center gap-4">
          <Link href="/documents" className="text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100">
            &larr; Documents
          </Link>
          <h1 className="text-2xl font-bold tracking-tight">Document Comparison</h1>
        </div>
        <p className="text-muted-foreground mt-1">
          Compare two documents side-by-side with difference highlighting
        </p>
      </div>

      <div className="space-y-6">
        {/* Document Selection */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Select Documents</CardTitle>
            <CardDescription>Choose two documents to compare</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="mb-4">
              <Input
                placeholder="Search documents by patient ID, note type, or document ID..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="max-w-md"
              />
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5 items-end">
              {/* Left Document */}
              <div className="lg:col-span-2">
                <label className="text-sm font-medium text-zinc-500 block mb-2">
                  Document A (Left)
                </label>
                <Select value={leftDocId} onValueChange={handleLeftSelect}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select first document..." />
                  </SelectTrigger>
                  <SelectContent>
                    {isLoadingDocuments ? (
                      <SelectItem value="" disabled>Loading...</SelectItem>
                    ) : filteredDocuments.length === 0 ? (
                      <SelectItem value="" disabled>No documents found</SelectItem>
                    ) : (
                      filteredDocuments.map((doc) => (
                        <SelectItem key={doc.id} value={doc.id} disabled={doc.id === rightDocId}>
                          <span className="flex items-center gap-2">
                            <span className="font-medium">{doc.patient_id}</span>
                            <span className="text-zinc-500">{doc.note_type}</span>
                            <span className="text-xs text-zinc-400">{doc.id.slice(0, 8)}...</span>
                          </span>
                        </SelectItem>
                      ))
                    )}
                  </SelectContent>
                </Select>
              </div>

              {/* Swap Button */}
              <div className="flex justify-center">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleSwap}
                  disabled={!leftDocId || !rightDocId}
                >
                  &harr; Swap
                </Button>
              </div>

              {/* Right Document */}
              <div className="lg:col-span-2">
                <label className="text-sm font-medium text-zinc-500 block mb-2">
                  Document B (Right)
                </label>
                <Select value={rightDocId} onValueChange={handleRightSelect}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select second document..." />
                  </SelectTrigger>
                  <SelectContent>
                    {isLoadingDocuments ? (
                      <SelectItem value="" disabled>Loading...</SelectItem>
                    ) : filteredDocuments.length === 0 ? (
                      <SelectItem value="" disabled>No documents found</SelectItem>
                    ) : (
                      filteredDocuments.map((doc) => (
                        <SelectItem key={doc.id} value={doc.id} disabled={doc.id === leftDocId}>
                          <span className="flex items-center gap-2">
                            <span className="font-medium">{doc.patient_id}</span>
                            <span className="text-zinc-500">{doc.note_type}</span>
                            <span className="text-xs text-zinc-400">{doc.id.slice(0, 8)}...</span>
                          </span>
                        </SelectItem>
                      ))
                    )}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Diff Statistics */}
        {diffStats && (
          <Card>
            <CardContent className="py-4">
              <div className="flex items-center justify-center gap-6">
                <Badge variant="outline" className="bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-200">
                  +{diffStats.added} added
                </Badge>
                <Badge variant="outline" className="bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-200">
                  -{diffStats.removed} removed
                </Badge>
                <Badge variant="outline">
                  {diffStats.unchanged} unchanged
                </Badge>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Comparison View */}
        {(isLoadingLeft || isLoadingRight) ? (
          <Card>
            <CardContent className="py-12">
              <div className="flex items-center justify-center">
                <div className="h-8 w-8 animate-spin rounded-full border-4 border-zinc-300 border-t-zinc-900" />
              </div>
            </CardContent>
          </Card>
        ) : leftDoc && rightDoc && diff ? (
          <div className="grid gap-4 lg:grid-cols-2">
            {/* Left Document */}
            <Card>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-base">
                      Document A: {leftDoc.note_type}
                    </CardTitle>
                    <CardDescription>
                      Patient: {leftDoc.patient_id}
                    </CardDescription>
                  </div>
                  <Badge>{leftDoc.status}</Badge>
                </div>
                <DocumentStats doc={leftDoc} />
              </CardHeader>
              <CardContent className="border-t">
                <DiffView lines={diff.left} side="left" />
              </CardContent>
            </Card>

            {/* Right Document */}
            <Card>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-base">
                      Document B: {rightDoc.note_type}
                    </CardTitle>
                    <CardDescription>
                      Patient: {rightDoc.patient_id}
                    </CardDescription>
                  </div>
                  <Badge>{rightDoc.status}</Badge>
                </div>
                <DocumentStats doc={rightDoc} />
              </CardHeader>
              <CardContent className="border-t">
                <DiffView lines={diff.right} side="right" />
              </CardContent>
            </Card>
          </div>
        ) : leftDoc || rightDoc ? (
          <Card>
            <CardContent className="py-12 text-center text-zinc-500">
              <p>Select both documents to see the comparison.</p>
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardContent className="py-12 text-center text-zinc-500">
              <p>Select two documents above to compare them side-by-side.</p>
              <p className="mt-2 text-sm">
                Differences will be highlighted with colors:
                <span className="text-green-600 ml-2">+ additions</span>
                <span className="text-red-600 ml-2">- removals</span>
              </p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
