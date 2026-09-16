import { ThemeContext } from "../../../context/ThemeContext";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import ParentDashboard from "../../../pages/parent/ParentDashboard";
import api from "../../../services/api";

jest.mock("../../../services/api", () => ({ __esModule: true, default: { get: jest.fn() } }));

const dashboard = {
  result_summary: { average: 81, position: 2 },
  attendance_summary: { percentage: 92, present: 46, total: 50, last_7_days: [] },
  fee_status: { outstanding: 5000, paid: 25000 },
  timetable_today: [{ start_time: "08:00", subject: "Mathematics", teacher: "Mr Bello" }],
  recent_notifications: [{ channel: "sms", message_body: "PTA meeting", sent_at: "2026-01-01" }],
};

describe("ParentDashboard", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    api.get.mockResolvedValueOnce({ data: [{ student_id: 101, name: "Mary Johnson", class: "Grade 5" }] })
      .mockResolvedValueOnce({ data: dashboard });
  });

  it("loads a linked child and displays that child's dashboard summary", async () => {
    render(<MemoryRouter><ThemeContext.Provider value={{school:null}}><ParentDashboard /></ThemeContext.Provider></MemoryRouter>);

    expect(await screen.findByRole("button", { name: /Mary Grade 5/i })).toBeInTheDocument();
    expect(screen.getByText("81%")).toBeInTheDocument();
    expect(screen.getByText("92%")).toBeInTheDocument();
    expect(screen.getByText("Mathematics")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Pay Now" })).toBeInTheDocument();
  });

  it("opens the notification drawer with recent messages", async () => {
    render(<MemoryRouter><ThemeContext.Provider value={{school:null}}><ParentDashboard /></ThemeContext.Provider></MemoryRouter>);
    await screen.findByText("81%");

    await userEvent.click(screen.getByRole("button", { name: /🔔/ }));
    expect(screen.getByText("Recent Messages")).toBeInTheDocument();
    expect(screen.getByText("PTA meeting")).toBeInTheDocument();
  });
});
