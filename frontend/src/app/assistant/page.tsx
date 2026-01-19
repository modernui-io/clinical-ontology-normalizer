"use client";

import { useState, useEffect, useRef } from "react";
import {
  Loader2,
  Send,
  Bot,
  User,
  Sparkles,
  Copy,
  Check,
  Trash2,
  Plus,
  FileText,
  UserCircle,
  ChevronRight,
  History,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";

// ============================================================================
// Types
// ============================================================================

interface CodeSuggestion {
  code: string;
  display_name: string;
  system: string;
  confidence: string;
  score: number;
  description: string | null;
  reasoning: string | null;
}

interface Citation {
  source: string;
  code: string | null;
  display: string | null;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  code_suggestions: CodeSuggestion[];
  citations: Citation[];
}

interface Session {
  id: string;
  user_id: string;
  context: {
    session_id: string;
    user_id: string;
    patient_id: string | null;
    document_id: string | null;
    patient_name: string | null;
    document_name: string | null;
  };
  message_count: number;
  created_at: string;
  updated_at: string;
}

// ============================================================================
// Components
// ============================================================================

function MessageBubble({
  message,
  onUseSuggestion,
}: {
  message: Message;
  onUseSuggestion: (suggestion: CodeSuggestion) => void;
}) {
  const [copiedCode, setCopiedCode] = useState<string | null>(null);
  const isUser = message.role === "user";

  const copyToClipboard = async (text: string, code: string) => {
    await navigator.clipboard.writeText(text);
    setCopiedCode(code);
    setTimeout(() => setCopiedCode(null), 2000);
    toast.success("Copied to clipboard");
  };

  return (
    <div
      className={cn(
        "flex gap-3 mb-4",
        isUser ? "flex-row-reverse" : "flex-row"
      )}
    >
      <div
        className={cn(
          "flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center",
          isUser ? "bg-primary text-primary-foreground" : "bg-muted"
        )}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>
      <div
        className={cn(
          "max-w-[80%] space-y-2",
          isUser ? "items-end" : "items-start"
        )}
      >
        <div
          className={cn(
            "rounded-lg px-4 py-2",
            isUser
              ? "bg-primary text-primary-foreground"
              : "bg-muted"
          )}
        >
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        </div>

        {/* Code Suggestions */}
        {message.code_suggestions.length > 0 && (
          <div className="space-y-2 mt-2">
            {message.code_suggestions.map((suggestion, idx) => (
              <Card key={idx} className="border-l-4 border-l-primary">
                <CardContent className="p-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <code className="text-sm font-mono font-medium">
                          {suggestion.code}
                        </code>
                        <Badge
                          variant={
                            suggestion.system === "icd10"
                              ? "default"
                              : suggestion.system === "cpt"
                              ? "secondary"
                              : "outline"
                          }
                          className="text-xs"
                        >
                          {suggestion.system.toUpperCase()}
                        </Badge>
                        <Badge
                          variant={
                            suggestion.confidence === "high"
                              ? "default"
                              : suggestion.confidence === "medium"
                              ? "secondary"
                              : "outline"
                          }
                          className={cn(
                            "text-xs",
                            suggestion.confidence === "high" && "bg-green-500"
                          )}
                        >
                          {Math.round(suggestion.score * 100)}%
                        </Badge>
                      </div>
                      <p className="text-sm">{suggestion.display_name}</p>
                      {suggestion.reasoning && (
                        <p className="text-xs text-muted-foreground">
                          {suggestion.reasoning}
                        </p>
                      )}
                    </div>
                    <div className="flex gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 p-0"
                        onClick={() =>
                          copyToClipboard(
                            `${suggestion.code} - ${suggestion.display_name}`,
                            suggestion.code
                          )
                        }
                      >
                        {copiedCode === suggestion.code ? (
                          <Check className="h-3 w-3" />
                        ) : (
                          <Copy className="h-3 w-3" />
                        )}
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-7 text-xs"
                        onClick={() => onUseSuggestion(suggestion)}
                      >
                        Use
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Citations */}
        {message.citations.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1">
            {message.citations.map((citation, idx) => (
              <Badge key={idx} variant="outline" className="text-xs">
                {citation.source}
                {citation.code && `: ${citation.code}`}
              </Badge>
            ))}
          </div>
        )}

        <p className="text-xs text-muted-foreground">
          {new Date(message.timestamp).toLocaleTimeString()}
        </p>
      </div>
    </div>
  );
}

function SessionSidebar({
  sessions,
  currentSession,
  onSelectSession,
  onNewSession,
  onDeleteSession,
  isOpen,
  onClose,
}: {
  sessions: Session[];
  currentSession: Session | null;
  onSelectSession: (session: Session) => void;
  onNewSession: () => void;
  onDeleteSession: (sessionId: string) => void;
  isOpen: boolean;
  onClose: () => void;
}) {
  return (
    <div
      className={cn(
        "fixed inset-y-0 left-0 z-50 w-80 bg-background border-r transform transition-transform duration-200 lg:relative lg:translate-x-0",
        isOpen ? "translate-x-0" : "-translate-x-full"
      )}
    >
      <div className="flex flex-col h-full">
        <div className="p-4 border-b flex items-center justify-between">
          <h2 className="font-semibold flex items-center gap-2">
            <History className="h-4 w-4" />
            Conversations
          </h2>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={onNewSession}>
              <Plus className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="lg:hidden"
              onClick={onClose}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>
        <ScrollArea className="flex-1">
          <div className="p-2 space-y-1">
            {sessions.length === 0 ? (
              <p className="text-sm text-muted-foreground p-4 text-center">
                No conversations yet
              </p>
            ) : (
              sessions.map((session) => (
                <div
                  key={session.id}
                  className={cn(
                    "p-3 rounded-md cursor-pointer group hover:bg-muted transition-colors",
                    currentSession?.id === session.id && "bg-muted"
                  )}
                  onClick={() => {
                    onSelectSession(session);
                    onClose();
                  }}
                >
                  <div className="flex items-start justify-between">
                    <div className="space-y-1 flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        {session.context.patient_name ? (
                          <UserCircle className="h-4 w-4 text-muted-foreground" />
                        ) : session.context.document_name ? (
                          <FileText className="h-4 w-4 text-muted-foreground" />
                        ) : (
                          <Bot className="h-4 w-4 text-muted-foreground" />
                        )}
                        <span className="text-sm font-medium truncate">
                          {session.context.patient_name ||
                            session.context.document_name ||
                            "General"}
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {session.message_count} messages
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {new Date(session.updated_at).toLocaleDateString()}
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteSession(session.id);
                      }}
                    >
                      <Trash2 className="h-3 w-3 text-muted-foreground" />
                    </Button>
                  </div>
                </div>
              ))
            )}
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}

// ============================================================================
// Main Page
// ============================================================================

export default function AssistantPage() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSession, setCurrentSession] = useState<Session | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Load sessions
  useEffect(() => {
    const fetchSessions = async () => {
      try {
        const response = await fetch(
          "http://localhost:8000/assistant/sessions?user_id=demo-user"
        );
        if (response.ok) {
          const data = await response.json();
          setSessions(data.sessions);

          // Create a new session if none exist
          if (data.sessions.length === 0) {
            await createNewSession();
          } else {
            // Select the most recent session
            setCurrentSession(data.sessions[0]);
            await loadSessionHistory(data.sessions[0].id);
          }
        }
      } catch (error) {
        console.error("Failed to fetch sessions:", error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchSessions();
  }, []);

  const createNewSession = async () => {
    try {
      const response = await fetch(
        "http://localhost:8000/assistant/sessions?user_id=demo-user",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({}),
        }
      );

      if (response.ok) {
        const session = await response.json();
        setSessions((prev) => [session, ...prev]);
        setCurrentSession(session);
        setMessages([]);
      }
    } catch (error) {
      toast.error("Failed to create session");
    }
  };

  const loadSessionHistory = async (sessionId: string) => {
    try {
      const response = await fetch(
        `http://localhost:8000/assistant/sessions/${sessionId}/history`
      );
      if (response.ok) {
        const data = await response.json();
        setMessages(data.messages);
      }
    } catch (error) {
      console.error("Failed to load history:", error);
    }
  };

  const selectSession = async (session: Session) => {
    setCurrentSession(session);
    await loadSessionHistory(session.id);
  };

  const deleteSession = async (sessionId: string) => {
    try {
      const response = await fetch(
        `http://localhost:8000/assistant/sessions/${sessionId}`,
        { method: "DELETE" }
      );

      if (response.ok) {
        setSessions((prev) => prev.filter((s) => s.id !== sessionId));
        if (currentSession?.id === sessionId) {
          if (sessions.length > 1) {
            const remaining = sessions.filter((s) => s.id !== sessionId);
            setCurrentSession(remaining[0]);
            await loadSessionHistory(remaining[0].id);
          } else {
            await createNewSession();
          }
        }
        toast.success("Conversation deleted");
      }
    } catch (error) {
      toast.error("Failed to delete conversation");
    }
  };

  const clearHistory = async () => {
    if (!currentSession) return;

    try {
      const response = await fetch(
        `http://localhost:8000/assistant/sessions/${currentSession.id}/history`,
        { method: "DELETE" }
      );

      if (response.ok) {
        setMessages([]);
        toast.success("History cleared");
      }
    } catch (error) {
      toast.error("Failed to clear history");
    }
  };

  const sendMessage = async () => {
    if (!input.trim() || !currentSession || isSending) return;

    const userMessage = input.trim();
    setInput("");
    setIsSending(true);

    // Optimistically add user message
    const tempUserMsg: Message = {
      id: `temp-${Date.now()}`,
      role: "user",
      content: userMessage,
      timestamp: new Date().toISOString(),
      code_suggestions: [],
      citations: [],
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      const response = await fetch("http://localhost:8000/assistant/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: currentSession.id,
          message: userMessage,
        }),
      });

      if (response.ok) {
        const data = await response.json();

        // Replace temp message with actual and add assistant response
        setMessages((prev) => {
          const filtered = prev.filter((m) => m.id !== tempUserMsg.id);
          return [
            ...filtered,
            {
              id: `user-${Date.now()}`,
              role: "user" as const,
              content: userMessage,
              timestamp: new Date().toISOString(),
              code_suggestions: [],
              citations: [],
            },
            {
              id: data.message.id,
              role: "assistant" as const,
              content: data.message.content,
              timestamp: data.message.timestamp,
              code_suggestions: data.suggestions,
              citations: data.citations,
            },
          ];
        });

        // Update session message count
        setSessions((prev) =>
          prev.map((s) =>
            s.id === currentSession.id
              ? { ...s, message_count: s.message_count + 2 }
              : s
          )
        );
      } else {
        throw new Error("Failed to send message");
      }
    } catch (error) {
      // Remove optimistic message on error
      setMessages((prev) => prev.filter((m) => m.id !== tempUserMsg.id));
      toast.error("Failed to send message");
    } finally {
      setIsSending(false);
    }
  };

  const handleUseSuggestion = (suggestion: CodeSuggestion) => {
    toast.success(`Code ${suggestion.code} selected`, {
      description: suggestion.display_name,
    });
    // In a real app, this would integrate with a coding workflow
  };

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-4rem)]">
      {/* Sidebar Overlay for Mobile */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Session Sidebar */}
      <SessionSidebar
        sessions={sessions}
        currentSession={currentSession}
        onSelectSession={selectSession}
        onNewSession={createNewSession}
        onDeleteSession={deleteSession}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="border-b p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="sm"
              className="lg:hidden"
              onClick={() => setSidebarOpen(true)}
            >
              <History className="h-4 w-4" />
            </Button>
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-md bg-primary/10">
                <Sparkles className="h-5 w-5 text-primary" />
              </div>
              <div>
                <h1 className="font-semibold">AI Coding Assistant</h1>
                {currentSession?.context.patient_name && (
                  <p className="text-xs text-muted-foreground">
                    Patient: {currentSession.context.patient_name}
                  </p>
                )}
                {currentSession?.context.document_name && (
                  <p className="text-xs text-muted-foreground">
                    Document: {currentSession.context.document_name}
                  </p>
                )}
              </div>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={clearHistory}
            disabled={messages.length === 0}
          >
            <Trash2 className="h-4 w-4 mr-2" />
            Clear
          </Button>
        </div>

        {/* Messages */}
        <ScrollArea className="flex-1 p-4">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="p-4 rounded-full bg-primary/10 mb-4">
                <Sparkles className="h-10 w-10 text-primary" />
              </div>
              <h2 className="text-xl font-semibold mb-2">
                Clinical Coding Assistant
              </h2>
              <p className="text-muted-foreground max-w-md mb-6">
                Ask me about clinical codes, documentation requirements, or get
                coding suggestions based on clinical descriptions.
              </p>
              <div className="grid gap-2 max-w-md w-full">
                {[
                  "What ICD-10 codes are appropriate for Type 2 diabetes?",
                  "Explain the difference between 99213 and 99214",
                  "What documentation is needed for hypertension coding?",
                ].map((suggestion, idx) => (
                  <Button
                    key={idx}
                    variant="outline"
                    className="justify-start text-left h-auto p-3"
                    onClick={() => {
                      setInput(suggestion);
                    }}
                  >
                    <ChevronRight className="h-4 w-4 mr-2 flex-shrink-0" />
                    <span className="text-sm">{suggestion}</span>
                  </Button>
                ))}
              </div>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto">
              {messages.map((message) => (
                <MessageBubble
                  key={message.id}
                  message={message}
                  onUseSuggestion={handleUseSuggestion}
                />
              ))}
              {isSending && (
                <div className="flex gap-3 mb-4">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-muted flex items-center justify-center">
                    <Bot className="h-4 w-4" />
                  </div>
                  <div className="bg-muted rounded-lg px-4 py-2">
                    <Loader2 className="h-4 w-4 animate-spin" />
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </ScrollArea>

        {/* Input */}
        <div className="border-t p-4">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              sendMessage();
            }}
            className="flex gap-2 max-w-3xl mx-auto"
          >
            <Input
              placeholder="Ask about clinical codes, documentation, or coding guidelines..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={isSending}
              className="flex-1"
            />
            <Button type="submit" disabled={!input.trim() || isSending}>
              {isSending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </form>
          <p className="text-xs text-muted-foreground text-center mt-2">
            AI suggestions are for informational purposes. Always verify codes
            with official guidelines.
          </p>
        </div>
      </div>
    </div>
  );
}
