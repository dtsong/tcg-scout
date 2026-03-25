import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import StartLayout from "@/app/start/layout";

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...props
  }: {
    href: string;
    children: React.ReactNode;
    [key: string]: unknown;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

describe("StartLayout", () => {
  afterEach(cleanup);

  it("renders the Scout brand link pointing to /", () => {
    render(<StartLayout><div>child</div></StartLayout>);
    const brandLink = screen.getByRole("link", { name: /Scout/ });
    expect(brandLink).toHaveAttribute("href", "/");
  });

  it("renders the Back to app link pointing to /", () => {
    render(<StartLayout><div>child</div></StartLayout>);
    const backLink = screen.getByRole("link", { name: /Back to app/ });
    expect(backLink).toHaveAttribute("href", "/");
  });

  it("renders children in the main content area", () => {
    render(<StartLayout><div>test child content</div></StartLayout>);
    expect(screen.getByText("test child content")).toBeInTheDocument();
  });

  it("renders footer with LimitlessTCG attribution link", () => {
    render(<StartLayout><div>child</div></StartLayout>);
    const limitlessLink = screen.getByRole("link", { name: /LimitlessTCG/ });
    expect(limitlessLink).toHaveAttribute("href", "https://limitlesstcg.com");
  });

  it("renders footer with pokemon-card.com attribution link", () => {
    render(<StartLayout><div>child</div></StartLayout>);
    const pokemonCardLink = screen.getByRole("link", { name: /pokemon-card\.com/ });
    expect(pokemonCardLink).toHaveAttribute("href", "https://pokemon-card.com");
  });
});
