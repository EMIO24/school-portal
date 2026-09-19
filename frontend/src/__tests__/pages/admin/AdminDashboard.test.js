import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import AdminDashboard from "../../../pages/admin/AdminDashboard";
jest.mock("../../../context/ThemeContext", () => ({useTheme: () => ({school: {name: 'Test School', entitlements: {features: ['analytics']}}})}));
jest.mock("../../../hooks/useAuth", () => ({useAuth: () => ({user: {role:'school_admin'}})}));
jest.mock("../../../components/common/WorkspaceHome", () => () => <div>School shortcuts</div>);
import api from "../../../services/api";

jest.mock("../../../services/api", () => ({
  __esModule: true, default: { get: jest.fn(), post: jest.fn() },
}));
const analytics = {
  total_students: 120, school_average: 68, overall_pass_rate: 82, fee_collection_rate: 75,
  subject_averages: [], grade_distribution: {}, class_averages: [],
  top_students: [{ name: "Ada Okafor", class: "Grade 5A", average: 95 }], attendance_school_avg: 88,
};
function mockRequests({ terms = [{ id: 1, name: "First Term", is_current: true }], snapshot = analytics, fail = "" } = {}) {
  api.get.mockImplementation(async url => {
    if (url.includes(fail) && fail) throw new Error("Offline");
    if (url === "/api/terms/") return { data: terms };
    if (url.includes("/analytics/")) return { data: snapshot, status: snapshot ? 200 : 204 };
    return { data: { count: 2, results: [] } };
  });
}
beforeEach(() => { jest.resetAllMocks(); mockRequests(); });

test("loads school counts and current-term analytics", async () => {
  render(<AdminDashboard />);
  expect(await screen.findByText("Ada Okafor")).toBeVisible();
  expect(screen.getByText("120")).toBeVisible();
  expect(screen.getByText("Enrolled Students")).toBeVisible();
  expect(api.get).toHaveBeenCalledWith("/api/analytics/overview/?term=1");
});

test("shows school counts even when no analytics snapshot exists", async () => {
  mockRequests({ snapshot: null });
  render(<AdminDashboard />);
  await waitFor(() => expect(screen.getByText(/Your term overview is ready to prepare/)).toBeVisible());
  expect(screen.getByText("Enrolled Students")).toBeVisible();
  expect(screen.getAllByText("2")).toHaveLength(4);
});

test("stops loading when there are no terms and disables refresh", async () => {
  mockRequests({ terms: [] });
  render(<AdminDashboard />);
  expect(await screen.findByText(/No academic terms found/)).toBeVisible();
  expect(screen.queryByText(/Loading analytics/)).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Refresh Analytics/ })).toBeDisabled();
});

test("selects the first term when none is marked current", async () => {
  mockRequests({ terms: [{ id: 7, name: "First Term" }] });
  render(<AdminDashboard />);
  await screen.findByText("Ada Okafor");
  expect(api.get).toHaveBeenCalledWith("/api/analytics/overview/?term=7");
});

test("reports analytics failures without hiding school counts", async () => {
  mockRequests({ fail: "/analytics/" });
  render(<AdminDashboard />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Could not load analytics");
  expect(screen.getByText("Enrolled Students")).toBeVisible();
});

test("reports a failed term request and stops loading", async () => {
  mockRequests({ fail: "/terms/" });
  render(<AdminDashboard />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Could not load terms");
  expect(screen.queryByText(/Loading analytics/)).not.toBeInTheDocument();
});

test("refreshes and reports queued processing", async () => {
  mockRequests({ snapshot: null });
  api.post.mockResolvedValue({ data: {} });
  render(<AdminDashboard />);
  await waitFor(() => expect(screen.getByText(/Your term overview is ready to prepare/)).toBeVisible());
  fireEvent.click(screen.getByRole("button", { name: /Refresh Analytics/ }));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/api/analytics/refresh/?term=1"));
  expect(await screen.findByRole("status")).toHaveTextContent("Refresh requested");
});
