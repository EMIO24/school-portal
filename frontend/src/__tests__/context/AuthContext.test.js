/**
 * __tests__/context/AuthContext.test.js
 *
 * Test suite for AuthContext — authentication state management.
 * Tests user login, logout, token refresh, and error handling.
 */

import React, { useContext } from "react";
import { renderHook, act, waitFor } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { AuthProvider, AuthContext } from "../../context/AuthContext";
import { tokenStore, authAPI } from "../../services/api";

// Mock the API module
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
    changePassword: jest.fn(),
    refresh: jest.fn(),
  },
}));

// Wrapper component for AuthProvider
const wrapper = ({ children }) => (
  <BrowserRouter>
    <AuthProvider>{children}</AuthProvider>
  </BrowserRouter>
);

describe("AuthContext", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
  });

  describe("Initial State", () => {
    it("should initialize with unauthenticated state and loading false when no session exists", async () => {
      const { result } = renderHook(() => useContext(AuthContext), {
        wrapper,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.user).toBeNull();
      expect(result.current.error).toBeNull();
    });
  });

  describe("loadUser() - Session Persistence", () => {
    it("should load persisted user when refresh token exists", async () => {
      const mockUser = {
        id: 1,
        email: "admin@school.ng",
        first_name: "John",
        last_name: "Doe",
        full_name: "John Doe",
        role: "school_admin",
        profile_photo: null,
        must_change_password: false,
        school: { id: 1, name: "Test School" },
      };

      tokenStore.getRefresh.mockReturnValue("valid_refresh_token");
      authAPI.refresh.mockResolvedValue({
        data: { access: "new_access_token", refresh: "new_refresh_token" },
      });
      authAPI.me.mockResolvedValue({ data: mockUser });

      const { result } = renderHook(() => useContext(AuthContext), {
        wrapper,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.isAuthenticated).toBe(true);
      expect(result.current.user).toEqual({
        platformAccess: null,
        id: 1,
        student_id: null,
        class_arm_id: null,
        email: "admin@school.ng",
        firstName: "John",
        lastName: "Doe",
        fullName: "John Doe",
        role: "school_admin",
        photo: null,
        mustChangePassword: false,
        school: { id: 1, name: "Test School" },
      });
    });

    it("should mark as unauthenticated when no refresh token", async () => {
      tokenStore.getRefresh.mockReturnValue(null);

      const { result } = renderHook(() => useContext(AuthContext), {
        wrapper,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.user).toBeNull();
    });
  });

  describe("login() Method", () => {
    it("should login user with valid credentials", async () => {
      const mockUser = {
        id: 1,
        email: "admin@school.ng",
        first_name: "John",
        last_name: "Doe",
        full_name: "John Doe",
        role: "school_admin",
        profile_photo: null,
        must_change_password: false,
        school: { id: 1, name: "Test School" },
      };

      authAPI.login.mockResolvedValue({
        data: {
          access: "access_token",
          refresh: "refresh_token",
          user: mockUser,
        },
      });

      const { result } = renderHook(() => useContext(AuthContext), {
        wrapper,
      });

      // Skip initial load state
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      await act(async () => {
        await result.current.login("admin@school.ng", "password123");
      });

      expect(result.current.isAuthenticated).toBe(true);
      expect(result.current.user?.email).toBe("admin@school.ng");
      expect(tokenStore.setTokens).toHaveBeenCalled();
    });

    it("should handle login failure gracefully", async () => {
      authAPI.login.mockRejectedValue(new Error("Invalid credentials"));

      const { result } = renderHook(() => useContext(AuthContext), {
        wrapper,
      });

      await waitFor(() => expect(result.current.isLoading).toBe(false));

      await act(async () => {
        await result.current.login("wrong@email.ng", "wrongpass");
      });

      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.error).toBeTruthy();
    });
  });

  describe("logout() Method", () => {
    it("should clear auth state on logout", async () => {
      const mockUser = {
        id: 1,
        email: "admin@school.ng",
        first_name: "John",
        last_name: "Doe",
        full_name: "John Doe",
        role: "school_admin",
        profile_photo: null,
        must_change_password: false,
        school: { id: 1, name: "Test School" },
      };

      authAPI.login.mockResolvedValue({
        data: {
          access: "access_token",
          refresh: "refresh_token",
          user: mockUser,
        },
      });

      const { result } = renderHook(() => useContext(AuthContext), {
        wrapper,
      });

      await waitFor(() => expect(result.current.isLoading).toBe(false));

      // Login first
      await act(async () => {
        await result.current.login("admin@school.ng", "password123");
      });

      expect(result.current.isAuthenticated).toBe(true);

      // Then logout
      await act(async () => {
        await result.current.logout();
      });

      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.user).toBeNull();
      expect(tokenStore.clearAll).toHaveBeenCalled();
    });
  });

  describe("Error Handling", () => {
    it("should clear error when clearError() is called", async () => {
      authAPI.login.mockRejectedValue(new Error("Login failed"));

      const { result } = renderHook(() => useContext(AuthContext), {
        wrapper,
      });

      await waitFor(() => expect(result.current.isLoading).toBe(false));

      await act(async () => {
        await result.current.login("bad@email.ng", "badpass");
      });

      expect(result.current.error).toBeTruthy();

      act(() => {
        result.current.clearError();
      });

      expect(result.current.error).toBeNull();
    });
  });
});

test('restored student sessions retain profile and class IDs separately from account IDs', async () => {
  jest.clearAllMocks();
  tokenStore.getRefresh.mockReturnValue('refresh');
  authAPI.refresh.mockResolvedValue({ data: { access: 'access' } });
  authAPI.me.mockResolvedValue({ data: { id: 41, student_id: 7, class_arm_id: 12, role: 'student' } });
  const { result } = renderHook(() => useContext(AuthContext), { wrapper });
  await waitFor(() => expect(result.current.isLoading).toBe(false));
  expect(result.current.user).toMatchObject({ id: 41, student_id: 7, class_arm_id: 12 });
});

test("StrictMode restores a rotating refresh token only once", async () => {
  jest.clearAllMocks();
  tokenStore.getRefresh.mockReturnValue("rotating-refresh");
  authAPI.refresh.mockResolvedValue({ data: { access: "access", refresh: "new-refresh" } });
  authAPI.me.mockResolvedValue({ data: { id: 1, email: "admin@test.example", role: "school_admin", full_name: "Admin" } });
  const strictWrapper = ({ children }) => <React.StrictMode><BrowserRouter><AuthProvider>{children}</AuthProvider></BrowserRouter></React.StrictMode>;
  const { result } = renderHook(() => useContext(AuthContext), { wrapper: strictWrapper });
  await waitFor(() => expect(result.current.isAuthenticated).toBe(true));
  expect(authAPI.refresh).toHaveBeenCalledTimes(1);
});


test('password step does not authenticate an owner before MFA verification', async () => {
  tokenStore.getRefresh.mockReturnValue(null);
  authAPI.login.mockResolvedValue({ data: { mfa_required: true, mfa_setup_required: true, challenge: 'challenge' } });
  const { result } = renderHook(() => useContext(AuthContext), { wrapper: ({children}) => <BrowserRouter><AuthProvider>{children}</AuthProvider></BrowserRouter> });
  await waitFor(() => expect(result.current.isLoading).toBe(false));
  let response;
  await act(async () => { response = await result.current.login('owner@test.example', 'password'); });
  expect(response.mfa.challenge).toBe('challenge');
  expect(result.current.isAuthenticated).toBe(false);
});
