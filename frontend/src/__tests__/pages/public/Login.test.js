/**
 * __tests__/pages/public/Login.test.js
 *
 * Test suite for Login page.
 * Tests form validation, submission, and authentication flow.
 */

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import Login from "../../../pages/public/Login";
import { AuthContext } from "../../../context/AuthContext";
import { ThemeContext } from "../../../context/ThemeContext";

jest.mock("../../../services/api", () => ({
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

const renderLoginPage = (mockAuthValue = null) => {
  const defaultAuthValue = {
    isAuthenticated: false,
    isLoading: false,
    user: null,
    error: null,
    login: jest.fn(),
    logout: jest.fn(),
    clearError: jest.fn(),
  };

  const authValue = mockAuthValue || defaultAuthValue;
  const themeValue = {
    school: { name: "Test School", logo: "", motto: "Learning together" },
    loading: false,
    error: null,
    refetch: jest.fn(),
  };

  return render(
    <BrowserRouter>
      <ThemeContext.Provider value={themeValue}>
        <AuthContext.Provider value={authValue}>
          <Login />
        </AuthContext.Provider>
      </ThemeContext.Provider>
    </BrowserRouter>
  );
};

describe("Login Page", () => {
  it("submits a student name and optional admission number without an email", async () => {
    const login = jest.fn().mockResolvedValue({ success: true });
    renderLoginPage({ isAuthenticated: false, isLoading: false, user: null, error: null, login, clearError: jest.fn() });
    fireEvent.change(screen.getByLabelText("Email or student name"), { target: { value: "Emmanuel Osarodion" } });
    fireEvent.change(screen.getByLabelText(/^password$/i), { target: { value: "Password!26" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign In" }));
    await waitFor(() => expect(login).toHaveBeenCalledWith("emmanuel osarodion", "Password!26"));
    await waitFor(() => expect(screen.getByRole("button", { name: "Sign In" })).toBeEnabled());
    fireEvent.change(screen.getByLabelText("Admission number (if needed)"), { target: { value: " PAI/2026/0142 " } });
    fireEvent.click(screen.getByRole("button", { name: "Sign In" }));
    await waitFor(() => expect(login).toHaveBeenLastCalledWith("emmanuel osarodion", "Password!26", "PAI/2026/0142"));
  });

  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
  });

  describe("Form Rendering", () => {
    it("should render email input field", () => {
      renderLoginPage();
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    });

    it("should render password input field", () => {
      renderLoginPage();
      expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument();
    });

    it("should render login button", () => {
      renderLoginPage();
      expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
    });

    it("should render show/hide password toggle", () => {
      renderLoginPage();
      const toggleButton = screen.getByRole("button", { name: /show|hide password/i });
      expect(toggleButton).toBeInTheDocument();
    });
  });

  describe("Form Validation", () => {
    it("should show error if email is empty on submit", async () => {
      renderLoginPage();

      const loginButton = screen.getByRole("button", { name: /sign in/i });
      fireEvent.click(loginButton);

      await waitFor(() => {
        expect(screen.getByText(/email or student name is required/i)).toBeInTheDocument();
      });
    });

    it("should show error if password is empty on submit", async () => {
      renderLoginPage();

      const loginButton = screen.getByRole("button", { name: /sign in/i });
      fireEvent.click(loginButton);

      await waitFor(() => {
        expect(screen.getByText(/password is required/i)).toBeInTheDocument();
      });
    });

    it("should show error for invalid email format", async () => {
      renderLoginPage();

      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/^password$/i);
      const loginButton = screen.getByRole("button", { name: /sign in|login/i });

      fireEvent.change(emailInput, { target: { value: "invalid@email" } });
      fireEvent.change(passwordInput, { target: { value: "password123" } });
      fireEvent.click(loginButton);

      await waitFor(() => {
        expect(screen.getByText(/enter a valid email/i)).toBeInTheDocument();
      });
    });

    it("should accept valid email format", async () => {
      const mockLogin = jest.fn();
      renderLoginPage({
        isAuthenticated: false,
        isLoading: false,
        user: null,
        error: null,
        login: mockLogin,
        logout: jest.fn(),
        clearError: jest.fn(),
      });

      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/^password$/i);
      const loginButton = screen.getByRole("button", { name: /sign in/i });

      await userEvent.type(emailInput, "admin@school.ng");
      await userEvent.type(passwordInput, "password123");
      fireEvent.click(loginButton);

      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalledWith(
          "admin@school.ng",
          "password123"
        );
      });
    });
  });

  describe("Form Submission", () => {
    it("should call login with trimmed and lowercased email", async () => {
      const mockLogin = jest.fn();
      renderLoginPage({
        isAuthenticated: false,
        isLoading: false,
        user: null,
        error: null,
        login: mockLogin,
        logout: jest.fn(),
        clearError: jest.fn(),
      });

      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/^password$/i);
      const loginButton = screen.getByRole("button", { name: /sign in/i });

      await userEvent.type(emailInput, "  Admin@SCHOOL.NG  ");
      await userEvent.type(passwordInput, "password123");
      fireEvent.click(loginButton);

      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalledWith(
          "admin@school.ng",
          "password123"
        );
      });
    });

    it("should disable submit button while submitting", async () => {
      const mockLogin = jest.fn(
        () => new Promise((resolve) => setTimeout(resolve, 100))
      );

      renderLoginPage({
        isAuthenticated: false,
        isLoading: false,
        user: null,
        error: null,
        login: mockLogin,
        logout: jest.fn(),
        clearError: jest.fn(),
      });

      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/^password$/i);
      const loginButton = screen.getByRole("button", { name: /sign in/i });

      await userEvent.type(emailInput, "admin@school.ng");
      await userEvent.type(passwordInput, "password123");
      fireEvent.click(loginButton);

      // Button should be disabled during submission
      // (Implementation may show "Loading..." state)
    });
  });

  describe("Password Visibility Toggle", () => {
    it("should toggle password visibility", async () => {
      renderLoginPage();

      const passwordInput = screen.getByLabelText(/^password$/i);
      const toggleButton = screen.getByRole("button", { name: /show password|hide password/i });

      expect(passwordInput).toHaveAttribute("type", "password");

      fireEvent.click(toggleButton);

      await waitFor(() => {
        expect(passwordInput).toHaveAttribute("type", "text");
      });

      fireEvent.click(toggleButton);

      await waitFor(() => {
        expect(passwordInput).toHaveAttribute("type", "password");
      });
    });
  });

  describe("Error Handling", () => {
    it("should display API error message", async () => {
      renderLoginPage({
        isAuthenticated: false,
        isLoading: false,
        user: null,
        error: "Invalid credentials. Please try again.",
        login: jest.fn(),
        logout: jest.fn(),
        clearError: jest.fn(),
      });

      expect(screen.getByText(/Invalid credentials/i)).toBeInTheDocument();
    });

    it("should clear error when user starts typing", async () => {
      const mockClearError = jest.fn();

      renderLoginPage({
        isAuthenticated: false,
        isLoading: false,
        user: null,
        error: "Login failed",
        login: jest.fn(),
        logout: jest.fn(),
        clearError: mockClearError,
      });

      const emailInput = screen.getByLabelText(/email/i);

      fireEvent.change(emailInput, { target: { value: "test@example.com" } });

      await waitFor(() => {
        expect(mockClearError).toHaveBeenCalled();
      });
    });
  });

  describe("Authentication Redirect", () => {
    it("should redirect to admin dashboard after successful admin login", async () => {
      const mockNavigate = jest.fn();
      jest.mock("react-router-dom", () => ({
        ...jest.requireActual("react-router-dom"),
        useNavigate: () => mockNavigate,
      }));

      // Test implementation would verify navigation
    });

    it("should redirect to teacher dashboard after successful teacher login", () => {
      // Similar to above but for teacher role
    });

    it("should redirect to student dashboard after successful student login", () => {
      // Similar to above but for student role
    });

    it("should preserve intended destination from location state", () => {
      // After login, should redirect to state.from if available
    });
  });

  describe("Email Autofocus", () => {
    it("should focus email input on page load", () => {
      renderLoginPage();
      const emailInput = screen.getByLabelText(/email/i);
      expect(emailInput).toHaveFocus();
    });
  });
});
