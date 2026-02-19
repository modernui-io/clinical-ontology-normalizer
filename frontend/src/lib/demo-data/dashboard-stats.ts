export const DEMO_DASHBOARD_STATS = {
  totalDocuments: 10,
  totalPatients: 5,
  activeTrials: 2,
  completedDocs: 8,
  processingDocs: 1,
  failedDocs: 1,
};

export const DEMO_RECENT_ACTIVITY = [
  {
    id: "act-001",
    type: "document_uploaded" as const,
    title: "Document Uploaded",
    description: "Discharge summary for John Smith uploaded",
    timestamp: "5m ago",
  },
  {
    id: "act-002",
    type: "document_processed" as const,
    title: "NLP Processing Complete",
    description: "8 clinical concepts extracted from doc-001",
    timestamp: "12m ago",
  },
  {
    id: "act-003",
    type: "patient_added" as const,
    title: "Patient Added",
    description: "Sarah Chen (MRN-10005) registered in system",
    timestamp: "25m ago",
  },
  {
    id: "act-004",
    type: "job_completed" as const,
    title: "Processing Job Complete",
    description: "Batch processing finished for 3 documents",
    timestamp: "1h ago",
  },
  {
    id: "act-005",
    type: "document_processed" as const,
    title: "NLP Processing Complete",
    description: "12 clinical concepts extracted from doc-006",
    timestamp: "2h ago",
  },
  {
    id: "act-006",
    type: "document_uploaded" as const,
    title: "Document Uploaded",
    description: "Consult note for Mary Johnson uploaded",
    timestamp: "3h ago",
  },
  {
    id: "act-007",
    type: "patient_added" as const,
    title: "Patient Added",
    description: "Robert Williams (MRN-10004) registered in system",
    timestamp: "5h ago",
  },
  {
    id: "act-008",
    type: "job_completed" as const,
    title: "Knowledge Graph Updated",
    description: "Graph rebuilt with 41 nodes and 38 edges",
    timestamp: "6h ago",
  },
];
