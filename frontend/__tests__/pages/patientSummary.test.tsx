/**
 * Tests for Patient Summary Page.
 *
 * Tests:
 * - Loading state
 * - Error handling
 * - Patient overview display
 * - Focus area selection
 * - Summary generation
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PatientSummaryPage from "@/app/patients/[patientId]/summary/page";

// Mock the API module
jest.mock("@/lib/api", () => ({
  getPatient: jest.fn(),
  getPatientFacts: jest.fn(),
  generatePatientSummary: jest.fn(),
}));

// Mock useParams
const mockPatientId = "test-patient-123";
jest.mock("next/navigation", () => ({
  useParams: () => ({ patientId: mockPatientId }),
  useRouter: () => ({
    push: jest.fn(),
    replace: jest.fn(),
  }),
}));

// Mock clipboard API
Object.assign(navigator, {
  clipboard: {
    writeText: jest.fn(),
  },
});

// Import mocked functions
import { getPatient, getPatientFacts, generatePatientSummary } from "@/lib/api";

const mockGetPatient = getPatient as jest.MockedFunction<typeof getPatient>;
const mockGetPatientFacts = getPatientFacts as jest.MockedFunction<typeof getPatientFacts>;
const mockGenerateSummary = generatePatientSummary as jest.MockedFunction<typeof generatePatientSummary>;
let consoleErrorSpy: ReturnType<typeof jest.spyOn>;

const mockPatient = {
  id: "patient-uuid-123",
  external_id: "PT-001",
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-15T00:00:00Z",
};

const mockFacts = [
  {
    id: "fact-1",
    patient_id: "patient-uuid-123",
    domain: "condition",
    concept_name: "Hypertension",
    omop_concept_id: 316866,
    assertion: "present",
    temporality: "current",
    confidence: 0.92,
    start_date: "2024-01-10",
    value: null,
    unit: null,
  },
  {
    id: "fact-2",
    patient_id: "patient-uuid-123",
    domain: "drug",
    concept_name: "Lisinopril 10mg",
    omop_concept_id: 1308216,
    assertion: "present",
    temporality: "current",
    confidence: 0.88,
    start_date: "2024-01-10",
    value: "10",
    unit: "mg",
  },
  {
    id: "fact-3",
    patient_id: "patient-uuid-123",
    domain: "measurement",
    concept_name: "Blood Pressure Systolic",
    omop_concept_id: 3004249,
    assertion: "present",
    temporality: "current",
    confidence: 0.95,
    start_date: "2024-01-15",
    value: "142",
    unit: "mmHg",
  },
];

const mockSummaryResponse = {
  content: "Patient with hypertension on lisinopril therapy. Recent BP reading elevated at 142/90 mmHg.",
  confidence: "high" as const,
  fact_count: 3,
  token_usage: 250,
  cost_usd: 0.0025,
  focus_areas: ["problems", "meds"],
  sections: {},
  citations: [
    {
      fact_id: "fact-1",
      text_span: "hypertension",
      source_description: "Clinical fact from medical record",
    },
  ],
};

describe("Patient Summary Page", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    consoleErrorSpy = jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
  });

  describe("Loading State", () => {
    it("should show loading spinner while fetching data", async () => {
      mockGetPatient.mockImplementation(() => new Promise(() => {}));
      mockGetPatientFacts.mockImplementation(() => new Promise(() => {}));

      render(<PatientSummaryPage />);

      // Check for spinner (Loader2 component has animate-spin class)
      const spinner = document.querySelector(".animate-spin");
      expect(spinner).toBeTruthy();
    });
  });

  describe("Error Handling", () => {
    it("should display error message when patient data fails to load", async () => {
      mockGetPatient.mockRejectedValue(new Error("Failed to fetch"));
      mockGetPatientFacts.mockRejectedValue(new Error("Failed to fetch"));

      render(<PatientSummaryPage />);

      await waitFor(() => {
        expect(screen.getByText(/failed to load/i)).toBeInTheDocument();
      });
    });
  });

  describe("Patient Overview", () => {
    it("should display patient information when loaded", async () => {
      mockGetPatient.mockResolvedValue(mockPatient);
      mockGetPatientFacts.mockResolvedValue(mockFacts);

      render(<PatientSummaryPage />);

      // Wait for loading to complete and patient overview to appear
      await waitFor(
        () => {
          expect(screen.getByText("Patient Overview")).toBeInTheDocument();
        },
        { timeout: 3000 }
      );
    });

    it("should display total facts count", async () => {
      mockGetPatient.mockResolvedValue(mockPatient);
      mockGetPatientFacts.mockResolvedValue(mockFacts);

      render(<PatientSummaryPage />);

      await waitFor(() => {
        expect(screen.getByText("Total Facts")).toBeInTheDocument();
        expect(screen.getByText("3")).toBeInTheDocument();
      });
    });

    it("should display clinical data section", async () => {
      mockGetPatient.mockResolvedValue(mockPatient);
      mockGetPatientFacts.mockResolvedValue(mockFacts);

      render(<PatientSummaryPage />);

      // Wait for patient overview which contains clinical data
      await waitFor(
        () => {
          expect(screen.getByText("Clinical Data")).toBeInTheDocument();
        },
        { timeout: 3000 }
      );
    });
  });

  describe("Focus Areas", () => {
    it("should render focus area checkboxes", async () => {
      mockGetPatient.mockResolvedValue(mockPatient);
      mockGetPatientFacts.mockResolvedValue(mockFacts);

      render(<PatientSummaryPage />);

      await waitFor(() => {
        expect(screen.getByText("Focus Areas")).toBeInTheDocument();
        expect(screen.getByLabelText("Active Problems")).toBeInTheDocument();
        expect(screen.getByLabelText("Medications")).toBeInTheDocument();
        expect(screen.getByLabelText("Recent Labs")).toBeInTheDocument();
      });
    });

    it("should have default focus areas selected", async () => {
      mockGetPatient.mockResolvedValue(mockPatient);
      mockGetPatientFacts.mockResolvedValue(mockFacts);

      render(<PatientSummaryPage />);

      await waitFor(() => {
        const problemsCheckbox = screen.getByLabelText("Active Problems");
        const medsCheckbox = screen.getByLabelText("Medications");
        const labsCheckbox = screen.getByLabelText("Recent Labs");

        expect(problemsCheckbox).toBeChecked();
        expect(medsCheckbox).toBeChecked();
        expect(labsCheckbox).toBeChecked();
      });
    });

    it("should toggle focus area selection", async () => {
      mockGetPatient.mockResolvedValue(mockPatient);
      mockGetPatientFacts.mockResolvedValue(mockFacts);

      render(<PatientSummaryPage />);

      await waitFor(() => {
        expect(screen.getByLabelText("Allergies")).toBeInTheDocument();
      });

      const allergiesCheckbox = screen.getByLabelText("Allergies");
      expect(allergiesCheckbox).not.toBeChecked();

      await userEvent.click(allergiesCheckbox);
      expect(allergiesCheckbox).toBeChecked();
    });
  });

  describe("Summary Generation", () => {
    it("should render generate summary button", async () => {
      mockGetPatient.mockResolvedValue(mockPatient);
      mockGetPatientFacts.mockResolvedValue(mockFacts);

      render(<PatientSummaryPage />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /generate summary/i })).toBeInTheDocument();
      });
    });

    it("should disable generate button when no facts are available", async () => {
      mockGetPatient.mockResolvedValue(mockPatient);
      mockGetPatientFacts.mockResolvedValue([]);

      render(<PatientSummaryPage />);

      await waitFor(() => {
        const generateButton = screen.getByRole("button", { name: /generate summary/i });
        expect(generateButton).toBeDisabled();
      });
    });

    it("should generate summary when button is clicked", async () => {
      mockGetPatient.mockResolvedValue(mockPatient);
      mockGetPatientFacts.mockResolvedValue(mockFacts);
      mockGenerateSummary.mockResolvedValue(mockSummaryResponse);

      render(<PatientSummaryPage />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /generate summary/i })).toBeInTheDocument();
      });

      await userEvent.click(screen.getByRole("button", { name: /generate summary/i }));

      await waitFor(() => {
        expect(mockGenerateSummary).toHaveBeenCalled();
      });
    });

    it("should display summary content after generation", async () => {
      mockGetPatient.mockResolvedValue(mockPatient);
      mockGetPatientFacts.mockResolvedValue(mockFacts);
      mockGenerateSummary.mockResolvedValue(mockSummaryResponse);

      render(<PatientSummaryPage />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /generate summary/i })).toBeInTheDocument();
      });

      await userEvent.click(screen.getByRole("button", { name: /generate summary/i }));

      await waitFor(() => {
        expect(screen.getByText(/Patient with hypertension/)).toBeInTheDocument();
      });
    });

    it("should display summary metadata", async () => {
      mockGetPatient.mockResolvedValue(mockPatient);
      mockGetPatientFacts.mockResolvedValue(mockFacts);
      mockGenerateSummary.mockResolvedValue(mockSummaryResponse);

      render(<PatientSummaryPage />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /generate summary/i })).toBeInTheDocument();
      });

      await userEvent.click(screen.getByRole("button", { name: /generate summary/i }));

      await waitFor(() => {
        expect(screen.getByText("3 facts processed")).toBeInTheDocument();
        expect(screen.getByText(/250 tokens/)).toBeInTheDocument();
      });
    });

    it("should show loading state while generating", async () => {
      mockGetPatient.mockResolvedValue(mockPatient);
      mockGetPatientFacts.mockResolvedValue(mockFacts);
      mockGenerateSummary.mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve(mockSummaryResponse), 100))
      );

      render(<PatientSummaryPage />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /generate summary/i })).toBeInTheDocument();
      });

      await userEvent.click(screen.getByRole("button", { name: /generate summary/i }));

      await waitFor(() => {
        expect(screen.getByText(/generating/i)).toBeInTheDocument();
      });
    });

    it("should show error when generation fails", async () => {
      mockGetPatient.mockResolvedValue(mockPatient);
      mockGetPatientFacts.mockResolvedValue(mockFacts);
      mockGenerateSummary.mockRejectedValue(new Error("Generation failed"));

      render(<PatientSummaryPage />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /generate summary/i })).toBeInTheDocument();
      });

      await userEvent.click(screen.getByRole("button", { name: /generate summary/i }));

      await waitFor(() => {
        expect(screen.getByText(/failed to generate/i)).toBeInTheDocument();
      });
    });
  });

  describe("Navigation", () => {
    it("should have link to patient facts", async () => {
      mockGetPatient.mockResolvedValue(mockPatient);
      mockGetPatientFacts.mockResolvedValue(mockFacts);

      render(<PatientSummaryPage />);

      await waitFor(() => {
        expect(screen.getByText(/patient facts/i)).toBeInTheDocument();
      });
    });

    it("should have link to knowledge graph", async () => {
      mockGetPatient.mockResolvedValue(mockPatient);
      mockGetPatientFacts.mockResolvedValue(mockFacts);

      render(<PatientSummaryPage />);

      await waitFor(() => {
        expect(screen.getByRole("link", { name: /knowledge graph/i })).toBeInTheDocument();
      });
    });
  });

  describe("Empty State", () => {
    it("should show message when no facts available", async () => {
      mockGetPatient.mockResolvedValue(mockPatient);
      mockGetPatientFacts.mockResolvedValue([]);

      render(<PatientSummaryPage />);

      await waitFor(() => {
        expect(screen.getByText(/no clinical facts available/i)).toBeInTheDocument();
      });
    });
  });

  describe("Clinical Facts Preview", () => {
    it("should show facts preview before summary is generated", async () => {
      mockGetPatient.mockResolvedValue(mockPatient);
      mockGetPatientFacts.mockResolvedValue(mockFacts);

      render(<PatientSummaryPage />);

      await waitFor(() => {
        expect(screen.getByText("Clinical Facts Preview")).toBeInTheDocument();
      });

      // Check that fact names are displayed
      await waitFor(() => {
        expect(screen.getByText("Hypertension")).toBeInTheDocument();
      });
    });
  });
});
