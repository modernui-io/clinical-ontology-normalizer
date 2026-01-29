/**
 * Tests for SMART on FHIR Callback Page.
 *
 * Tests:
 * - Loading state display
 * - Error parameter handling
 * - State verification (CSRF protection)
 * - Code verifier retrieval
 * - Token exchange
 * - Token storage
 * - Redirect on success
 */

import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import SMARTCallbackPage from "@/app/smart/callback/page";

// Mock fetch
const mockFetch = jest.fn();
global.fetch = mockFetch;

// Mock window.location
const mockLocation = {
  href: "",
  origin: "http://localhost:3000",
  pathname: "/smart/callback",
};
Object.defineProperty(window, "location", {
  value: mockLocation,
  writable: true,
});

// Mock sessionStorage
const mockSessionStorage: { [key: string]: string } = {};
const mockSessionStorageImpl = {
  getItem: jest.fn((key: string) => mockSessionStorage[key] || null),
  setItem: jest.fn((key: string, value: string) => {
    mockSessionStorage[key] = value;
  }),
  removeItem: jest.fn((key: string) => {
    delete mockSessionStorage[key];
  }),
  clear: jest.fn(() => {
    Object.keys(mockSessionStorage).forEach((key) => delete mockSessionStorage[key]);
  }),
};
Object.defineProperty(window, "sessionStorage", {
  value: mockSessionStorageImpl,
});

// Mock useSearchParams and useRouter
const mockSearchParams = new Map<string, string>();
const mockPush = jest.fn();
jest.mock("next/navigation", () => ({
  useSearchParams: () => ({
    get: (key: string) => mockSearchParams.get(key) || null,
  }),
  useRouter: () => ({
    push: mockPush,
    replace: jest.fn(),
  }),
}));

describe("SMART Callback Page", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch.mockReset();
    mockLocation.href = "";
    mockSearchParams.clear();
    Object.keys(mockSessionStorage).forEach((key) => delete mockSessionStorage[key]);
    mockPush.mockClear();
  });

  it("should show loading state initially", () => {
    mockSearchParams.set("code", "auth-code-123");
    mockSearchParams.set("state", "test-state");
    mockSessionStorage["smart_state"] = "test-state";
    mockSessionStorage["smart_code_verifier"] = "test-verifier";

    mockFetch.mockImplementation(() => new Promise(() => {})); // Never resolves

    render(<SMARTCallbackPage />);

    expect(screen.getByText("Processing Authorization")).toBeInTheDocument();
    expect(screen.getByText("Exchanging authorization code...")).toBeInTheDocument();
  });

  it("should show error when error parameter is present", async () => {
    mockSearchParams.set("error", "access_denied");
    mockSearchParams.set("error_description", "User denied access");

    render(<SMARTCallbackPage />);

    await waitFor(() => {
      expect(screen.getByText("Authorization Failed")).toBeInTheDocument();
      expect(screen.getByText("User denied access")).toBeInTheDocument();
    });
  });

  it("should show error when code is missing", async () => {
    // No code parameter
    mockSearchParams.set("state", "test-state");

    render(<SMARTCallbackPage />);

    await waitFor(() => {
      expect(screen.getByText("Authorization Failed")).toBeInTheDocument();
      expect(screen.getByText("Missing authorization code")).toBeInTheDocument();
    });
  });

  it("should show error on state mismatch (CSRF protection)", async () => {
    mockSearchParams.set("code", "auth-code-123");
    mockSearchParams.set("state", "callback-state");
    mockSessionStorage["smart_state"] = "different-state";
    mockSessionStorage["smart_code_verifier"] = "test-verifier";

    render(<SMARTCallbackPage />);

    await waitFor(() => {
      expect(screen.getByText("Authorization Failed")).toBeInTheDocument();
      expect(screen.getByText("State mismatch - possible CSRF attack")).toBeInTheDocument();
    });
  });

  it("should show error when code verifier is missing", async () => {
    mockSearchParams.set("code", "auth-code-123");
    mockSearchParams.set("state", "test-state");
    mockSessionStorage["smart_state"] = "test-state";
    // No code verifier

    render(<SMARTCallbackPage />);

    await waitFor(() => {
      expect(screen.getByText("Authorization Failed")).toBeInTheDocument();
      expect(screen.getByText("Missing code verifier - session expired")).toBeInTheDocument();
    });
  });

  it("should exchange code for tokens successfully", async () => {
    mockSearchParams.set("code", "auth-code-123");
    mockSearchParams.set("state", "test-state");
    mockSessionStorage["smart_state"] = "test-state";
    mockSessionStorage["smart_code_verifier"] = "test-verifier";

    const mockTokenResponse = {
      access_token: "test-access-token",
      token_type: "Bearer",
      expires_in: 3600,
      refresh_token: "test-refresh-token",
      scope: "openid patient/*.read",
      patient: "patient-123",
      encounter: "encounter-456",
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockTokenResponse),
    });

    render(<SMARTCallbackPage />);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/smart-server/token"),
        expect.objectContaining({
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
        })
      );
    });

    await waitFor(() => {
      expect(screen.getByText("Authorization Successful")).toBeInTheDocument();
    });
  });

  it("should store tokens in sessionStorage", async () => {
    mockSearchParams.set("code", "auth-code-123");
    mockSearchParams.set("state", "test-state");
    mockSessionStorage["smart_state"] = "test-state";
    mockSessionStorage["smart_code_verifier"] = "test-verifier";

    const mockTokenResponse = {
      access_token: "test-access-token",
      token_type: "Bearer",
      expires_in: 3600,
      refresh_token: "test-refresh-token",
      scope: "openid patient/*.read",
      patient: "patient-123",
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockTokenResponse),
    });

    render(<SMARTCallbackPage />);

    await waitFor(() => {
      expect(mockSessionStorageImpl.setItem).toHaveBeenCalledWith(
        "smart_access_token",
        "test-access-token"
      );
      expect(mockSessionStorageImpl.setItem).toHaveBeenCalledWith(
        "smart_refresh_token",
        "test-refresh-token"
      );
      expect(mockSessionStorageImpl.setItem).toHaveBeenCalledWith(
        "smart_patient_id",
        "patient-123"
      );
    });
  });

  it("should clean up code verifier and state after success", async () => {
    mockSearchParams.set("code", "auth-code-123");
    mockSearchParams.set("state", "test-state");
    mockSessionStorage["smart_state"] = "test-state";
    mockSessionStorage["smart_code_verifier"] = "test-verifier";

    const mockTokenResponse = {
      access_token: "test-access-token",
      token_type: "Bearer",
      expires_in: 3600,
      scope: "openid",
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockTokenResponse),
    });

    render(<SMARTCallbackPage />);

    await waitFor(() => {
      expect(mockSessionStorageImpl.removeItem).toHaveBeenCalledWith("smart_code_verifier");
      expect(mockSessionStorageImpl.removeItem).toHaveBeenCalledWith("smart_state");
    });
  });

  it("should display token information on success", async () => {
    mockSearchParams.set("code", "auth-code-123");
    mockSearchParams.set("state", "test-state");
    mockSessionStorage["smart_state"] = "test-state";
    mockSessionStorage["smart_code_verifier"] = "test-verifier";

    const mockTokenResponse = {
      access_token: "test-access-token",
      token_type: "Bearer",
      expires_in: 3600,
      scope: "openid patient/*.read",
      patient: "patient-123",
      encounter: "encounter-456",
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockTokenResponse),
    });

    render(<SMARTCallbackPage />);

    await waitFor(() => {
      expect(screen.getByText("Authorization Successful")).toBeInTheDocument();
      expect(screen.getByText("openid patient/*.read")).toBeInTheDocument();
      expect(screen.getByText("patient-123")).toBeInTheDocument();
      expect(screen.getByText("encounter-456")).toBeInTheDocument();
    });
  });

  it("should show error on token exchange failure", async () => {
    mockSearchParams.set("code", "auth-code-123");
    mockSearchParams.set("state", "test-state");
    mockSessionStorage["smart_state"] = "test-state";
    mockSessionStorage["smart_code_verifier"] = "test-verifier";

    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: () =>
        Promise.resolve({
          error: "invalid_grant",
          error_description: "Authorization code expired",
        }),
    });

    render(<SMARTCallbackPage />);

    await waitFor(() => {
      expect(screen.getByText("Authorization Failed")).toBeInTheDocument();
      expect(screen.getByText("Authorization code expired")).toBeInTheDocument();
    });
  });

  it("should setup redirect to patient view when patient context is present", async () => {
    // This test verifies that the success screen is displayed when patient context exists
    // and that the UI indicates a redirect is pending (actual redirect uses setTimeout)
    mockSearchParams.set("code", "auth-code-123");
    mockSearchParams.set("state", "test-state");
    mockSessionStorage["smart_state"] = "test-state";
    mockSessionStorage["smart_code_verifier"] = "test-verifier";

    const mockTokenResponse = {
      access_token: "test-access-token",
      token_type: "Bearer",
      expires_in: 3600,
      scope: "openid",
      patient: "patient-123",
    };

    mockFetch.mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockTokenResponse),
      })
    );

    render(<SMARTCallbackPage />);

    // Verify success screen is shown with patient context
    await waitFor(() => {
      expect(screen.getByText("Authorization Successful")).toBeInTheDocument();
      expect(screen.getByText("patient-123")).toBeInTheDocument();
      expect(screen.getByText("Redirecting to patient view...")).toBeInTheDocument();
    });
  });
});
