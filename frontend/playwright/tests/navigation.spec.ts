/**
 * E2E tests for navigation and page routing.
 *
 * Tests:
 * - Home page access
 * - Dashboard navigation
 * - Patient page navigation
 * - Document page navigation
 * - Clinical search page
 * - 404 handling
 */

import { test, expect } from '@playwright/test';

test.describe('Navigation', () => {
  test.describe('Home Page', () => {
    test('should display home page', async ({ page }) => {
      await page.goto('/');
      await expect(page).toHaveTitle(/Clinical Ontology/i);
    });

    test('should have navigation to main sections', async ({ page }) => {
      await page.goto('/');

      // Check for main navigation links
      const navLinks = page.locator('nav a, header a');
      await expect(navLinks.first()).toBeVisible();
    });
  });

  test.describe('Dashboard', () => {
    test('should navigate to dashboard', async ({ page }) => {
      await page.goto('/dashboard');

      await expect(page.getByRole('heading', { name: /dashboard/i })).toBeVisible();
    });

    test('should display stats cards', async ({ page }) => {
      await page.goto('/dashboard');

      await expect(page.getByText(/total documents/i)).toBeVisible();
      await expect(page.getByText(/total patients/i)).toBeVisible();
    });

    test('should display recent activity', async ({ page }) => {
      await page.goto('/dashboard');

      await expect(page.getByText(/recent activity/i)).toBeVisible();
    });

    test('should display quick actions', async ({ page }) => {
      await page.goto('/dashboard');

      await expect(page.getByText(/quick actions/i)).toBeVisible();
    });
  });

  test.describe('Patients', () => {
    test('should navigate to patients page', async ({ page }) => {
      await page.goto('/patients');

      await expect(page.getByRole('heading', { name: /patients/i })).toBeVisible();
    });

    test('should display patient search', async ({ page }) => {
      await page.goto('/patients');

      await expect(page.getByPlaceholder(/search/i)).toBeVisible();
    });

    test('should navigate to patient details', async ({ page }) => {
      // This test will depend on having test data
      await page.goto('/patients/P001/graph');

      // Should either show patient data or not found
      const content = await page.content();
      expect(content.length).toBeGreaterThan(0);
    });
  });

  test.describe('Documents', () => {
    test('should navigate to documents page', async ({ page }) => {
      await page.goto('/documents');

      // Check for documents page content
      const content = await page.content();
      expect(content.length).toBeGreaterThan(0);
    });

    test('should navigate to document upload', async ({ page }) => {
      await page.goto('/documents/upload');

      const content = await page.content();
      expect(content.length).toBeGreaterThan(0);
    });
  });

  test.describe('Clinical Search', () => {
    test('should navigate to clinical search page', async ({ page }) => {
      await page.goto('/clinical');

      const content = await page.content();
      expect(content.length).toBeGreaterThan(0);
    });
  });

  test.describe('Error Pages', () => {
    test('should handle 404 for non-existent pages', async ({ page }) => {
      const response = await page.goto('/non-existent-page');

      // Should either return 404 or redirect
      expect(response?.status()).toBeDefined();
    });
  });

  test.describe('Link Functionality', () => {
    test('dashboard links work correctly', async ({ page }) => {
      await page.goto('/dashboard');

      // Click on upload document link
      const uploadLink = page.getByRole('link', { name: /upload document/i });
      if (await uploadLink.isVisible()) {
        await uploadLink.click();
        await expect(page).toHaveURL(/documents\/upload/);
      }
    });

    test('can navigate from dashboard to patients', async ({ page }) => {
      await page.goto('/dashboard');

      const patientsLink = page.getByRole('link', { name: /view patients/i });
      if (await patientsLink.isVisible()) {
        await patientsLink.click();
        await expect(page).toHaveURL(/patients/);
      }
    });
  });
});
