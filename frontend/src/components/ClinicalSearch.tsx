"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";

// Types
interface SearchResult {
  document_id: string;
  content: string;
  score: number;
  highlights: string[];
}

interface SearchResponse {
  query: string;
  search_type: string;
  results: SearchResult[];
  total_results: number;
  search_time_ms: number;
  suggestions: string[];
}

interface Answer {
  text: string;
  confidence: number;
  evidence: string[];
  source_documents: string[];
}

interface QAResponse {
  question: string;
  question_type: string;
  answer: Answer;
  related_concepts: string[];
  follow_up_questions: string[];
  response_time_ms: number;
}

type SearchMode = "search" | "qa";
type SearchType = "keyword" | "semantic" | "hybrid";

interface ClinicalSearchProps {
  patientId?: string;
  apiBaseUrl?: string;
  onResultClick?: (documentId: string) => void;
}

// Highlight component
function HighlightText({ text, query }: { text: string; query: string }) {
  if (!query.trim()) return <>{text}</>;

  const parts = text.split(new RegExp(`(${query})`, "gi"));
  return (
    <>
      {parts.map((part, i) =>
        part.toLowerCase() === query.toLowerCase() ? (
          <mark key={i} className="bg-amber-300/40 text-amber-100 rounded px-0.5">
            {part}
          </mark>
        ) : (
          part
        )
      )}
    </>
  );
}

export default function ClinicalSearch({
  patientId,
  apiBaseUrl = "http://localhost:8001",
  onResultClick,
}: ClinicalSearchProps) {
  // State
  const [mode, setMode] = useState<SearchMode>("search");
  const [searchType, setSearchType] = useState<SearchType>("hybrid");
  const [query, setQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [searchResults, setSearchResults] = useState<SearchResponse | null>(null);
  const [qaResponse, setQAResponse] = useState<QAResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [recentQueries, setRecentQueries] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Search function
  const performSearch = useCallback(async () => {
    if (!query.trim()) return;

    setIsLoading(true);
    setError(null);

    try {
      if (mode === "search") {
        const response = await fetch(`${apiBaseUrl}/documents/search/semantic`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            query,
            search_type: searchType,
            patient_id: patientId,
            max_results: 20,
          }),
        });

        if (!response.ok) throw new Error("Search failed");

        const data: SearchResponse = await response.json();
        setSearchResults(data);
        setQAResponse(null);
      } else {
        const response = await fetch(`${apiBaseUrl}/documents/search/qa`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            question: query,
            patient_id: patientId,
          }),
        });

        if (!response.ok) throw new Error("QA failed");

        const data: QAResponse = await response.json();
        setQAResponse(data);
        setSearchResults(null);
      }

      // Add to recent queries
      setRecentQueries((prev) => {
        const updated = [query, ...prev.filter((q) => q !== query)].slice(0, 5);
        return updated;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setIsLoading(false);
    }
  }, [query, mode, searchType, patientId, apiBaseUrl]);

  // Handle submit
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    performSearch();
  };

  // Handle suggestion click
  const handleSuggestionClick = (suggestion: string) => {
    setQuery(suggestion);
    setShowSuggestions(false);
    inputRef.current?.focus();
  };

  // Handle follow-up question click
  const handleFollowUpClick = (question: string) => {
    setQuery(question);
    setMode("qa");
    setTimeout(performSearch, 100);
  };

  return (
    <div className="bg-gradient-to-br from-slate-950 via-slate-900 to-indigo-950 text-slate-100 rounded-lg">
      {/* Page Header */}
      <div className="max-w-5xl mx-auto px-6 pt-6 pb-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
              <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
            <div>
              <h1 className="text-xl font-semibold text-white">Clinical Search</h1>
              <p className="text-sm text-slate-400">Semantic search and Q&A over clinical notes</p>
            </div>
          </div>

          {patientId && (
            <div className="px-3 py-1.5 bg-slate-800/50 rounded-lg text-sm">
              <span className="text-slate-400">Patient:</span>{" "}
              <span className="text-white font-medium">{patientId}</span>
            </div>
          )}
        </div>
      </div>

      {/* Main content */}
      <main className="max-w-5xl mx-auto px-6 pb-8">
        {/* Mode toggle */}
        <div className="flex justify-center mb-8">
          <div className="inline-flex rounded-xl bg-slate-800/50 p-1 backdrop-blur-sm">
            <button
              onClick={() => setMode("search")}
              className={`px-6 py-2.5 rounded-lg text-sm font-medium transition-all ${
                mode === "search"
                  ? "bg-indigo-600 text-white shadow-lg shadow-indigo-500/30"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <span className="flex items-center gap-2">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                Search
              </span>
            </button>
            <button
              onClick={() => setMode("qa")}
              className={`px-6 py-2.5 rounded-lg text-sm font-medium transition-all ${
                mode === "qa"
                  ? "bg-indigo-600 text-white shadow-lg shadow-indigo-500/30"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <span className="flex items-center gap-2">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Ask Question
              </span>
            </button>
          </div>
        </div>

        {/* Search box */}
        <form onSubmit={handleSubmit} className="mb-8">
          <div className="relative">
            <div className="absolute inset-0 bg-gradient-to-r from-indigo-500/20 to-purple-500/20 rounded-2xl blur-xl" />
            <div className="relative bg-slate-800/80 backdrop-blur-sm rounded-2xl border border-slate-700/50 overflow-hidden">
              <div className="flex items-center">
                <div className="pl-5">
                  {isLoading ? (
                    <svg className="w-5 h-5 text-indigo-400 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                  ) : (
                    <svg className="w-5 h-5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                  )}
                </div>
                <input
                  ref={inputRef}
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onFocus={() => setShowSuggestions(true)}
                  onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
                  placeholder={mode === "search" ? "Search clinical notes..." : "Ask a clinical question..."}
                  className="flex-1 px-4 py-4 bg-transparent text-white placeholder-slate-500 focus:outline-none text-lg"
                />
                {mode === "search" && (
                  <select
                    value={searchType}
                    onChange={(e) => setSearchType(e.target.value as SearchType)}
                    className="mr-2 px-3 py-2 bg-slate-700/50 rounded-lg text-sm text-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 cursor-pointer"
                  >
                    <option value="hybrid">Hybrid</option>
                    <option value="semantic">Semantic</option>
                    <option value="keyword">Keyword</option>
                  </select>
                )}
                <button
                  type="submit"
                  disabled={isLoading || !query.trim()}
                  className="m-2 px-6 py-2.5 bg-gradient-to-r from-indigo-600 to-purple-600 rounded-xl text-white font-medium hover:from-indigo-500 hover:to-purple-500 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {mode === "search" ? "Search" : "Ask"}
                </button>
              </div>
            </div>

            {/* Recent queries dropdown */}
            <AnimatePresence>
              {showSuggestions && recentQueries.length > 0 && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  className="absolute top-full left-0 right-0 mt-2 bg-slate-800/95 backdrop-blur-sm rounded-xl border border-slate-700/50 overflow-hidden z-20"
                >
                  <div className="p-2">
                    <p className="px-3 py-1 text-xs text-slate-500 uppercase tracking-wide">Recent</p>
                    {recentQueries.map((q, i) => (
                      <button
                        key={i}
                        onClick={() => handleSuggestionClick(q)}
                        className="w-full px-3 py-2 text-left text-slate-300 hover:bg-slate-700/50 rounded-lg transition-colors text-sm"
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </form>

        {/* Error message */}
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400"
          >
            {error}
          </motion.div>
        )}

        {/* Search results */}
        <AnimatePresence mode="wait">
          {searchResults && mode === "search" && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="space-y-4"
            >
              {/* Results header */}
              <div className="flex items-center justify-between mb-4">
                <p className="text-slate-400">
                  Found <span className="text-white font-medium">{searchResults.total_results}</span> results
                  <span className="text-slate-500 ml-2">({searchResults.search_time_ms.toFixed(1)}ms)</span>
                </p>
              </div>

              {/* Suggestions */}
              {searchResults.suggestions.length > 0 && (
                <div className="flex items-center gap-2 flex-wrap mb-4">
                  <span className="text-sm text-slate-500">Related:</span>
                  {searchResults.suggestions.map((suggestion, i) => (
                    <button
                      key={i}
                      onClick={() => handleSuggestionClick(suggestion)}
                      className="px-3 py-1 bg-slate-800/50 hover:bg-slate-700/50 rounded-full text-sm text-slate-300 transition-colors"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              )}

              {/* Results list */}
              <div className="space-y-3">
                {searchResults.results.map((result, i) => (
                  <motion.div
                    key={result.document_id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.05 }}
                    onClick={() => onResultClick?.(result.document_id)}
                    className="p-5 bg-slate-800/40 hover:bg-slate-800/60 rounded-xl border border-slate-700/30 cursor-pointer transition-all group"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-0.5 bg-indigo-500/20 text-indigo-300 text-xs rounded-full">
                          {result.document_id}
                        </span>
                        <div className="h-4 w-px bg-slate-700" />
                        <div className="flex items-center gap-1">
                          <div className="w-2 h-2 rounded-full bg-emerald-500" />
                          <span className="text-xs text-slate-400">
                            {(result.score * 100).toFixed(0)}% match
                          </span>
                        </div>
                      </div>
                      <svg className="w-5 h-5 text-slate-500 group-hover:text-indigo-400 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </div>
                    <p className="text-slate-300 text-sm leading-relaxed line-clamp-3">
                      <HighlightText text={result.content} query={query} />
                    </p>
                    {result.highlights.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-slate-700/50">
                        <p className="text-xs text-slate-500 mb-1">Highlights:</p>
                        <div className="space-y-1">
                          {result.highlights.slice(0, 2).map((h, j) => (
                            <p key={j} className="text-xs text-slate-400 italic">
                              "...{h}..."
                            </p>
                          ))}
                        </div>
                      </div>
                    )}
                  </motion.div>
                ))}
              </div>

              {searchResults.results.length === 0 && (
                <div className="text-center py-12">
                  <svg className="w-16 h-16 mx-auto text-slate-600 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <p className="text-slate-400">No results found for "{query}"</p>
                  <p className="text-sm text-slate-500 mt-1">Try different keywords or search type</p>
                </div>
              )}
            </motion.div>
          )}

          {/* QA Response */}
          {qaResponse && mode === "qa" && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="space-y-6"
            >
              {/* Answer card */}
              <div className="p-6 bg-gradient-to-br from-slate-800/60 to-indigo-900/20 rounded-2xl border border-indigo-500/20">
                <div className="flex items-center gap-2 mb-4">
                  <div className="w-8 h-8 rounded-lg bg-indigo-500/20 flex items-center justify-center">
                    <svg className="w-5 h-5 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                  </div>
                  <span className="text-sm text-indigo-300">Answer</span>
                  <div className="ml-auto flex items-center gap-2">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      qaResponse.answer.confidence >= 0.8
                        ? "bg-emerald-500/20 text-emerald-300"
                        : qaResponse.answer.confidence >= 0.5
                        ? "bg-amber-500/20 text-amber-300"
                        : "bg-red-500/20 text-red-300"
                    }`}>
                      {(qaResponse.answer.confidence * 100).toFixed(0)}% confident
                    </span>
                    <span className="text-xs text-slate-500">
                      {qaResponse.response_time_ms.toFixed(1)}ms
                    </span>
                  </div>
                </div>
                <p className="text-white text-lg leading-relaxed">
                  {qaResponse.answer.text}
                </p>
              </div>

              {/* Evidence */}
              {qaResponse.answer.evidence.length > 0 && (
                <div className="space-y-3">
                  <h3 className="text-sm text-slate-400 font-medium flex items-center gap-2">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    Evidence ({qaResponse.answer.evidence.length})
                  </h3>
                  <div className="space-y-2">
                    {qaResponse.answer.evidence.map((evidence, i) => (
                      <div
                        key={i}
                        className="p-4 bg-slate-800/40 rounded-xl border-l-2 border-indigo-500/50"
                      >
                        <p className="text-slate-300 text-sm">{evidence}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Related concepts */}
              {qaResponse.related_concepts.length > 0 && (
                <div>
                  <h3 className="text-sm text-slate-400 font-medium mb-3">Related Concepts</h3>
                  <div className="flex flex-wrap gap-2">
                    {qaResponse.related_concepts.map((concept, i) => (
                      <span
                        key={i}
                        className="px-3 py-1.5 bg-slate-800/50 rounded-lg text-sm text-slate-300 capitalize"
                      >
                        {concept}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Follow-up questions */}
              {qaResponse.follow_up_questions.length > 0 && (
                <div>
                  <h3 className="text-sm text-slate-400 font-medium mb-3">Follow-up Questions</h3>
                  <div className="space-y-2">
                    {qaResponse.follow_up_questions.map((question, i) => (
                      <button
                        key={i}
                        onClick={() => handleFollowUpClick(question)}
                        className="w-full p-3 bg-slate-800/40 hover:bg-slate-700/40 rounded-xl text-left text-slate-300 text-sm transition-colors flex items-center gap-3 group"
                      >
                        <svg className="w-4 h-4 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        {question}
                        <svg className="w-4 h-4 ml-auto text-slate-500 group-hover:text-indigo-400 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" />
                        </svg>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Sources */}
              {qaResponse.answer.source_documents.length > 0 && (
                <div className="pt-4 border-t border-slate-700/50">
                  <p className="text-xs text-slate-500">
                    Sources: {qaResponse.answer.source_documents.join(", ")}
                  </p>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Empty state */}
        {!searchResults && !qaResponse && !isLoading && (
          <div className="text-center py-16">
            <div className="w-20 h-20 mx-auto mb-6 rounded-full bg-gradient-to-br from-indigo-500/20 to-purple-500/20 flex items-center justify-center">
              <svg className="w-10 h-10 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
            <h2 className="text-xl font-medium text-white mb-2">
              {mode === "search" ? "Search clinical notes" : "Ask a clinical question"}
            </h2>
            <p className="text-slate-400 max-w-md mx-auto">
              {mode === "search"
                ? "Use semantic search to find relevant clinical information across patient records."
                : "Ask questions in natural language and get answers with evidence from clinical notes."}
            </p>

            {/* Example queries */}
            <div className="mt-8">
              <p className="text-xs text-slate-500 uppercase tracking-wide mb-3">
                {mode === "search" ? "Example searches" : "Example questions"}
              </p>
              <div className="flex flex-wrap justify-center gap-2">
                {(mode === "search"
                  ? ["diabetes medications", "blood pressure readings", "recent lab results"]
                  : ["What medications is the patient taking?", "Does the patient have diabetes?", "When was the last A1C?"]
                ).map((example, i) => (
                  <button
                    key={i}
                    onClick={() => {
                      setQuery(example);
                      inputRef.current?.focus();
                    }}
                    className="px-4 py-2 bg-slate-800/50 hover:bg-slate-700/50 rounded-lg text-sm text-slate-300 transition-colors"
                  >
                    {example}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
