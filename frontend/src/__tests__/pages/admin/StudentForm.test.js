import React from "react";
import { screen, fireEvent, waitFor } from "@testing-library/react";
import StudentForm from "../../../pages/admin/StudentForm";
import { renderPage } from "../../../testSupport/renderPage";
import api from "../../../services/api";
jest.mock("../../../services/api", () => ({
  __esModule: true, default: { get: jest.fn(), post: jest.fn(), patch: jest.fn() },
}));
beforeEach(() => {
  jest.resetAllMocks();
  api.get.mockResolvedValue({ data: { results: [{ id: 4, full_name: "JSS1A" }] } });
});
function openNew() { return renderPage(<StudentForm />, { path: "/new", route: "/new" }); }
test("creates a student without requiring personal email", async () => {
  api.post.mockResolvedValue({ data: { id: 23 } });
  openNew();
  fireEvent.change(await screen.findByLabelText("First name"), { target: { value: "Emmanuel" } });
  fireEvent.change(screen.getByLabelText("Last name"), { target: { value: "Osarodion" } });
  expect(screen.getByLabelText("Email (optional)")).not.toBeRequired();
  fireEvent.click(screen.getByRole("button", { name: "Add Student" }));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/api/students/", expect.objectContaining({ new_email: "", new_first_name: "Emmanuel" })));
});
async function fillStudent() {
  await screen.findByLabelText("First name");
  for (const [label, value] of [["First name", "Ada"], ["Last name", "Test"], ["Email (optional)", "ada@test.example"], ["Class", "4"]]) {
    fireEvent.change(screen.getByLabelText(label), { target: { value } });
  }
}
test("creates a student with the selected class and navigates to the saved profile", async () => {
  api.post.mockResolvedValue({ data: { id: 22 } });
  openNew(); await fillStudent();
  fireEvent.click(screen.getByRole("button", { name: "Add Student" }));
  await screen.findByText("Navigation destination");
  expect(api.post).toHaveBeenCalledWith("/api/students/", expect.objectContaining({
    new_first_name: "Ada", new_last_name: "Test", new_email: "ada@test.example", current_class: 4, dob: null,
  }));
});
test("retains input and displays backend field errors", async () => {
  api.post.mockRejectedValue({ response: { data: { new_email: ["Email already exists."] } } });
  openNew(); await fillStudent();
  fireEvent.click(screen.getByRole("button", { name: "Add Student" }));
  expect(await screen.findByText("Email already exists.")).toBeVisible();
  expect(screen.getByLabelText("Email (optional)")).toHaveValue("ada@test.example");
  expect(screen.getByRole("button", { name: "Add Student" })).toBeEnabled();
});
test("updates account and profile fields together", async () => {
  api.get.mockImplementation(async url => ({ data: url.includes("/students/") ?
    { id: 9, first_name: "Ada", last_name: "Test", email: "ada@test.example", current_class: 4, guardian_name: "Old guardian" } :
    [{ id: 4, full_name: "JSS1A" }] }));
  api.patch.mockResolvedValue({ data: { id: 9 } });
  renderPage(<StudentForm />, { path: "/students/9/edit", route: "/students/:id/edit" });
  expect(await screen.findByLabelText("Email (optional)")).toBeEnabled();
  fireEvent.change(screen.getByLabelText("Guardian name"), { target: { value: "New guardian" } });
  fireEvent.click(screen.getByRole("button", { name: "Save Changes" }));
  await waitFor(() => expect(api.patch).toHaveBeenCalled());
  const [url, payload] = api.patch.mock.calls[0];
  expect(url).toBe("/api/students/9/");
  expect(payload.guardian_name).toBe("New guardian");
  expect(payload.new_email).toBe("ada@test.example");
  expect(payload.new_first_name).toBe("Ada");
});
test("does not allow saving when reference data fails to load", async () => {
  api.get.mockRejectedValue(new Error("Offline"));
  openNew();
  expect(await screen.findByRole("alert")).toHaveTextContent("Could not load the student form");
  expect(screen.queryByRole("button", { name: "Add Student" })).not.toBeInTheDocument();
});
