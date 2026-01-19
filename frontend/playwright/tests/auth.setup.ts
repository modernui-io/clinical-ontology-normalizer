/**
 * Authentication setup for E2E tests.
 *
 * This file runs before all tests to set up authentication state.
 * The authenticated state is saved and reused across tests.
 */

import { test as setup, expect } from '@playwright/test';

const authFile = 'playwright/.auth/user.json';

setup('authenticate', async ({ page }) => {
  // Skip authentication for now - add your auth flow here when needed
  // This is a placeholder for future authentication setup

  /*
  // Example authentication flow:
  await page.goto('/login');
  await page.getByLabel('Email').fill('test@example.com');
  await page.getByLabel('Password').fill('password');
  await page.getByRole('button', { name: 'Sign in' }).click();

  // Wait for redirect after login
  await page.waitForURL('/dashboard');

  // Ensure auth state is established
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();

  // Save authenticated state
  await page.context().storageState({ path: authFile });
  */

  // For now, just verify the app is accessible
  await page.goto('/');
  await expect(page).toHaveTitle(/Clinical Ontology/i);
});
