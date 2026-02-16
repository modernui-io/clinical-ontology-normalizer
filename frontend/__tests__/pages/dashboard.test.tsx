/**
 * Tests for the Dashboard page.
 *
 * Tests:
 * - Page rendering
 * - Stats cards display
 * - Recent activity display
 * - Quick actions
 * - System status
 * - Refresh functionality
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import DashboardPage from '@/app/dashboard/page';

// Mock next/link
jest.mock('next/link', () => {
  return ({ children, href, ...props }: { children: React.ReactNode; href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  );
});

// Mock PersonaNavigator to avoid side effects
jest.mock('@/components/PersonaNavigator', () => ({
  PersonaNavigator: () => <div data-testid="persona-navigator" />,
}));

// --- Mock fetch data for dashboard API calls ---
const MOCK_NOW = 1700000000000;

const mockDocumentsPage1 = { total: 1247, documents: [] };
const mockDocuments100 = {
  documents: [
    { id: '1', status: 'completed' },
    { id: '2', status: 'processing' },
    { id: '3', status: 'completed' },
    { id: '4', status: 'failed' },
    { id: '5', status: 'queued' },
    { id: '6', status: 'processing' },
  ],
};
const mockPatients = { total: 342 };
const mockTrials = {
  trials: [
    { id: 't1', status: 'recruiting' },
    { id: 't2', status: 'completed' },
  ],
};
const mockAuditLogs = {
  logs: [
    {
      id: 'log-1',
      action: 'read',
      resource_type: 'document',
      request_path: '/api/documents/doc-123',
      timestamp: new Date(MOCK_NOW - 5 * 60000).toISOString(),
      resource_id: 'doc-123',
    },
    {
      id: 'log-2',
      action: 'create',
      resource_type: 'document',
      request_path: '/api/documents',
      timestamp: new Date(MOCK_NOW - 12 * 60000).toISOString(),
      resource_id: 'doc-456',
    },
    {
      id: 'log-3',
      action: 'create',
      resource_type: 'patient',
      request_path: '/api/patients',
      timestamp: new Date(MOCK_NOW - 60 * 60000).toISOString(),
      patient_id: 'pat-789',
    },
  ],
};

function createMockFetch() {
  return jest.fn((url: string) => {
    if (url.includes('/api/documents') && url.includes('page_size=100')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(mockDocuments100) });
    }
    if (url.includes('/api/documents') && url.includes('page_size=1')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(mockDocumentsPage1) });
    }
    if (url.includes('/api/patients')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(mockPatients) });
    }
    if (url.includes('/api/trials')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(mockTrials) });
    }
    if (url.includes('/api/audit/logs')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(mockAuditLogs) });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
  }) as jest.Mock;
}

describe('Dashboard Page', () => {
  let dateSpy: jest.SpyInstance;
  const originalFetch = global.fetch;

  beforeEach(() => {
    dateSpy = jest.spyOn(Date, 'now').mockReturnValue(MOCK_NOW);
    global.fetch = createMockFetch() as unknown as typeof fetch;
  });

  afterEach(() => {
    dateSpy.mockRestore();
    global.fetch = originalFetch;
    jest.useRealTimers();
    jest.restoreAllMocks();
  });

  describe('Rendering', () => {
    it('renders dashboard heading', () => {
      render(<DashboardPage />);
      expect(screen.getByText('Dashboard')).toBeInTheDocument();
    });

    it('renders page description', () => {
      render(<DashboardPage />);
      expect(
        screen.getByText(/overview of your clinical data processing/i)
      ).toBeInTheDocument();
    });

    it('renders refresh button', () => {
      render(<DashboardPage />);
      expect(screen.getByRole('button', { name: /refresh/i })).toBeInTheDocument();
    });
  });

  describe('Stats Cards', () => {
    it('renders total documents card', () => {
      render(<DashboardPage />);
      expect(screen.getByText('Total Documents')).toBeInTheDocument();
    });

    it('renders total patients card', () => {
      render(<DashboardPage />);
      expect(screen.getByText('Total Patients')).toBeInTheDocument();
    });

    it('renders active trials card', () => {
      render(<DashboardPage />);
      expect(screen.getByText('Active Trials')).toBeInTheDocument();
    });

    it('renders success rate card', () => {
      render(<DashboardPage />);
      expect(screen.getByText('Success Rate')).toBeInTheDocument();
    });

    it('displays document count', async () => {
      render(<DashboardPage />);
      expect(await screen.findByText('1,247')).toBeInTheDocument();
    });

    it('displays patient count', async () => {
      render(<DashboardPage />);
      expect(await screen.findByText('342')).toBeInTheDocument();
    });

    it('displays stats detail text', async () => {
      render(<DashboardPage />);
      expect(await screen.findByText('2 completed')).toBeInTheDocument();
      expect(await screen.findByText('in knowledge graph')).toBeInTheDocument();
    });
  });

  describe('Recent Activity', () => {
    it('renders recent activity section', () => {
      render(<DashboardPage />);
      expect(screen.getByText('Recent Activity')).toBeInTheDocument();
    });

    it('displays activity items', async () => {
      render(<DashboardPage />);
      expect(await screen.findByText('Read Document')).toBeInTheDocument();
      expect(await screen.findByText('Create Document')).toBeInTheDocument();
    });

    it('shows activity timestamps', async () => {
      render(<DashboardPage />);
      expect(await screen.findByText('5m ago')).toBeInTheDocument();
      expect(await screen.findByText('12m ago')).toBeInTheDocument();
    });

    it('renders view document links for activities with documents', async () => {
      render(<DashboardPage />);
      await waitFor(() => {
        const viewDocLinks = screen.getAllByText('View Document');
        expect(viewDocLinks.length).toBeGreaterThan(0);
      });
    });

    it('renders view patient links for activities with patients', async () => {
      render(<DashboardPage />);
      await waitFor(() => {
        const viewPatientLinks = screen.getAllByText('View Patient');
        expect(viewPatientLinks.length).toBeGreaterThan(0);
      });
    });

    it('renders view all activity button', () => {
      render(<DashboardPage />);
      expect(screen.getByText('View all activity')).toBeInTheDocument();
    });
  });

  describe('Quick Actions', () => {
    it('renders quick actions section', () => {
      render(<DashboardPage />);
      expect(screen.getByText('Quick Actions')).toBeInTheDocument();
    });

    it('renders upload document button', () => {
      render(<DashboardPage />);
      expect(screen.getByText('Upload Document')).toBeInTheDocument();
    });

    it('renders search clinical data button', () => {
      render(<DashboardPage />);
      expect(screen.getByText('Search Clinical Data')).toBeInTheDocument();
    });

    it('renders view patients button', () => {
      render(<DashboardPage />);
      expect(screen.getByText('View Patients')).toBeInTheDocument();
    });

    it('renders browse documents button', () => {
      render(<DashboardPage />);
      expect(screen.getByText('Browse Documents')).toBeInTheDocument();
    });

    it('renders quality metrics button', () => {
      render(<DashboardPage />);
      expect(screen.getByText('Quality Metrics')).toBeInTheDocument();
    });

    it('has correct links for quick actions', () => {
      render(<DashboardPage />);

      const uploadLink = screen.getByRole('link', { name: /upload document/i });
      expect(uploadLink).toHaveAttribute('href', '/documents/upload');

      const patientsLink = screen.getByRole('link', { name: /view patients/i });
      expect(patientsLink).toHaveAttribute('href', '/patients');

      const documentsLink = screen.getByRole('link', { name: /browse documents/i });
      expect(documentsLink).toHaveAttribute('href', '/documents');
    });
  });

  describe('System Status', () => {
    it('renders system status section', () => {
      render(<DashboardPage />);
      expect(screen.getByText('System Status')).toBeInTheDocument();
    });

    it('displays NLP Pipeline status', () => {
      render(<DashboardPage />);
      expect(screen.getByText('NLP Pipeline')).toBeInTheDocument();
      expect(screen.getAllByText('Operational')[0]).toBeInTheDocument();
    });

    it('displays OMOP Mapper status', () => {
      render(<DashboardPage />);
      expect(screen.getByText('OMOP Mapper')).toBeInTheDocument();
    });

    it('displays Database status', () => {
      render(<DashboardPage />);
      expect(screen.getByText('Database')).toBeInTheDocument();
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });

    it('displays Job Queue status', async () => {
      render(<DashboardPage />);
      expect(screen.getByText('Job Queue')).toBeInTheDocument();
      expect(await screen.findByText('3 pending')).toBeInTheDocument();
    });
  });

  describe('Refresh Functionality', () => {
    it('shows loading state when refreshing', async () => {
      render(<DashboardPage />);

      // Wait for initial data load to complete
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /refresh/i })).not.toBeDisabled();
      });

      // Replace fetch with a non-resolving mock so loading state persists
      global.fetch = jest.fn(() => new Promise(() => {})) as unknown as typeof fetch;

      const user = userEvent.setup();
      const refreshButton = screen.getByRole('button', { name: /refresh/i });
      await user.click(refreshButton);

      // Button should be disabled during refresh
      expect(refreshButton).toBeDisabled();
    });

    it('re-enables refresh button after loading', async () => {
      jest.useFakeTimers();
      const user = userEvent.setup({ delay: null });

      render(<DashboardPage />);

      // Advance to complete initial load
      await jest.advanceTimersByTimeAsync(100);

      const refreshButton = screen.getByRole('button', { name: /refresh/i });
      await user.click(refreshButton);

      // Advance to complete refresh
      await jest.advanceTimersByTimeAsync(100);

      expect(refreshButton).not.toBeDisabled();

      jest.useRealTimers();
    });
  });

  describe('Activity Icons', () => {
    it('renders appropriate icons for activity types', async () => {
      render(<DashboardPage />);

      // The component should render different icons for different activity types
      // We check for the presence of the activity items which should include icons
      await waitFor(() => {
        const activities = screen.getAllByText(/m ago|h ago/);
        expect(activities.length).toBeGreaterThan(0);
      });
    });
  });

  describe('Accessibility', () => {
    it('has accessible heading structure', () => {
      render(<DashboardPage />);

      const mainHeading = screen.getByRole('heading', { name: /dashboard/i });
      expect(mainHeading).toBeInTheDocument();
    });

    it('buttons are focusable', async () => {
      render(<DashboardPage />);

      // Wait for loading to complete so button is enabled
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /refresh/i })).not.toBeDisabled();
      });

      const refreshButton = screen.getByRole('button', { name: /refresh/i });
      refreshButton.focus();
      expect(document.activeElement).toBe(refreshButton);
    });

    it('links have accessible text', () => {
      render(<DashboardPage />);

      const links = screen.getAllByRole('link');
      links.forEach((link) => {
        expect(link.textContent?.length).toBeGreaterThan(0);
      });
    });
  });
});
