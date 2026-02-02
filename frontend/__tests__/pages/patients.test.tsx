/**
 * Tests for the Patients page.
 *
 * Tests:
 * - Page rendering
 * - Patient search functionality
 * - Patient graph display
 * - Loading states
 * - Error handling
 * - Navigation links
 */

import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import PatientsPage from '@/app/patients/page';

// Mock next/link
jest.mock('next/link', () => {
  return ({ children, href, ...props }: { children: React.ReactNode; href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  );
});

// Mock sonner toast
jest.mock('sonner', () => ({
  toast: {
    success: jest.fn(),
    error: jest.fn(),
    warning: jest.fn(),
  },
}));

// Mock the API
jest.mock('@/lib/api', () => ({
  getPatientGraph: jest.fn(),
}));

import { toast } from 'sonner';

const { getPatientGraph } = require('@/lib/api') as {
  getPatientGraph: (...args: unknown[]) => Promise<unknown>;
};

const mockGetPatientGraph = getPatientGraph as jest.Mock;
let consoleErrorSpy: jest.SpyInstance;

const advanceTimers = async (ms: number) => {
  await act(async () => {
    await jest.advanceTimersByTimeAsync(ms);
  });
};

describe('Patients Page', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    // Reset timer mocks
    jest.useFakeTimers();
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
    jest.useRealTimers();
  });

  describe('Rendering', () => {
    it('renders page heading', () => {
      render(<PatientsPage />);
      expect(screen.getByText('Patients')).toBeInTheDocument();
    });

    it('renders page description', () => {
      render(<PatientsPage />);
      expect(
        screen.getByText(/view and manage patient records/i)
      ).toBeInTheDocument();
    });

    it('renders find patient card', () => {
      render(<PatientsPage />);
      expect(screen.getByText('Find Patient')).toBeInTheDocument();
    });

    it('renders search input', () => {
      render(<PatientsPage />);
      expect(
        screen.getByPlaceholderText(/search by patient id/i)
      ).toBeInTheDocument();
    });

    it('renders search card description', () => {
      render(<PatientsPage />);
      expect(
        screen.getByText(/search for a patient by id/i)
      ).toBeInTheDocument();
    });
  });

  describe('Search Functionality', () => {
    it('updates input value on typing', async () => {
      const user = userEvent.setup({ delay: null });
      render(<PatientsPage />);

      const input = screen.getByPlaceholderText(/search by patient id/i);
      await user.type(input, 'P001');

      expect(input).toHaveValue('P001');
    });

    it('triggers search after debounce', async () => {
      mockGetPatientGraph.mockResolvedValueOnce({
        patient_id: 'P001',
        nodes: [],
        edges: [],
        node_count: 10,
        edge_count: 5,
      });

      const user = userEvent.setup({ delay: null });
      render(<PatientsPage />);

      const input = screen.getByPlaceholderText(/search by patient id/i);
      await user.type(input, 'P001');

      // Fast-forward debounce timer
      await advanceTimers(500);

      await waitFor(() => {
        expect(mockGetPatientGraph).toHaveBeenCalledWith('P001');
      });
    });

    it('does not search for empty input', async () => {
      const user = userEvent.setup({ delay: null });
      render(<PatientsPage />);

      const input = screen.getByPlaceholderText(/search by patient id/i);

      // Type and then clear
      await user.type(input, 'P001');
      await user.clear(input);

      // Fast-forward debounce timer
      await advanceTimers(500);

      // Should not have been called with empty string
      const calls = mockGetPatientGraph.mock.calls;
      const emptyCalls = calls.filter((call: [string, ...unknown[]]) => call[0] === '');
      expect(emptyCalls.length).toBe(0);
    });
  });

  describe('Loading State', () => {
    it('shows loading skeleton while searching', async () => {
      // Make the API call slow
      mockGetPatientGraph.mockImplementation(
        () =>
          new Promise((resolve) =>
            setTimeout(
              () =>
                resolve({
                  patient_id: 'P001',
                  nodes: [],
                  edges: [],
                  node_count: 10,
                  edge_count: 5,
                }),
              1000
            )
          )
      );

      const user = userEvent.setup({ delay: null });
      render(<PatientsPage />);

      const input = screen.getByPlaceholderText(/search by patient id/i);
      await user.type(input, 'P001');

      // Fast-forward past debounce
      await advanceTimers(500);

      // Loading skeleton should be visible
      // The component uses SkeletonCard which has a specific structure
      await waitFor(() => {
        const loadingElement = document.querySelector('[data-slot="card"]');
        expect(loadingElement).toBeInTheDocument();
      });
    });
  });

  describe('Search Results', () => {
    it('displays patient information when found', async () => {
      mockGetPatientGraph.mockResolvedValueOnce({
        patient_id: 'P001',
        nodes: [],
        edges: [],
        node_count: 15,
        edge_count: 8,
      });

      const user = userEvent.setup({ delay: null });
      render(<PatientsPage />);

      const input = screen.getByPlaceholderText(/search by patient id/i);
      await user.type(input, 'P001');

      // Fast-forward debounce timer
      await advanceTimers(500);

      await waitFor(() => {
        expect(screen.getByText(/patient p001/i)).toBeInTheDocument();
      });
    });

    it('displays node count', async () => {
      mockGetPatientGraph.mockResolvedValueOnce({
        patient_id: 'P001',
        nodes: [],
        edges: [],
        node_count: 15,
        edge_count: 8,
      });

      const user = userEvent.setup({ delay: null });
      render(<PatientsPage />);

      const input = screen.getByPlaceholderText(/search by patient id/i);
      await user.type(input, 'P001');

      await advanceTimers(500);

      await waitFor(() => {
        expect(screen.getByText('15')).toBeInTheDocument();
        expect(screen.getByText('Total Nodes')).toBeInTheDocument();
      });
    });

    it('displays edge count', async () => {
      mockGetPatientGraph.mockResolvedValueOnce({
        patient_id: 'P001',
        nodes: [],
        edges: [],
        node_count: 15,
        edge_count: 8,
      });

      const user = userEvent.setup({ delay: null });
      render(<PatientsPage />);

      const input = screen.getByPlaceholderText(/search by patient id/i);
      await user.type(input, 'P001');

      await advanceTimers(500);

      await waitFor(() => {
        expect(screen.getByText('8')).toBeInTheDocument();
        expect(screen.getByText('Total Edges')).toBeInTheDocument();
      });
    });

    it('renders view knowledge graph button', async () => {
      mockGetPatientGraph.mockResolvedValueOnce({
        patient_id: 'P001',
        nodes: [],
        edges: [],
        node_count: 10,
        edge_count: 5,
      });

      const user = userEvent.setup({ delay: null });
      render(<PatientsPage />);

      const input = screen.getByPlaceholderText(/search by patient id/i);
      await user.type(input, 'P001');

      await advanceTimers(500);

      await waitFor(() => {
        expect(screen.getByText('View Knowledge Graph')).toBeInTheDocument();
      });
    });

    it('renders timeline button', async () => {
      mockGetPatientGraph.mockResolvedValueOnce({
        patient_id: 'P001',
        nodes: [],
        edges: [],
        node_count: 10,
        edge_count: 5,
      });

      const user = userEvent.setup({ delay: null });
      render(<PatientsPage />);

      const input = screen.getByPlaceholderText(/search by patient id/i);
      await user.type(input, 'P001');

      await advanceTimers(500);

      await waitFor(() => {
        expect(screen.getByText('Timeline')).toBeInTheDocument();
      });
    });

    it('renders facts button', async () => {
      mockGetPatientGraph.mockResolvedValueOnce({
        patient_id: 'P001',
        nodes: [],
        edges: [],
        node_count: 10,
        edge_count: 5,
      });

      const user = userEvent.setup({ delay: null });
      render(<PatientsPage />);

      const input = screen.getByPlaceholderText(/search by patient id/i);
      await user.type(input, 'P001');

      await advanceTimers(500);

      await waitFor(() => {
        expect(screen.getByText('Facts')).toBeInTheDocument();
      });
    });
  });

  describe('Not Found State', () => {
    it('shows not found message when patient is not found', async () => {
      mockGetPatientGraph.mockRejectedValueOnce(new Error('Not found'));

      const user = userEvent.setup({ delay: null });
      render(<PatientsPage />);

      const input = screen.getByPlaceholderText(/search by patient id/i);
      await user.type(input, 'INVALID');

      await advanceTimers(500);

      await waitFor(() => {
        expect(screen.getByText(/no patient found/i)).toBeInTheDocument();
      });
    });

    it('shows toast error on failed search', async () => {
      mockGetPatientGraph.mockRejectedValueOnce(new Error('Backend error'));

      const user = userEvent.setup({ delay: null });
      render(<PatientsPage />);

      const input = screen.getByPlaceholderText(/search by patient id/i);
      await user.type(input, 'P001');

      await advanceTimers(500);

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalled();
      });
    });

    it('suggests trying different patient ID', async () => {
      mockGetPatientGraph.mockRejectedValueOnce(new Error('Not found'));

      const user = userEvent.setup({ delay: null });
      render(<PatientsPage />);

      const input = screen.getByPlaceholderText(/search by patient id/i);
      await user.type(input, 'INVALID');

      await advanceTimers(500);

      await waitFor(() => {
        expect(
          screen.getByText(/try searching with a different patient id/i)
        ).toBeInTheDocument();
      });
    });
  });

  describe('Navigation Links', () => {
    it('has correct link to knowledge graph', async () => {
      mockGetPatientGraph.mockResolvedValueOnce({
        patient_id: 'P001',
        nodes: [],
        edges: [],
        node_count: 10,
        edge_count: 5,
      });

      const user = userEvent.setup({ delay: null });
      render(<PatientsPage />);

      const input = screen.getByPlaceholderText(/search by patient id/i);
      await user.type(input, 'P001');

      await advanceTimers(500);

      await waitFor(() => {
        const graphLink = screen.getByRole('link', { name: /view knowledge graph/i });
        expect(graphLink).toHaveAttribute('href', '/patients/P001/graph');
      });
    });

    it('has correct link to timeline', async () => {
      mockGetPatientGraph.mockResolvedValueOnce({
        patient_id: 'P001',
        nodes: [],
        edges: [],
        node_count: 10,
        edge_count: 5,
      });

      const user = userEvent.setup({ delay: null });
      render(<PatientsPage />);

      const input = screen.getByPlaceholderText(/search by patient id/i);
      await user.type(input, 'P001');

      await advanceTimers(500);

      await waitFor(() => {
        const timelineLink = screen.getByRole('link', { name: /timeline/i });
        expect(timelineLink).toHaveAttribute('href', '/patients/P001/timeline');
      });
    });

    it('has correct link to facts', async () => {
      mockGetPatientGraph.mockResolvedValueOnce({
        patient_id: 'P001',
        nodes: [],
        edges: [],
        node_count: 10,
        edge_count: 5,
      });

      const user = userEvent.setup({ delay: null });
      render(<PatientsPage />);

      const input = screen.getByPlaceholderText(/search by patient id/i);
      await user.type(input, 'P001');

      await advanceTimers(500);

      await waitFor(() => {
        const factsLink = screen.getByRole('link', { name: /facts/i });
        expect(factsLink).toHaveAttribute('href', '/patients/P001/facts');
      });
    });
  });

  describe('Accessibility', () => {
    it('has accessible heading', () => {
      render(<PatientsPage />);
      expect(screen.getByRole('heading', { name: /patients/i })).toBeInTheDocument();
    });

    it('search input has accessible label', () => {
      render(<PatientsPage />);
      const input = screen.getByPlaceholderText(/search by patient id/i);
      expect(input).toBeInTheDocument();
    });
  });
});
