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

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
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

describe('Dashboard Page', () => {
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

    it('renders processing jobs card', () => {
      render(<DashboardPage />);
      expect(screen.getByText('Processing Jobs')).toBeInTheDocument();
    });

    it('renders success rate card', () => {
      render(<DashboardPage />);
      expect(screen.getByText('Success Rate')).toBeInTheDocument();
    });

    it('displays document count', () => {
      render(<DashboardPage />);
      // Check for the mock value
      expect(screen.getByText('1,247')).toBeInTheDocument();
    });

    it('displays patient count', () => {
      render(<DashboardPage />);
      expect(screen.getByText('342')).toBeInTheDocument();
    });

    it('displays weekly changes', () => {
      render(<DashboardPage />);
      expect(screen.getByText('+89')).toBeInTheDocument();
      expect(screen.getByText('+12')).toBeInTheDocument();
    });
  });

  describe('Recent Activity', () => {
    it('renders recent activity section', () => {
      render(<DashboardPage />);
      expect(screen.getByText('Recent Activity')).toBeInTheDocument();
    });

    it('displays activity items', () => {
      render(<DashboardPage />);
      expect(screen.getByText('Discharge Summary Processed')).toBeInTheDocument();
      expect(screen.getByText('Progress Note Uploaded')).toBeInTheDocument();
    });

    it('shows activity timestamps', () => {
      render(<DashboardPage />);
      expect(screen.getByText('5 minutes ago')).toBeInTheDocument();
      expect(screen.getByText('12 minutes ago')).toBeInTheDocument();
    });

    it('renders view document links for activities with documents', () => {
      render(<DashboardPage />);
      const viewDocLinks = screen.getAllByText('View Document');
      expect(viewDocLinks.length).toBeGreaterThan(0);
    });

    it('renders view patient links for activities with patients', () => {
      render(<DashboardPage />);
      const viewPatientLinks = screen.getAllByText('View Patient');
      expect(viewPatientLinks.length).toBeGreaterThan(0);
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

    it('displays Job Queue status', () => {
      render(<DashboardPage />);
      expect(screen.getByText('Job Queue')).toBeInTheDocument();
      expect(screen.getByText('3 pending')).toBeInTheDocument();
    });
  });

  describe('Refresh Functionality', () => {
    it('shows loading state when refreshing', async () => {
      const user = userEvent.setup();
      render(<DashboardPage />);

      const refreshButton = screen.getByRole('button', { name: /refresh/i });
      await user.click(refreshButton);

      // Button should be disabled during refresh
      expect(refreshButton).toBeDisabled();
    });

    it('re-enables refresh button after loading', async () => {
      jest.useFakeTimers();
      const user = userEvent.setup({ delay: null });

      render(<DashboardPage />);

      const refreshButton = screen.getByRole('button', { name: /refresh/i });
      await user.click(refreshButton);

      // Fast-forward past the simulated API call
      await jest.advanceTimersByTimeAsync(1500);

      await waitFor(() => {
        expect(refreshButton).not.toBeDisabled();
      });

      jest.useRealTimers();
    });
  });

  describe('Activity Icons', () => {
    it('renders appropriate icons for activity types', () => {
      render(<DashboardPage />);

      // The component should render different icons for different activity types
      // We check for the presence of the activity items which should include icons
      const activities = screen.getAllByText(/minutes ago|hour ago/);
      expect(activities.length).toBeGreaterThan(0);
    });
  });

  describe('Accessibility', () => {
    it('has accessible heading structure', () => {
      render(<DashboardPage />);

      const mainHeading = screen.getByRole('heading', { name: /dashboard/i });
      expect(mainHeading).toBeInTheDocument();
    });

    it('buttons are focusable', () => {
      render(<DashboardPage />);

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
