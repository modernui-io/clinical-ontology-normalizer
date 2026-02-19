"use client";

import { useState, useCallback, useRef } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Search,
  FileText,
  ChevronLeft,
  ChevronRight,
  Users,
  Database,
  Loader2,
} from "lucide-react";
import { useMimicNoteStats, useMimicNoteSearch } from "@/hooks/api/useResearch";
import type { MimicNote } from "@/lib/api";

const PAGE_SIZE = 50;

const SECTION_HEADERS = [
  "Chief Complaint",
  "Major Surgical",
  "History of Present Illness",
  "Past Medical History",
  "Social History",
  "Family History",
  "Physical Exam",
  "Pertinent Results",
  "Brief Hospital Course",
  "Medications on Admission",
  "Discharge Medications",
  "Discharge Disposition",
  "Discharge Diagnosis",
  "Discharge Condition",
  "Discharge Instructions",
  "Followup Instructions",
  "EXAMINATION",
  "INDICATION",
  "TECHNIQUE",
  "COMPARISON",
  "FINDINGS",
  "IMPRESSION",
  "Allergies",
  "Attending",
  "Service",
  "Facility",
  "Active Issues",
  "Assessment and Plan",
  "Review of Systems",
  "Vitals",
  "Labs",
  "Imaging",
  "Micro",
];

const CATEGORY_COLORS: Record<string, string> = {
  "Discharge Summary": "bg-emerald-900/40 text-emerald-400 border-emerald-700/50",
  "Radiology Report": "bg-blue-900/40 text-blue-400 border-blue-700/50",
  "ED Triage": "bg-amber-900/40 text-amber-400 border-amber-700/50",
};

function highlightText(text: string, query: string): string {
  let escaped = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Highlight section headers
  const headerPattern = new RegExp(
    `(^|\\n)(${SECTION_HEADERS.join("|")})([:\\s])`,
    "gm"
  );
  escaped = escaped.replace(
    headerPattern,
    '$1<span class="text-amber-400 font-bold">$2</span>$3'
  );

  // Highlight search terms
  if (query) {
    const words = query
      .split(/\s+/)
      .filter((w) => w.length > 1);
    for (const w of words) {
      const re = new RegExp(
        `(${w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`,
        "gi"
      );
      escaped = escaped.replace(
        re,
        '<mark class="bg-yellow-700/60 text-yellow-100 px-0.5 rounded-sm">$1</mark>'
      );
    }
  }

  return escaped;
}

export default function NoteBrowserPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [activeQuery, setActiveQuery] = useState("");
  const [category, setCategory] = useState("all");
  const [page, setPage] = useState(0);
  const [selectedNote, setSelectedNote] = useState<MimicNote | null>(null);
  const noteBodyRef = useRef<HTMLDivElement>(null);

  const { data: stats } = useMimicNoteStats();
  const { data: results, isFetching } = useMimicNoteSearch({
    q: activeQuery,
    category,
    offset: page * PAGE_SIZE,
    limit: PAGE_SIZE,
  });

  const handleSearch = useCallback(() => {
    setActiveQuery(searchQuery);
    setPage(0);
    setSelectedNote(null);
  }, [searchQuery]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") handleSearch();
    },
    [handleSearch]
  );

  const handleCategoryChange = useCallback(
    (cat: string) => {
      setCategory(cat);
      setPage(0);
      setSelectedNote(null);
    },
    []
  );

  const handleSelectNote = useCallback((note: MimicNote) => {
    setSelectedNote(note);
    if (noteBodyRef.current) {
      noteBodyRef.current.scrollTop = 0;
    }
  }, []);

  const totalPages = results ? Math.ceil(results.total / PAGE_SIZE) : 0;

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900">
      {/* Header */}
      <header className="border-b bg-white dark:bg-zinc-950">
        <div className="container mx-auto px-4 py-4">
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <FileText className="h-6 w-6" />
            MIMIC-IV Note Browser
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Search and browse {stats?.total?.toLocaleString() ?? "..."} de-identified clinical notes
          </p>

          {/* Stats chips */}
          {stats && (
            <div className="flex flex-wrap gap-2 mt-3">
              {Object.entries(stats.categories).map(([cat, count]) => (
                <Badge
                  key={cat}
                  variant="secondary"
                  className="text-xs"
                >
                  {cat}: {count.toLocaleString()}
                </Badge>
              ))}
              <Badge variant="outline" className="text-xs">
                <Users className="h-3 w-3 mr-1" />
                {stats.unique_patients.toLocaleString()} patients
              </Badge>
              <Badge variant="outline" className="text-xs">
                <Database className="h-3 w-3 mr-1" />
                {stats.total.toLocaleString()} total
              </Badge>
            </div>
          )}

          {/* Search + filters */}
          <div className="flex gap-2 mt-4 items-center flex-wrap">
            <div className="relative flex-1 min-w-[280px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search notes... (e.g. pneumonia, chest pain, diabetes)"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                className="pl-10"
              />
            </div>
            {["all", "Discharge Summary", "Radiology Report", "ED Triage"].map(
              (cat) => (
                <Button
                  key={cat}
                  variant={category === cat ? "default" : "outline"}
                  size="sm"
                  onClick={() => handleCategoryChange(cat)}
                >
                  {cat === "all"
                    ? "All"
                    : cat === "Discharge Summary"
                      ? "Discharge"
                      : cat === "Radiology Report"
                        ? "Radiology"
                        : "ED Triage"}
                </Button>
              )
            )}
            <Button size="sm" onClick={handleSearch} disabled={isFetching}>
              {isFetching ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                "Search"
              )}
            </Button>
          </div>
        </div>
      </header>

      {/* Main content */}
      <div className="flex" style={{ height: "calc(100vh - 220px)" }}>
        {/* Sidebar - note list */}
        <div className="w-[380px] flex-shrink-0 border-r bg-white dark:bg-zinc-950 flex flex-col">
          <ScrollArea className="flex-1">
            {results?.notes && results.notes.length > 0 ? (
              <div>
                {results.notes.map((note) => (
                  <div
                    key={note.id}
                    onClick={() => handleSelectNote(note)}
                    className={`px-4 py-3 border-b cursor-pointer transition-colors hover:bg-zinc-100 dark:hover:bg-zinc-800 ${
                      selectedNote?.id === note.id
                        ? "bg-blue-50 dark:bg-blue-950/30 border-l-2 border-l-blue-500"
                        : ""
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs text-muted-foreground">
                        {note.note_id}
                      </span>
                      <Badge
                        variant="outline"
                        className={`text-[10px] px-1.5 py-0 ${
                          CATEGORY_COLORS[note.note_category] ?? ""
                        }`}
                      >
                        {note.note_category}
                      </Badge>
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      Patient {note.subject_id} &middot; {note.charttime || "—"}
                    </div>
                    <p className="text-xs text-muted-foreground/60 mt-1 truncate">
                      {note.text.replace(/\s+/g, " ").trim().slice(0, 100)}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-full py-20 text-muted-foreground">
                <Search className="h-8 w-8 mb-2 opacity-30" />
                <p className="text-sm">
                  {isFetching ? "Searching..." : "Search to browse notes"}
                </p>
              </div>
            )}
          </ScrollArea>

          {/* Pager */}
          {results && results.total > PAGE_SIZE && (
            <div className="flex items-center justify-center gap-2 py-2 px-3 border-t bg-zinc-50 dark:bg-zinc-900">
              <Button
                variant="outline"
                size="sm"
                disabled={page === 0}
                onClick={() => setPage((p) => p - 1)}
              >
                <ChevronLeft className="h-3 w-3" />
              </Button>
              <span className="text-xs text-muted-foreground">
                Page {page + 1} of {totalPages.toLocaleString()} (
                {results.total.toLocaleString()} results)
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages - 1}
                onClick={() => setPage((p) => p + 1)}
              >
                <ChevronRight className="h-3 w-3" />
              </Button>
            </div>
          )}
        </div>

        {/* Content - selected note */}
        <div className="flex-1 flex flex-col overflow-hidden bg-white dark:bg-zinc-950">
          {selectedNote ? (
            <>
              <div className="px-6 py-4 border-b flex-shrink-0">
                <div className="flex items-center gap-3">
                  <h2 className="text-sm font-semibold">
                    {selectedNote.note_category}
                  </h2>
                  <Badge
                    variant="outline"
                    className={`text-[10px] ${
                      CATEGORY_COLORS[selectedNote.note_category] ?? ""
                    }`}
                  >
                    {selectedNote.note_category}
                  </Badge>
                </div>
                <div className="flex gap-4 mt-2 text-xs text-muted-foreground flex-wrap">
                  <span>
                    Note:{" "}
                    <code className="bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded text-[11px]">
                      {selectedNote.note_id}
                    </code>
                  </span>
                  <span>
                    Patient:{" "}
                    <code className="bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded text-[11px]">
                      {selectedNote.subject_id}
                    </code>
                  </span>
                  <span>
                    Admission:{" "}
                    <code className="bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded text-[11px]">
                      {selectedNote.hadm_id || "—"}
                    </code>
                  </span>
                  <span>
                    Chart Time:{" "}
                    <code className="bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded text-[11px]">
                      {selectedNote.charttime || "—"}
                    </code>
                  </span>
                </div>
              </div>
              <div
                ref={noteBodyRef}
                className="flex-1 overflow-y-auto px-6 py-4"
              >
                <pre
                  className="whitespace-pre-wrap font-mono text-[13px] leading-7 text-zinc-700 dark:text-zinc-300"
                  dangerouslySetInnerHTML={{
                    __html: highlightText(selectedNote.text, activeQuery),
                  }}
                />
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
              <FileText className="h-10 w-10 mb-3 opacity-20" />
              <p className="text-sm">Select a note to view</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
