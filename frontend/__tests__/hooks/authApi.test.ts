/**
 * Tests for auth API functions.
 *
 * Tests:
 * - apiLogin: Login flow with token + user fetch
 * - apiRegister: Registration flow
 * - apiLogout: Logout with token revocation
 * - apiRefreshToken: Token refresh
 * - apiGetCurrentUser: Fetch current user
 * - apiUpdateProfile: Profile updates
 * - apiChangePassword: Password change
 * - apiForgotPassword: Password reset request
 */

// Mock fetch globally before imports
const mockFetch = jest.fn();
global.fetch = mockFetch;

// Mock document.cookie
let mockCookie = "";
Object.defineProperty(document, "cookie", {
  get: () => mockCookie,
  set: (value: string) => {
    mockCookie = value;
  },
});

import {
  apiLogin,
  apiRegister,
  apiLogout,
  apiRefreshToken,
  apiGetCurrentUser,
  apiUpdateProfile,
  apiChangePassword,
  apiForgotPassword,
} from "@/hooks/auth/authApi";

describe("Auth API Functions", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mockCookie = "";
  });

  describe("apiLogin", () => {
    const mockCredentials = {
      email: "test@example.com",
      password: "password123",
    };

    const mockTokens = {
      access_token: "test-access-token",
      refresh_token: "test-refresh-token",
      token_type: "bearer",
      expires_in: 3600,
    };

    const mockUser = {
      id: "user-123",
      email: "test@example.com",
      name: "Test User",
      roles: ["provider"],
      permissions: ["patients:read"],
    };

    it("should login successfully and return user and tokens", async () => {
      // Mock login response
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockTokens),
      });

      // Mock user fetch response
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockUser),
      });

      const result = await apiLogin(mockCredentials);

      expect(result.user).toEqual(mockUser);
      expect(result.tokens).toEqual(mockTokens);
      expect(mockFetch).toHaveBeenCalledTimes(2);
      expect(mockCookie).toContain("has_auth=true");
    });

    it("should throw error on invalid credentials", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({ detail: "Invalid credentials" }),
      });

      await expect(apiLogin(mockCredentials)).rejects.toThrow("Invalid credentials");
    });

    it("should throw error if user fetch fails after login", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockTokens),
      });

      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({ detail: "User not found" }),
      });

      await expect(apiLogin(mockCredentials)).rejects.toThrow(
        "Failed to fetch user info after login"
      );
    });

    it("should handle network errors gracefully", async () => {
      mockFetch.mockRejectedValueOnce(new Error("Network error"));

      await expect(apiLogin(mockCredentials)).rejects.toThrow("Network error");
    });
  });

  describe("apiRegister", () => {
    const mockRegisterData = {
      email: "newuser@example.com",
      password: "password123",
      name: "New User",
    };

    const mockTokens = {
      access_token: "new-access-token",
      refresh_token: "new-refresh-token",
      token_type: "bearer",
      expires_in: 3600,
    };

    const mockUser = {
      id: "user-456",
      email: "newuser@example.com",
      name: "New User",
      roles: ["viewer"],
      permissions: [],
    };

    it("should register successfully and return user and tokens", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockTokens),
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockUser),
      });

      const result = await apiRegister(mockRegisterData);

      expect(result.user).toEqual(mockUser);
      expect(result.tokens).toEqual(mockTokens);
      expect(mockCookie).toContain("has_auth=true");
    });

    it("should throw error on registration failure", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({ detail: "Email already exists" }),
      });

      await expect(apiRegister(mockRegisterData)).rejects.toThrow("Email already exists");
    });
  });

  describe("apiLogout", () => {
    it("should clear auth cookie on logout", async () => {
      mockCookie = "has_auth=true";

      mockFetch.mockResolvedValueOnce({ ok: true });

      await apiLogout("test-refresh-token");

      expect(mockCookie).toContain("max-age=0");
    });

    it("should not throw on logout failure", async () => {
      mockFetch.mockRejectedValueOnce(new Error("Server error"));

      // Should not throw
      await expect(apiLogout("test-refresh-token")).resolves.not.toThrow();
    });
  });

  describe("apiRefreshToken", () => {
    it("should refresh tokens successfully", async () => {
      const newTokens = {
        access_token: "new-access-token",
        refresh_token: "new-refresh-token",
        token_type: "bearer",
        expires_in: 3600,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(newTokens),
      });

      const result = await apiRefreshToken("old-refresh-token");

      expect(result).toEqual(newTokens);
      expect(mockCookie).toContain("has_auth=true");
    });

    it("should throw error on refresh failure", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({ detail: "Invalid refresh token" }),
      });

      await expect(apiRefreshToken("invalid-token")).rejects.toThrow("Token refresh failed");
    });
  });

  describe("apiGetCurrentUser", () => {
    it("should fetch current user successfully", async () => {
      const mockUser = {
        id: "user-123",
        email: "test@example.com",
        name: "Test User",
        roles: ["admin"],
        permissions: ["admin:read"],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockUser),
      });

      const result = await apiGetCurrentUser("test-access-token");

      expect(result).toEqual(mockUser);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/auth/me"),
        expect.objectContaining({
          headers: { Authorization: "Bearer test-access-token" },
        })
      );
    });

    it("should throw error when user not found", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({ detail: "User not found" }),
      });

      await expect(apiGetCurrentUser("invalid-token")).rejects.toThrow("Failed to fetch user");
    });
  });

  describe("apiUpdateProfile", () => {
    it("should update profile successfully", async () => {
      const updatedUser = {
        id: "user-123",
        email: "test@example.com",
        name: "Updated Name",
        roles: ["provider"],
        permissions: [],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(updatedUser),
      });

      const result = await apiUpdateProfile("test-token", { name: "Updated Name" });

      expect(result.name).toBe("Updated Name");
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/auth/profile"),
        expect.objectContaining({
          method: "PATCH",
          headers: expect.objectContaining({
            Authorization: "Bearer test-token",
          }),
        })
      );
    });

    it("should throw error on update failure", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({ detail: "Validation error" }),
      });

      await expect(apiUpdateProfile("test-token", { name: "" })).rejects.toThrow(
        "Validation error"
      );
    });
  });

  describe("apiChangePassword", () => {
    it("should change password successfully", async () => {
      mockFetch.mockResolvedValueOnce({ ok: true });

      await expect(
        apiChangePassword("test-token", "oldPassword", "newPassword")
      ).resolves.not.toThrow();

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/auth/change-password"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            current_password: "oldPassword",
            new_password: "newPassword",
          }),
        })
      );
    });

    it("should throw error when current password is wrong", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({ detail: "Current password is incorrect" }),
      });

      await expect(
        apiChangePassword("test-token", "wrongPassword", "newPassword")
      ).rejects.toThrow("Current password is incorrect");
    });
  });

  describe("apiForgotPassword", () => {
    it("should send password reset email successfully", async () => {
      mockFetch.mockResolvedValueOnce({ ok: true });

      await expect(apiForgotPassword("test@example.com")).resolves.not.toThrow();

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/auth/forgot-password"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ email: "test@example.com" }),
        })
      );
    });

    it("should throw error on failure", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({ detail: "Email not found" }),
      });

      await expect(apiForgotPassword("unknown@example.com")).rejects.toThrow("Email not found");
    });
  });
});
