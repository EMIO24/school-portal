/**
 * __tests__/hooks/useAuth.test.js
 *
 * Test suite for useAuth hook.
 * Tests that the hook properly consumes AuthContext and throws when used outside provider.
 */

import React from "react";
import { renderHook } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import { AuthProvider } from "../../context/AuthContext";

jest.mock("../../services/api", () => ({
  tokenStore: {
    getAccess: jest.fn(() => null),
    setAccess: jest.fn(),
    clearAccess: jest.fn(),
    getRefresh: jest.fn(() => null),
    setRefresh: jest.fn(),
    clearRefresh: jest.fn(),
    setTokens: jest.fn(),
    clearAll: jest.fn(),
  },
  authAPI: {
    login: jest.fn(),
    logout: jest.fn(),
    me: jest.fn(),
  },
}));

const wrapper = ({ children }) => (
  <BrowserRouter>
    <AuthProvider>{children}</AuthProvider>
  </BrowserRouter>
);

describe("useAuth Hook", () => {
  it("should return auth context when used inside AuthProvider", () => {
    const { result } = renderHook(() => useAuth(), { wrapper });

    expect(result.current).toBeDefined();
    expect(result.current.isAuthenticated).toBeDefined();
    expect(result.current.isLoading).toBeDefined();
    expect(result.current.user).toBeDefined();
    expect(result.current.login).toBeDefined();
    expect(result.current.logout).toBeDefined();
  });

  it("should throw error when used outside AuthProvider", () => {
    // Suppress console.error for this test
    const consoleSpy = jest.spyOn(console, "error").mockImplementation();

    expect(() => {
      renderHook(() => useAuth());
    }).toThrow("useAuth must be used inside <AuthProvider>.");

    consoleSpy.mockRestore();
  });

  it("should provide login method", () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    expect(typeof result.current.login).toBe("function");
  });

  it("should provide logout method", () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    expect(typeof result.current.logout).toBe("function");
  });

  it("should provide clearError method", () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    expect(typeof result.current.clearError).toBe("function");
  });
});
