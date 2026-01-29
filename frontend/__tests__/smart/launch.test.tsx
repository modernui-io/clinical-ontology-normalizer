/**
 * Tests for SMART on FHIR Launch Page.
 *
 * Tests:
 * - Loading state display
 * - Error handling for missing parameters
 * - SMART configuration fetch
 * - Authorization URL construction
 * - PKCE code challenge generation
 */

import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import SMARTLaunchPage from "@/app/smart/launch/page";

// Mock fetch
const mockFetch = jest.fn();
global.fetch = mockFetch;

// Mock window.location
const mockLocation = {
  href: "",
  origin: "http://localhost:3000",
  pathname: "/smart/launch",
};
Object.defineProperty(window, "location", {
  value: mockLocation,
  writable: true,
});

// Mock TextEncoder (not available in JSDOM)
class MockTextEncoder {
  encode(str: string): Uint8Array {
    const arr = new Uint8Array(str.length);
    for (let i = 0; i < str.length; i++) {
      arr[i] = str.charCodeAt(i);
    }
    return arr;
  }
}
(global as unknown as { TextEncoder: typeof MockTextEncoder }).TextEncoder = MockTextEncoder;

// Mock crypto
const mockRandomUUID = jest.fn(() => "test-state-uuid");
const mockGetRandomValues = jest.fn((array: Uint8Array) => {
  for (let i = 0; i < array.length; i++) {
    array[i] = i % 256;
  }
  return array;
});
const mockSubtleDigest = jest.fn(() => Promise.resolve(new ArrayBuffer(32)));

Object.defineProperty(global, "crypto", {
  value: {
    randomUUID: mockRandomUUID,
    getRandomValues: mockGetRandomValues,
    subtle: {
      digest: mockSubtleDigest,
    },
  },
});

// Mock sessionStorage
const mockSessionStorage: { [key: string]: string } = {};
Object.defineProperty(window, "sessionStorage", {
  value: {
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
  },
});

// Mock useSearchParams
const mockSearchParams = new Map<string, string>();
jest.mock("next/navigation", () => ({
  useSearchParams: () => ({
    get: (key: string) => mockSearchParams.get(key) || null,
  }),
  useRouter: () => ({
    push: jest.fn(),
    replace: jest.fn(),
  }),
}));

describe("SMART Launch Page", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch.mockReset();
    mockLocation.href = "";
    mockSearchParams.clear();
    Object.keys(mockSessionStorage).forEach((key) => delete mockSessionStorage[key]);
  });

  it("should show loading state initially", () => {
    mockSearchParams.set("iss", "http://localhost:8000");
    mockFetch.mockImplementation(() => new Promise(() => {})); // Never resolves

    render(<SMARTLaunchPage />);

    expect(screen.getByText("SMART Launch")).toBeInTheDocument();
    expect(screen.getByText("Initiating SMART on FHIR launch...")).toBeInTheDocument();
  });

  it("should show error when iss parameter is missing", async () => {
    // No iss parameter set

    render(<SMARTLaunchPage />);

    await waitFor(() => {
      expect(screen.getByText("Launch Error")).toBeInTheDocument();
      expect(screen.getByText("Missing required 'iss' parameter")).toBeInTheDocument();
    });
  });

  it("should fetch SMART configuration and redirect", async () => {
    mockSearchParams.set("iss", "http://localhost:8000");

    const mockConfig = {
      authorization_endpoint: "http://localhost:8000/api/v1/smart-server/authorize",
      token_endpoint: "http://localhost:8000/api/v1/smart-server/token",
    };

    mockFetch.mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockConfig),
      })
    );

    render(<SMARTLaunchPage />);

    await waitFor(
      () => {
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining("/.well-known/smart-configuration")
        );
      },
      { timeout: 3000 }
    );

    await waitFor(
      () => {
        expect(mockLocation.href).toContain("authorize");
        expect(mockLocation.href).toContain("response_type=code");
        expect(mockLocation.href).toContain("client_id=");
        expect(mockLocation.href).toContain("code_challenge=");
      },
      { timeout: 3000 }
    );
  });

  it("should include launch token when provided (EHR launch)", async () => {
    mockSearchParams.set("iss", "http://localhost:8000");
    mockSearchParams.set("launch", "test-launch-token");

    const mockConfig = {
      authorization_endpoint: "http://localhost:8000/api/v1/smart-server/authorize",
      token_endpoint: "http://localhost:8000/api/v1/smart-server/token",
    };

    mockFetch.mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockConfig),
      })
    );

    render(<SMARTLaunchPage />);

    await waitFor(
      () => {
        expect(mockLocation.href).toContain("launch=test-launch-token");
      },
      { timeout: 3000 }
    );
  });

  it("should store code verifier and state in sessionStorage", async () => {
    mockSearchParams.set("iss", "http://localhost:8000");

    const mockConfig = {
      authorization_endpoint: "http://localhost:8000/api/v1/smart-server/authorize",
      token_endpoint: "http://localhost:8000/api/v1/smart-server/token",
    };

    mockFetch.mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockConfig),
      })
    );

    render(<SMARTLaunchPage />);

    await waitFor(
      () => {
        expect(window.sessionStorage.setItem).toHaveBeenCalledWith(
          "smart_code_verifier",
          expect.any(String)
        );
        expect(window.sessionStorage.setItem).toHaveBeenCalledWith(
          "smart_state",
          expect.any(String)
        );
      },
      { timeout: 3000 }
    );
  });

  it("should show error when SMART configuration fetch fails", async () => {
    mockSearchParams.set("iss", "http://localhost:8000");

    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
    });

    render(<SMARTLaunchPage />);

    await waitFor(() => {
      expect(screen.getByText("Launch Error")).toBeInTheDocument();
      expect(screen.getByText("Failed to fetch SMART configuration")).toBeInTheDocument();
    });
  });

  it("should use external EHR endpoint for non-localhost iss", async () => {
    mockSearchParams.set("iss", "https://ehr.example.com/fhir");

    const mockConfig = {
      authorization_endpoint: "https://ehr.example.com/authorize",
      token_endpoint: "https://ehr.example.com/token",
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockConfig),
    });

    render(<SMARTLaunchPage />);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "https://ehr.example.com/fhir/.well-known/smart-configuration"
      );
    });
  });
});
