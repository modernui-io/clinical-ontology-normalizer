"use client";

import * as React from "react";
import * as ContextMenu from "@radix-ui/react-context-menu";

interface NodeContextMenuProps {
  children: React.ReactNode;
  nodeId: string;
  nodeLabel: string;
  nodeType: string;
  omopConceptId: number | null;
  isPinned: boolean;
  isHidden: boolean;
  onExpandNeighbors: (nodeId: string) => void;
  onCollapseNeighbors: (nodeId: string) => void;
  onHideNode: (nodeId: string) => void;
  onShowNode: (nodeId: string) => void;
  onPinNode: (nodeId: string) => void;
  onUnpinNode: (nodeId: string) => void;
  onCopyOmopId: (omopId: number) => void;
  onFocusNode: (nodeId: string) => void;
  neighborCount: number;
  hiddenNeighborCount: number;
}

export function NodeContextMenu({
  children,
  nodeId,
  nodeLabel,
  nodeType,
  omopConceptId,
  isPinned,
  isHidden,
  onExpandNeighbors,
  onCollapseNeighbors,
  onHideNode,
  onShowNode,
  onPinNode,
  onUnpinNode,
  onCopyOmopId,
  onFocusNode,
  neighborCount,
  hiddenNeighborCount,
}: NodeContextMenuProps) {
  const [copiedFeedback, setCopiedFeedback] = React.useState(false);

  const handleCopyOmopId = () => {
    if (omopConceptId) {
      navigator.clipboard.writeText(omopConceptId.toString());
      onCopyOmopId(omopConceptId);
      setCopiedFeedback(true);
      setTimeout(() => setCopiedFeedback(false), 1500);
    }
  };

  const handleCopyNodeId = () => {
    navigator.clipboard.writeText(nodeId);
    setCopiedFeedback(true);
    setTimeout(() => setCopiedFeedback(false), 1500);
  };

  return (
    <ContextMenu.Root>
      <ContextMenu.Trigger asChild>{children}</ContextMenu.Trigger>
      <ContextMenu.Portal>
        <ContextMenu.Content
          className="min-w-[200px] bg-slate-900/98 backdrop-blur-sm border border-slate-700 rounded-xl shadow-2xl p-1.5 z-50 animate-in fade-in zoom-in-95 duration-100"
        >
          {/* Header */}
          <div className="px-3 py-2 border-b border-slate-800 mb-1">
            <div className="text-sm font-medium text-slate-200 truncate max-w-[180px]">
              {nodeLabel}
            </div>
            <div className="text-xs text-slate-500 capitalize">{nodeType}</div>
          </div>

          {/* Expand/Collapse Neighbors */}
          {hiddenNeighborCount > 0 ? (
            <ContextMenu.Item
              className="flex items-center gap-2 px-3 py-2 text-sm text-slate-200 hover:bg-slate-800 rounded-lg cursor-pointer outline-none"
              onSelect={() => onExpandNeighbors(nodeId)}
            >
              <svg className="w-4 h-4 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
              </svg>
              <span>Expand neighbors</span>
              <span className="ml-auto text-xs text-slate-500 bg-slate-800 px-1.5 py-0.5 rounded">
                {hiddenNeighborCount}
              </span>
            </ContextMenu.Item>
          ) : neighborCount > 0 ? (
            <ContextMenu.Item
              className="flex items-center gap-2 px-3 py-2 text-sm text-slate-200 hover:bg-slate-800 rounded-lg cursor-pointer outline-none"
              onSelect={() => onCollapseNeighbors(nodeId)}
            >
              <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
              </svg>
              <span>Collapse neighbors</span>
            </ContextMenu.Item>
          ) : null}

          {/* Focus on this node */}
          <ContextMenu.Item
            className="flex items-center gap-2 px-3 py-2 text-sm text-slate-200 hover:bg-slate-800 rounded-lg cursor-pointer outline-none"
            onSelect={() => onFocusNode(nodeId)}
          >
            <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7" />
            </svg>
            <span>Focus on node</span>
          </ContextMenu.Item>

          <ContextMenu.Separator className="h-px bg-slate-800 my-1" />

          {/* Hide/Show Node */}
          {isHidden ? (
            <ContextMenu.Item
              className="flex items-center gap-2 px-3 py-2 text-sm text-slate-200 hover:bg-slate-800 rounded-lg cursor-pointer outline-none"
              onSelect={() => onShowNode(nodeId)}
            >
              <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
              </svg>
              <span>Show node</span>
            </ContextMenu.Item>
          ) : (
            <ContextMenu.Item
              className="flex items-center gap-2 px-3 py-2 text-sm text-slate-200 hover:bg-slate-800 rounded-lg cursor-pointer outline-none"
              onSelect={() => onHideNode(nodeId)}
            >
              <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
              </svg>
              <span>Hide node</span>
            </ContextMenu.Item>
          )}

          {/* Pin/Unpin Position */}
          {isPinned ? (
            <ContextMenu.Item
              className="flex items-center gap-2 px-3 py-2 text-sm text-slate-200 hover:bg-slate-800 rounded-lg cursor-pointer outline-none"
              onSelect={() => onUnpinNode(nodeId)}
            >
              <svg className="w-4 h-4 text-amber-400" fill="currentColor" viewBox="0 0 24 24">
                <path d="M16 12V4h1V2H7v2h1v8l-2 2v2h5.2v6h1.6v-6H18v-2l-2-2z" />
              </svg>
              <span>Unpin position</span>
            </ContextMenu.Item>
          ) : (
            <ContextMenu.Item
              className="flex items-center gap-2 px-3 py-2 text-sm text-slate-200 hover:bg-slate-800 rounded-lg cursor-pointer outline-none"
              onSelect={() => onPinNode(nodeId)}
            >
              <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 12V4h1V2H7v2h1v8l-2 2v2h5.2v6h1.6v-6H18v-2l-2-2z" />
              </svg>
              <span>Pin position</span>
            </ContextMenu.Item>
          )}

          <ContextMenu.Separator className="h-px bg-slate-800 my-1" />

          {/* Copy OMOP ID */}
          {omopConceptId && (
            <ContextMenu.Item
              className="flex items-center gap-2 px-3 py-2 text-sm text-slate-200 hover:bg-slate-800 rounded-lg cursor-pointer outline-none"
              onSelect={handleCopyOmopId}
            >
              <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
              <span>{copiedFeedback ? "Copied!" : "Copy OMOP ID"}</span>
              <span className="ml-auto text-xs text-indigo-400 font-mono">{omopConceptId}</span>
            </ContextMenu.Item>
          )}

          {/* Copy Node ID */}
          <ContextMenu.Item
            className="flex items-center gap-2 px-3 py-2 text-sm text-slate-200 hover:bg-slate-800 rounded-lg cursor-pointer outline-none"
            onSelect={handleCopyNodeId}
          >
            <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
            </svg>
            <span>Copy node ID</span>
          </ContextMenu.Item>
        </ContextMenu.Content>
      </ContextMenu.Portal>
    </ContextMenu.Root>
  );
}

// Simpler standalone context menu for use without wrapping
export interface ContextMenuState {
  isOpen: boolean;
  x: number;
  y: number;
  nodeId: string | null;
}

export function useNodeContextMenu() {
  const [menuState, setMenuState] = React.useState<ContextMenuState>({
    isOpen: false,
    x: 0,
    y: 0,
    nodeId: null,
  });

  const openMenu = React.useCallback((x: number, y: number, nodeId: string) => {
    setMenuState({ isOpen: true, x, y, nodeId });
  }, []);

  const closeMenu = React.useCallback(() => {
    setMenuState((prev) => ({ ...prev, isOpen: false }));
  }, []);

  return { menuState, openMenu, closeMenu };
}
