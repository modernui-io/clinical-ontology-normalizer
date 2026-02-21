/**
 * Tests for the Patients page.
 *
 * Tests:
 * - Page rendering
 * - Patient list display
 * - Search / filter functionality
 * - Loading states
 * - Empty state
 * - Accessibility
 */

import { render, screen, waitFor } from '@testing-library/react';
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

// Mock useAuth to avoid requiring AuthProvider
jest.mock('@/hooks/use-auth', () => ({
  useAuth: () => ({
    isDemo: false,
    isLoading: false,
    isAuthenticated: true,
    user: { id: 'user-1', email: 'test@example.com', name: 'Test', roles: ['admin'], permissions: ['*'] },
    error: null,
  }),
}));

// Mock the API
jest.mock('@/lib/api', () => ({
  getPatients: jest.fn(),
  getPatientGraph: jest.fn(),
}));

// Mock DataSourceModeBanner
jest.mock('@/components/readiness/DataSourceModeBanner', () => {
  return function MockBanner() {
    return <div data-testid="data-source-banner" />;
  };
});

const { getPatients } = require('@/lib/api') as {
  getPatients: (...args: unknown[]) => Promise<unknown>;
};
const mockGetPatients = getPatients as jest.Mock;

const MOCK_PATIENTS = [
  {
    id: 'P001',
    external_id: 'EXT-001',
    name: 'John Doe',
    gender: 'male',
    birth_date: '1980-01-15',
    created_at: '2025-01-01T00:00:00Z',
    document_count: 3,
    fact_count: 15,
    node_count: 10,
    conditions: ['Hypertension', 'Diabetes'],
    medications: ['Metformin', 'Lisinopril'],
  },
  {
    id: 'P002',
    external_id: 'EXT-002',
    name: 'Jane Smith',
    gender: 'female',
    birth_date: '1990-05-20',
    created_at: '2025-01-02T00:00:00Z',
    document_count: 1,
    fact_count: 8,
    node_count: 5,
    conditions: ['Asthma'],
    medications: ['Albuterol'],
  },
];

describe('Patients Page', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetPatients.mockResolvedValue({
      patients: MOCK_PATIENTS,
      total: 2,
      page: 1,
      page_size: 200,
    });
  });

  describe('Rendering', () => {
    it('renders page heading', async () => {
      render(<PatientsPage />);
      expect(screen.getByText('Patients')).toBeInTheDocument();
    });

    it('renders page description', async () => {
      render(<PatientsPage />);
      expect(
        screen.getByText(/browse patient records/i)
      ).toBeInTheDocument();
    });

    it('renders search/filter input', async () => {
      render(<PatientsPage />);
      await waitFor(() => {
        expect(screen.getByPlaceholderText(/filter patients/i)).toBeInTheDocument();
      });
    });
  });

  describe('Patient List Display', () => {
    it('displays patient names after loading', async () => {
      render(<PatientsPage />);

      await waitFor(() => {
        expect(screen.getByText('John Doe')).toBeInTheDocument();
        expect(screen.getByText('Jane Smith')).toBeInTheDocument();
      });
    });

    it('displays patient IDs', async () => {
      render(<PatientsPage />);

      await waitFor(() => {
        expect(screen.getByText('P001')).toBeInTheDocument();
        expect(screen.getByText('P002')).toBeInTheDocument();
      });
    });

    it('displays conditions as badges', async () => {
      render(<PatientsPage />);

      await waitFor(() => {
        expect(screen.getByText('Hypertension')).toBeInTheDocument();
        expect(screen.getByText('Diabetes')).toBeInTheDocument();
      });
    });

    it('displays total patients stat card', async () => {
      render(<PatientsPage />);

      await waitFor(() => {
        expect(screen.getByText('Total Patients')).toBeInTheDocument();
      });
    });

    it('calls getPatients API on mount', async () => {
      render(<PatientsPage />);

      await waitFor(() => {
        expect(mockGetPatients).toHaveBeenCalledWith({ page: 1, page_size: 200 });
      });
    });
  });

  describe('Search Functionality', () => {
    it('filters patients by name', async () => {
      const user = userEvent.setup();
      render(<PatientsPage />);

      // Wait for patients to load
      await waitFor(() => {
        expect(screen.getByText('John Doe')).toBeInTheDocument();
      });

      const input = screen.getByPlaceholderText(/filter patients/i);
      await user.type(input, 'Jane');

      expect(screen.getByText('Jane Smith')).toBeInTheDocument();
      expect(screen.queryByText('John Doe')).not.toBeInTheDocument();
    });

    it('filters patients by condition', async () => {
      const user = userEvent.setup();
      render(<PatientsPage />);

      await waitFor(() => {
        expect(screen.getByText('John Doe')).toBeInTheDocument();
      });

      const input = screen.getByPlaceholderText(/filter patients/i);
      await user.type(input, 'Asthma');

      expect(screen.getByText('Jane Smith')).toBeInTheDocument();
      expect(screen.queryByText('John Doe')).not.toBeInTheDocument();
    });

    it('shows no matching message when filter has no results', async () => {
      const user = userEvent.setup();
      render(<PatientsPage />);

      await waitFor(() => {
        expect(screen.getByText('John Doe')).toBeInTheDocument();
      });

      const input = screen.getByPlaceholderText(/filter patients/i);
      await user.type(input, 'ZZZZNOPATIENT');

      expect(screen.getByText(/no matching patients/i)).toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    it('shows loading spinner while fetching', async () => {
      mockGetPatients.mockImplementation(
        () => new Promise(() => {}) // never resolves
      );

      render(<PatientsPage />);

      expect(screen.getByText(/loading patients/i)).toBeInTheDocument();
    });
  });

  describe('Error / Fallback State', () => {
    it('falls back to demo data when API fails', async () => {
      mockGetPatients.mockRejectedValueOnce(new Error('Backend error'));

      render(<PatientsPage />);

      // Should fall back to demo patients and show the data source banner
      await waitFor(() => {
        expect(screen.getByTestId('data-source-banner')).toBeInTheDocument();
      });
    });
  });

  describe('Navigation Links', () => {
    it('has correct links to patient graph pages', async () => {
      render(<PatientsPage />);

      await waitFor(() => {
        const link = screen.getByRole('link', { name: /john doe/i });
        expect(link).toHaveAttribute('href', '/patients/P001/graph');
      });
    });
  });

  describe('Accessibility', () => {
    it('has accessible heading', async () => {
      render(<PatientsPage />);
      expect(screen.getByRole('heading', { name: /patients/i })).toBeInTheDocument();
    });

    it('filter input is accessible', async () => {
      render(<PatientsPage />);
      await waitFor(() => {
        const input = screen.getByPlaceholderText(/filter patients/i);
        expect(input).toBeInTheDocument();
      });
    });
  });
});
