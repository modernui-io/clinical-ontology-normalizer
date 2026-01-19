"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  MessageSquare,
  X,
  Send,
  Loader2,
  Minimize2,
  Maximize2,
  Sparkles,
  Code,
  Copy,
  Check,
  ExternalLink,
} from "lucide-react";

// Types
interface CodeSuggestion {
  code: string;
  display: string;
  system: string;
  relevance: number;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  codeSuggestions?: CodeSuggestion[];
}

interface AssistantWidgetProps {
  className?: string;
  defaultExpanded?: boolean;
  onExpandedChange?: (expanded: boolean) => void;
  position?: "bottom-right" | "bottom-left";
  context?: {
    patientId?: string;
    documentId?: string;
    pageType?: string;
  };
}

// Suggested quick prompts
const QUICK_PROMPTS = [
  "Find ICD-10 code for diabetes",
  "What are drug interactions for metformin?",
  "Suggest CPT codes for office visit",
  "Explain SNOMED concept hierarchy",
];

export function AssistantWidget({
  className,
  defaultExpanded = false,
  onExpandedChange,
  position = "bottom-right",
  context,
}: AssistantWidgetProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const [isMinimized, setIsMinimized] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [copiedCode, setCopiedCode] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Focus input when expanded
  useEffect(() => {
    if (isExpanded && !isMinimized) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isExpanded, isMinimized]);

  // Notify parent of expanded state changes
  useEffect(() => {
    onExpandedChange?.(isExpanded);
  }, [isExpanded, onExpandedChange]);

  // Create or get session
  const ensureSession = useCallback(async (): Promise<string> => {
    if (sessionId) return sessionId;

    try {
      const response = await fetch("http://localhost:8000/api/v1/assistant/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "widget-user",
          context: context || {},
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setSessionId(data.session_id);
        return data.session_id;
      }
    } catch (error) {
      console.error("Failed to create session:", error);
    }

    // Fallback session ID
    const fallbackId = `widget-${Date.now()}`;
    setSessionId(fallbackId);
    return fallbackId;
  }, [sessionId, context]);

  // Send message to assistant
  const sendMessage = async (content: string) => {
    if (!content.trim() || isLoading) return;

    const userMessage: Message = {
      id: `msg-${Date.now()}`,
      role: "user",
      content: content.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue("");
    setIsLoading(true);

    try {
      const currentSessionId = await ensureSession();

      const response = await fetch(
        `http://localhost:8000/api/v1/assistant/sessions/${currentSessionId}/chat`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: content.trim(),
            context: context || {},
          }),
        }
      );

      if (response.ok) {
        const data = await response.json();
        const assistantMessage: Message = {
          id: `msg-${Date.now()}-assistant`,
          role: "assistant",
          content: data.response || data.message || "I understand your question. Let me help you with that.",
          timestamp: new Date(),
          codeSuggestions: data.code_suggestions || data.suggestions || [],
        };
        setMessages((prev) => [...prev, assistantMessage]);
      } else {
        throw new Error("Failed to get response");
      }
    } catch (error) {
      console.error("Failed to send message:", error);
      // Mock response for demo
      const mockResponse: Message = {
        id: `msg-${Date.now()}-assistant`,
        role: "assistant",
        content: getMockResponse(content),
        timestamp: new Date(),
        codeSuggestions: getMockSuggestions(content),
      };
      setMessages((prev) => [...prev, mockResponse]);
    } finally {
      setIsLoading(false);
    }
  };

  // Mock response generator for demo
  const getMockResponse = (query: string): string => {
    const lowerQuery = query.toLowerCase();
    if (lowerQuery.includes("icd") || lowerQuery.includes("diabetes")) {
      return "I found several ICD-10 codes related to your query. Here are the most relevant codes for diabetes mellitus:";
    }
    if (lowerQuery.includes("cpt") || lowerQuery.includes("office visit")) {
      return "For office visits, here are the commonly used CPT codes based on the level of complexity:";
    }
    if (lowerQuery.includes("drug") || lowerQuery.includes("interaction")) {
      return "I can help you check drug interactions. Here are some relevant findings:";
    }
    if (lowerQuery.includes("snomed")) {
      return "SNOMED CT provides a comprehensive clinical terminology. Here's information about the concept hierarchy:";
    }
    return "I can help you with clinical coding queries, drug interactions, and terminology lookups. What specific information are you looking for?";
  };

  // Mock suggestions generator for demo
  const getMockSuggestions = (query: string): CodeSuggestion[] => {
    const lowerQuery = query.toLowerCase();
    if (lowerQuery.includes("icd") || lowerQuery.includes("diabetes")) {
      return [
        { code: "E11.9", display: "Type 2 diabetes mellitus without complications", system: "ICD-10-CM", relevance: 0.95 },
        { code: "E11.65", display: "Type 2 diabetes mellitus with hyperglycemia", system: "ICD-10-CM", relevance: 0.88 },
        { code: "E10.9", display: "Type 1 diabetes mellitus without complications", system: "ICD-10-CM", relevance: 0.82 },
      ];
    }
    if (lowerQuery.includes("cpt") || lowerQuery.includes("office visit")) {
      return [
        { code: "99213", display: "Office visit, established patient, low complexity", system: "CPT", relevance: 0.92 },
        { code: "99214", display: "Office visit, established patient, moderate complexity", system: "CPT", relevance: 0.88 },
        { code: "99215", display: "Office visit, established patient, high complexity", system: "CPT", relevance: 0.75 },
      ];
    }
    return [];
  };

  // Copy code to clipboard
  const copyCode = async (code: string) => {
    try {
      await navigator.clipboard.writeText(code);
      setCopiedCode(code);
      setTimeout(() => setCopiedCode(null), 2000);
    } catch (error) {
      console.error("Failed to copy:", error);
    }
  };

  // Handle quick prompt click
  const handleQuickPrompt = (prompt: string) => {
    sendMessage(prompt);
  };

  // Toggle expanded state
  const toggleExpanded = () => {
    if (isExpanded) {
      setIsExpanded(false);
      setIsMinimized(false);
    } else {
      setIsExpanded(true);
    }
  };

  // Position classes
  const positionClasses = position === "bottom-right" ? "right-4" : "left-4";

  // Collapsed button (floating action button)
  if (!isExpanded) {
    return (
      <div className={cn("fixed bottom-4 z-50", positionClasses, className)}>
        <Button
          onClick={toggleExpanded}
          size="lg"
          className="h-14 w-14 rounded-full shadow-lg hover:shadow-xl transition-all"
        >
          <MessageSquare className="h-6 w-6" />
        </Button>
        {messages.length > 0 && (
          <span className="absolute -top-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-destructive text-[10px] font-medium text-white">
            {messages.filter((m) => m.role === "assistant").length}
          </span>
        )}
      </div>
    );
  }

  // Minimized state (collapsed to title bar)
  if (isMinimized) {
    return (
      <div className={cn("fixed bottom-4 z-50", positionClasses, className)}>
        <div className="w-80 rounded-lg border bg-background shadow-xl">
          <div className="flex items-center justify-between p-3 border-b">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-primary" />
              <span className="font-medium text-sm">AI Assistant</span>
            </div>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={() => setIsMinimized(false)}
              >
                <Maximize2 className="h-3.5 w-3.5" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={toggleExpanded}
              >
                <X className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Expanded chat widget
  return (
    <div className={cn("fixed bottom-4 z-50", positionClasses, className)}>
      <div className="w-96 rounded-lg border bg-background shadow-xl flex flex-col max-h-[600px]">
        {/* Header */}
        <div className="flex items-center justify-between p-3 border-b shrink-0">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" />
            <span className="font-medium">AI Coding Assistant</span>
            {context?.pageType && (
              <Badge variant="secondary" className="text-xs">
                {context.pageType}
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={() => setIsMinimized(true)}
              title="Minimize"
            >
              <Minimize2 className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={toggleExpanded}
              title="Close"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Messages Area */}
        <ScrollArea className="flex-1 min-h-0">
          <div className="p-4 space-y-4">
            {messages.length === 0 ? (
              // Empty state with quick prompts
              <div className="space-y-4">
                <div className="text-center py-6">
                  <div className="mx-auto w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center mb-3">
                    <Sparkles className="h-6 w-6 text-primary" />
                  </div>
                  <h4 className="font-medium mb-1">AI Coding Assistant</h4>
                  <p className="text-sm text-muted-foreground">
                    Ask me about clinical codes, drug interactions, or terminology
                  </p>
                </div>

                <div className="space-y-2">
                  <p className="text-xs text-muted-foreground font-medium">
                    Quick prompts
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {QUICK_PROMPTS.map((prompt, index) => (
                      <button
                        key={index}
                        onClick={() => handleQuickPrompt(prompt)}
                        className="text-xs px-3 py-1.5 rounded-full border bg-muted/50 hover:bg-muted transition-colors text-left"
                      >
                        {prompt}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              // Messages
              messages.map((message) => (
                <div
                  key={message.id}
                  className={cn(
                    "flex",
                    message.role === "user" ? "justify-end" : "justify-start"
                  )}
                >
                  <div
                    className={cn(
                      "max-w-[85%] rounded-lg px-3 py-2",
                      message.role === "user"
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted"
                    )}
                  >
                    <p className="text-sm">{message.content}</p>

                    {/* Code suggestions */}
                    {message.codeSuggestions && message.codeSuggestions.length > 0 && (
                      <div className="mt-3 space-y-2">
                        {message.codeSuggestions.map((suggestion, index) => (
                          <div
                            key={index}
                            className="p-2 rounded bg-background border text-foreground"
                          >
                            <div className="flex items-center justify-between gap-2">
                              <div className="flex items-center gap-2 min-w-0">
                                <Code className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                                <code className="text-xs font-mono font-medium">
                                  {suggestion.code}
                                </code>
                                <Badge variant="outline" className="text-[10px] shrink-0">
                                  {suggestion.system}
                                </Badge>
                              </div>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-6 w-6 shrink-0"
                                onClick={() => copyCode(suggestion.code)}
                              >
                                {copiedCode === suggestion.code ? (
                                  <Check className="h-3 w-3 text-green-500" />
                                ) : (
                                  <Copy className="h-3 w-3" />
                                )}
                              </Button>
                            </div>
                            <p className="text-xs text-muted-foreground mt-1 truncate">
                              {suggestion.display}
                            </p>
                          </div>
                        ))}
                      </div>
                    )}

                    <p className="text-[10px] mt-1 opacity-70">
                      {message.timestamp.toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </p>
                  </div>
                </div>
              ))
            )}

            {/* Loading indicator */}
            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-muted rounded-lg px-3 py-2">
                  <div className="flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span className="text-sm text-muted-foreground">
                      Thinking...
                    </span>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </ScrollArea>

        {/* Input Area */}
        <div className="p-3 border-t shrink-0">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              sendMessage(inputValue);
            }}
            className="flex items-center gap-2"
          >
            <Input
              ref={inputRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Ask about codes, drugs, terminology..."
              className="flex-1 text-sm"
              disabled={isLoading}
            />
            <Button
              type="submit"
              size="icon"
              disabled={!inputValue.trim() || isLoading}
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </form>
          <div className="flex items-center justify-between mt-2">
            <p className="text-[10px] text-muted-foreground">
              Press Enter to send
            </p>
            <a
              href="/assistant"
              className="text-[10px] text-primary hover:underline flex items-center gap-1"
            >
              Open full assistant
              <ExternalLink className="h-3 w-3" />
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}

export default AssistantWidget;
