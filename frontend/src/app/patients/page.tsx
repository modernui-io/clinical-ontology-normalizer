"use client";

import { useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { getPatientGraph, PatientGraph } from "@/lib/api";

export default function PatientsPage() {
  const [patientId, setPatientId] = useState("");
  const [graph, setGraph] = useState<PatientGraph | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!patientId.trim()) {
      toast.error("Please enter a patient ID");
      return;
    }

    setIsLoading(true);
    try {
      const patientGraph = await getPatientGraph(patientId.trim());
      setGraph(patientGraph);
    } catch (error) {
      console.error("Failed to fetch patient graph:", error);
      toast.error("Patient not found or backend unavailable");
      setGraph(null);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">Patients</h1>
        <p className="text-muted-foreground">
          View and manage patient records and knowledge graphs
        </p>
      </div>

      <div className="mx-auto max-w-2xl space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Find Patient</CardTitle>
              <CardDescription>
                Enter a patient ID to view their knowledge graph
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSearch} className="flex gap-4">
                <Input
                  placeholder="Patient ID (e.g., P001)"
                  value={patientId}
                  onChange={(e) => setPatientId(e.target.value)}
                />
                <Button type="submit" disabled={isLoading}>
                  {isLoading ? "Searching..." : "Search"}
                </Button>
              </form>
            </CardContent>
          </Card>

          {graph && (
            <Card>
              <CardHeader>
                <CardTitle>Patient {graph.patient_id}</CardTitle>
                <CardDescription>
                  {graph.node_count} nodes, {graph.edge_count} edges
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="rounded-lg bg-blue-50 p-4 dark:bg-blue-900/20">
                    <div className="text-2xl font-bold text-blue-800 dark:text-blue-200">
                      {graph.node_count}
                    </div>
                    <div className="text-sm text-blue-600 dark:text-blue-300">
                      Total Nodes
                    </div>
                  </div>
                  <div className="rounded-lg bg-green-50 p-4 dark:bg-green-900/20">
                    <div className="text-2xl font-bold text-green-800 dark:text-green-200">
                      {graph.edge_count}
                    </div>
                    <div className="text-sm text-green-600 dark:text-green-300">
                      Total Edges
                    </div>
                  </div>
                </div>
                <Link href={`/patients/${graph.patient_id}/graph`}>
                  <Button className="w-full">View Knowledge Graph</Button>
                </Link>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
  );
}
