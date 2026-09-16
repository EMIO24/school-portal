import { ThemeContext } from "../../../context/ThemeContext";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import ProtectedRoute from "../../../components/common/ProtectedRoute";
import { AuthContext } from "../../../context/AuthContext";

const authenticatedTeacher = {
  isAuthenticated: true, isLoading: false,
  user: { id: 1, role: "teacher" }, login: jest.fn(), logout: jest.fn(), clearError: jest.fn(),
};

function renderRoute(authValue, allowedRoles) {
  return render(
    <MemoryRouter initialEntries={["/protected"]}>
      <ThemeContext.Provider value={{school:null}}><AuthContext.Provider value={authValue}>
        <Routes>
          <Route path="/protected" element={<ProtectedRoute allowedRoles={allowedRoles}><div>Protected Content</div></ProtectedRoute>} />
          <Route path="/login" element={<div>Login Page</div>} />
          <Route path="/teacher/dashboard" element={<div>Teacher Dashboard</div>} />
        </Routes>
      </AuthContext.Provider></ThemeContext.Provider>
    </MemoryRouter>
  );
}

describe("ProtectedRoute", () => {
  it("shows a loading status while authentication is resolving", () => {
    renderRoute({ isAuthenticated: false, isLoading: true, user: null }, []);

    expect(screen.getByRole("status", { name: "Loading school portal" })).toBeInTheDocument();
  });

  it("redirects unauthenticated visitors to login", () => {
    renderRoute({ isAuthenticated: false, isLoading: false, user: null }, []);

    expect(screen.getByText("Login Page")).toBeInTheDocument();
  });

  it("renders children for an authenticated user with an allowed role", () => {
    renderRoute(authenticatedTeacher, ["school_admin", "teacher"]);

    expect(screen.getByText("Protected Content")).toBeInTheDocument();
  });

  it("redirects an authenticated user with the wrong role to their dashboard", () => {
    renderRoute(authenticatedTeacher, ["school_admin"]);

    expect(screen.getByText("Teacher Dashboard")).toBeInTheDocument();
    expect(screen.queryByText("Protected Content")).not.toBeInTheDocument();
  });

  it("permits any authenticated role when no roles are specified", () => {
    renderRoute(authenticatedTeacher, []);

    expect(screen.getByText("Protected Content")).toBeInTheDocument();
  });
});
