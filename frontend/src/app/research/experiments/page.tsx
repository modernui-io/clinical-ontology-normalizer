"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { FlaskConical, Plus, Play, CheckCircle, Trash2, AlertTriangle, Clock } from "lucide-react";
import { toast } from "sonner";
import {
  useExperiments,
  useCreateExperiment,
  useDeleteExperiment,
  useStartExperiment,
  useCompleteExperiment,
} from "@/hooks/api/useResearch";

export default function ExperimentsPage() {
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [hypothesis, setHypothesis] = useState("");
  const [nlpMethod, setNlpMethod] = useState("ensemble");
  const [assertionAware, setAssertionAware] = useState(true);
  const [tags, setTags] = useState("");

  const { data: experiments, isLoading } = useExperiments({ status: statusFilter });
  const createMutation = useCreateExperiment({
    onSuccess: () => {
      toast.success("Experiment created");
      setDialogOpen(false);
      resetForm();
    },
    onError: () => toast.error("Failed to create experiment"),
  });
  const deleteMutation = useDeleteExperiment({
    onSuccess: () => toast.success("Experiment deleted"),
  });
  const startMutation = useStartExperiment({
    onSuccess: () => toast.success("Experiment started"),
  });
  const completeMutation = useCompleteExperiment({
    onSuccess: () => toast.success("Experiment completed"),
  });

  function resetForm() {
    setName("");
    setDescription("");
    setHypothesis("");
    setNlpMethod("ensemble");
    setAssertionAware(true);
    setTags("");
  }

  function handleCreate() {
    createMutation.mutate({
      name,
      description: description || undefined,
      hypothesis: hypothesis || undefined,
      config: {
        nlp_method: nlpMethod,
        assertion_aware: assertionAware,
        graph_rag: true,
        kg_construction: true,
      },
      tags: tags ? tags.split(",").map((t) => t.trim()) : undefined,
    });
  }

  const statusIcon = (status: string) => {
    switch (status) {
      case "running":
        return <Play className="h-4 w-4 text-blue-500" />;
      case "completed":
        return <CheckCircle className="h-4 w-4 text-emerald-500" />;
      case "failed":
        return <AlertTriangle className="h-4 w-4 text-red-500" />;
      default:
        return <Clock className="h-4 w-4 text-zinc-400" />;
    }
  };

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900">
      <header className="border-b bg-white dark:bg-zinc-950">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <FlaskConical className="h-6 w-6" />
              Experiments
            </h1>
            <div className="flex gap-2">
              <Select
                value={statusFilter ?? "all"}
                onValueChange={(v) => setStatusFilter(v === "all" ? undefined : v)}
              >
                <SelectTrigger className="w-40">
                  <SelectValue placeholder="All statuses" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All statuses</SelectItem>
                  <SelectItem value="draft">Draft</SelectItem>
                  <SelectItem value="running">Running</SelectItem>
                  <SelectItem value="completed">Completed</SelectItem>
                  <SelectItem value="failed">Failed</SelectItem>
                </SelectContent>
              </Select>
              <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
                <DialogTrigger asChild>
                  <Button>
                    <Plus className="h-4 w-4 mr-1" /> New Experiment
                  </Button>
                </DialogTrigger>
                <DialogContent className="max-w-lg">
                  <DialogHeader>
                    <DialogTitle>Create Experiment</DialogTitle>
                  </DialogHeader>
                  <div className="space-y-4">
                    <div>
                      <Label>Name</Label>
                      <Input
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        placeholder="e.g. Assertion-Aware EKG Baseline"
                      />
                    </div>
                    <div>
                      <Label>Hypothesis</Label>
                      <Textarea
                        value={hypothesis}
                        onChange={(e) => setHypothesis(e.target.value)}
                        placeholder="e.g. Assertion-aware NLP improves KG precision by 15%+"
                        rows={2}
                      />
                    </div>
                    <div>
                      <Label>Description</Label>
                      <Textarea
                        value={description}
                        onChange={(e) => setDescription(e.target.value)}
                        placeholder="Detailed description of the experiment"
                        rows={3}
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label>NLP Method</Label>
                        <Select value={nlpMethod} onValueChange={setNlpMethod}>
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="ensemble">Ensemble</SelectItem>
                            <SelectItem value="rule_based">Rule-based</SelectItem>
                            <SelectItem value="ml">ML Only</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div>
                        <Label>Assertion Aware</Label>
                        <Select
                          value={assertionAware ? "true" : "false"}
                          onValueChange={(v) => setAssertionAware(v === "true")}
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="true">Yes</SelectItem>
                            <SelectItem value="false">No</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                    <div>
                      <Label>Tags (comma-separated)</Label>
                      <Input
                        value={tags}
                        onChange={(e) => setTags(e.target.value)}
                        placeholder="neurips, baseline, assertions"
                      />
                    </div>
                    <Button onClick={handleCreate} disabled={!name || createMutation.isPending}>
                      {createMutation.isPending ? "Creating..." : "Create Experiment"}
                    </Button>
                  </div>
                </DialogContent>
              </Dialog>
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        {isLoading ? (
          <p className="text-muted-foreground">Loading...</p>
        ) : !experiments?.experiments.length ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12">
              <FlaskConical className="h-12 w-12 text-muted-foreground mb-3" />
              <p className="text-muted-foreground mb-4">No experiments found</p>
              <Button onClick={() => setDialogOpen(true)}>
                <Plus className="h-4 w-4 mr-1" /> Create Experiment
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {experiments.experiments.map((exp) => (
              <Card key={exp.id}>
                <CardContent className="flex items-center justify-between py-4">
                  <div className="flex items-center gap-3">
                    {statusIcon(exp.status)}
                    <div>
                      <p className="font-medium">{exp.name}</p>
                      <p className="text-sm text-muted-foreground">
                        {exp.hypothesis && (
                          <span className="italic">{exp.hypothesis}</span>
                        )}
                        {exp.hypothesis && " · "}
                        {exp.run_count} run{exp.run_count !== 1 ? "s" : ""} ·{" "}
                        {new Date(exp.created_at).toLocaleDateString()}
                      </p>
                      {exp.tags && (
                        <div className="flex gap-1 mt-1">
                          {exp.tags.map((tag) => (
                            <span
                              key={tag}
                              className="px-2 py-0.5 text-xs bg-zinc-100 dark:bg-zinc-800 rounded-full"
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    {exp.status === "draft" && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => startMutation.mutate(exp.id)}
                      >
                        <Play className="h-3 w-3 mr-1" /> Start
                      </Button>
                    )}
                    {exp.status === "running" && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => completeMutation.mutate(exp.id)}
                      >
                        <CheckCircle className="h-3 w-3 mr-1" /> Complete
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => deleteMutation.mutate(exp.id)}
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
