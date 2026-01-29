"use client";

import * as React from "react";
import type { GraphNode } from "@/lib/api";

// Node type configuration
const NODE_CONFIG: Record<string, { color: string; icon: string }> = {
  patient: { color: "#a78bfa", icon: "M12 4.354a4 4 0 110 5.292M15 21H9m6 0a2 2 0 100-4H9a2 2 0 100 4m6 0v-4H9v4m3-14v4" },
  condition: { color: "#f87171", icon: "M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" },
  drug: { color: "#60a5fa", icon: "M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" },
  measurement: { color: "#4ade80", icon: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" },
  procedure: { color: "#fb923c", icon: "M12 14l9-5-9-5-9 5 9 5zm0 7l9-5-9-5-9 5 9 5z" },
  observation: { color: "#94a3b8", icon: "M15 12a3 3 0 11-6 0 3 3 0 016 0z M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" },
  device: { color: "#f472b6", icon: "M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" },
};

interface GraphSearchComboboxProps {
  nodes: GraphNode[];
  onSelect: (nodeId: string) => void;
  onSearch: (query: string) => void;
  className?: string;
}

export function GraphSearchCombobox({
  nodes,
  onSelect,
  onSearch,
  className = "",
}: GraphSearchComboboxProps) {
  const [query, setQuery] = React.useState("");
  const [isOpen, setIsOpen] = React.useState(false);
  const [selectedIndex, setSelectedIndex] = React.useState(0);
  const inputRef = React.useRef<HTMLInputElement>(null);
  const listRef = React.useRef<HTMLDivElement>(null);

  // Filter nodes based on query
  const filteredNodes = React.useMemo(() => {
    if (!query.trim()) return [];
    const lowerQuery = query.toLowerCase();
    return nodes
      .filter(
        (n) =>
          n.label.toLowerCase().includes(lowerQuery) ||
          n.omop_concept_id?.toString().includes(lowerQuery) ||
          n.node_type.toLowerCase().includes(lowerQuery)
      )
      .slice(0, 10); // Limit to 10 suggestions
  }, [nodes, query]);

  // Handle input change
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newQuery = e.target.value;
    setQuery(newQuery);
    onSearch(newQuery);
    setIsOpen(newQuery.length > 0);
    setSelectedIndex(0);
  };

  // Handle selection
  const handleSelect = (nodeId: string) => {
    onSelect(nodeId);
    setIsOpen(false);
    setQuery("");
    inputRef.current?.blur();
  };

  // Handle keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!isOpen || filteredNodes.length === 0) return;

    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setSelectedIndex((prev) =>
          prev < filteredNodes.length - 1 ? prev + 1 : prev
        );
        break;
      case "ArrowUp":
        e.preventDefault();
        setSelectedIndex((prev) => (prev > 0 ? prev - 1 : 0));
        break;
      case "Enter":
        e.preventDefault();
        if (filteredNodes[selectedIndex]) {
          handleSelect(filteredNodes[selectedIndex].id);
        }
        break;
      case "Escape":
        e.preventDefault();
        setIsOpen(false);
        inputRef.current?.blur();
        break;
    }
  };

  // Scroll selected item into view
  React.useEffect(() => {
    if (listRef.current && isOpen) {
      const selectedElement = listRef.current.children[selectedIndex] as HTMLElement;
      if (selectedElement) {
        selectedElement.scrollIntoView({ block: "nearest" });
      }
    }
  }, [selectedIndex, isOpen]);

  // Close dropdown when clicking outside
  React.useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        inputRef.current &&
        !inputRef.current.contains(e.target as Node) &&
        listRef.current &&
        !listRef.current.contains(e.target as Node)
      ) {
        setIsOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div className={`relative ${className}`}>
      {/* Search Input */}
      <div className="bg-slate-900/95 backdrop-blur-sm rounded-lg border border-slate-800 overflow-hidden">
        <div className="flex items-center px-3 py-2 gap-2">
          <svg
            className="w-4 h-4 text-slate-500 flex-shrink-0"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
          <input
            ref={inputRef}
            type="text"
            placeholder="Search nodes..."
            value={query}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            onFocus={() => query.length > 0 && setIsOpen(true)}
            className="bg-transparent text-sm text-slate-200 placeholder-slate-500 outline-none w-full"
          />
          {query && (
            <button
              onClick={() => {
                setQuery("");
                onSearch("");
                setIsOpen(false);
              }}
              className="text-slate-500 hover:text-slate-300 flex-shrink-0"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Dropdown */}
      {isOpen && filteredNodes.length > 0 && (
        <div
          ref={listRef}
          className="absolute top-full left-0 right-0 mt-1 bg-slate-900/98 backdrop-blur-sm border border-slate-700 rounded-lg shadow-2xl overflow-hidden z-50 max-h-80 overflow-y-auto"
        >
          {filteredNodes.map((node, index) => {
            const config = NODE_CONFIG[node.node_type] || NODE_CONFIG.observation;
            return (
              <button
                key={node.id}
                className={`w-full flex items-center gap-3 px-3 py-2.5 text-left transition-colors ${
                  index === selectedIndex
                    ? "bg-slate-800"
                    : "hover:bg-slate-800/50"
                }`}
                onClick={() => handleSelect(node.id)}
                onMouseEnter={() => setSelectedIndex(index)}
              >
                {/* Node type icon */}
                <div
                  className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
                  style={{ backgroundColor: `${config.color}20` }}
                >
                  <svg
                    className="w-4 h-4"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke={config.color}
                    strokeWidth={1.5}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d={config.icon} />
                  </svg>
                </div>

                {/* Node info */}
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-slate-200 truncate">{node.label}</div>
                  <div className="flex items-center gap-2 text-xs text-slate-500">
                    <span className="capitalize">{node.node_type}</span>
                    {node.omop_concept_id && (
                      <>
                        <span className="text-slate-700">•</span>
                        <span className="font-mono text-indigo-400">
                          {node.omop_concept_id}
                        </span>
                      </>
                    )}
                  </div>
                </div>

                {/* Navigate icon */}
                <svg
                  className="w-4 h-4 text-slate-600 flex-shrink-0"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M13 7l5 5m0 0l-5 5m5-5H6"
                  />
                </svg>
              </button>
            );
          })}

          {/* Result count */}
          <div className="px-3 py-2 border-t border-slate-800 text-xs text-slate-500">
            {filteredNodes.length} result{filteredNodes.length !== 1 ? "s" : ""}
            {nodes.length > 10 && query && " (showing top 10)"}
          </div>
        </div>
      )}

      {/* No results */}
      {isOpen && query && filteredNodes.length === 0 && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-slate-900/98 backdrop-blur-sm border border-slate-700 rounded-lg shadow-2xl overflow-hidden z-50">
          <div className="px-3 py-4 text-center text-sm text-slate-500">
            No nodes found matching &quot;{query}&quot;
          </div>
        </div>
      )}
    </div>
  );
}
