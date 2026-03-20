import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { ReportClient } from "../report-client";
import type { MetaReport } from "@/app/lib/types";

const mockReport: MetaReport = {
  format: "nihil-zero",
  generated_at: "2026-03-19T12:00:00.000Z",
  data_hash: "abc123",
  sections: [
    {
      id: "meta-at-a-glance",
      title: "Meta at a Glance",
      content: "Dragapult Dusknoir leads at 9.0% meta share.",
      highlights: ["Top archetype: Dragapult Dusknoir", "A-tier meta"],
    },
    {
      id: "tier-movements",
      title: "Tier Movements",
      content: "[Mega Lucario](/archetypes/mega-lucario) dropped significantly.",
      highlights: ["Mega Lucario fell -6.1%"],
    },
  ],
};

describe("ReportClient", () => {
  afterEach(cleanup);

  it("renders the Meta Report heading", () => {
    render(<ReportClient report={mockReport} format="nihil-zero" />);
    expect(screen.getByText("Meta Report")).toBeInTheDocument();
  });

  it("renders all section titles", () => {
    render(<ReportClient report={mockReport} format="nihil-zero" />);
    expect(screen.getByText("Meta at a Glance")).toBeInTheDocument();
    expect(screen.getByText("Tier Movements")).toBeInTheDocument();
  });

  it("renders section content text", () => {
    render(<ReportClient report={mockReport} format="nihil-zero" />);
    expect(
      screen.getByText(/Dragapult Dusknoir leads at 9.0% meta share/)
    ).toBeInTheDocument();
  });

  it("renders highlight bullet points", () => {
    render(<ReportClient report={mockReport} format="nihil-zero" />);
    expect(
      screen.getByText("Top archetype: Dragapult Dusknoir")
    ).toBeInTheDocument();
    expect(screen.getByText("A-tier meta")).toBeInTheDocument();
  });

  it("renders inline markdown links as anchor or Next Link", () => {
    render(<ReportClient report={mockReport} format="nihil-zero" />);
    const link = screen.getByRole("link", { name: "Mega Lucario" });
    expect(link).toHaveAttribute("href", "/nihil-zero/archetypes/mega-lucario");
  });

  it("renders generated date in human-readable format", () => {
    render(<ReportClient report={mockReport} format="nihil-zero" />);
    // The date "2026-03-19" should appear somewhere in the component
    expect(screen.getByText(/Generated/)).toBeInTheDocument();
    expect(screen.getByText(/March 19, 2026/)).toBeInTheDocument();
  });

  it("renders empty-state message when no sections", () => {
    const emptyReport: MetaReport = {
      ...mockReport,
      sections: [],
    };
    render(<ReportClient report={emptyReport} format="nihil-zero" />);
    expect(
      screen.getByText(/This report has no sections yet/)
    ).toBeInTheDocument();
  });

  it("renders external links with target _blank", () => {
    const reportWithExternal: MetaReport = {
      ...mockReport,
      sections: [
        {
          id: "external-test",
          title: "External Links",
          content: "See [Limitless](https://limitlesstcg.com) for details.",
          highlights: [],
        },
      ],
    };
    render(<ReportClient report={reportWithExternal} format="nihil-zero" />);
    const link = screen.getByRole("link", { name: "Limitless" });
    expect(link).toHaveAttribute("href", "https://limitlesstcg.com");
    expect(link).toHaveAttribute("target", "_blank");
  });

  it("renders section content with no links as plain text", () => {
    render(<ReportClient report={mockReport} format="nihil-zero" />);
    expect(
      screen.getByText(/Dragapult Dusknoir leads at 9.0% meta share/)
    ).toBeInTheDocument();
  });

  it("renders guide link in subtitle", () => {
    render(<ReportClient report={mockReport} format="nihil-zero" />);
    const guideLink = screen.getByText("How this works →");
    expect(guideLink).toHaveAttribute("href", "/guide#report");
  });
});
