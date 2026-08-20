import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { StatusBadge } from "@/components/ui/data";
import { Button } from "@/components/ui/primitives";
import tokens from "@/theme/tokens";

describe("design tokens", () => {
  it("defines the full launch language registry (15)", () => {
    expect(tokens.languages).toHaveLength(15);
    expect(tokens.languages.map((l) => l.code)).toEqual(
      expect.arrayContaining(["en", "hi", "bn", "te", "mr", "ta", "gu", "kn", "ml", "or", "pa", "as", "ur", "mai", "sd"]),
    );
  });

  it("has semantic + severity colors and WCAG-minded contrast pairs", () => {
    expect(tokens.colors.primary).toMatch(/^#[0-9A-F]{6}$/i);
    expect(tokens.colors.severity).toHaveProperty("critical");
    expect(tokens.colors.tiers).toHaveProperty("ai");
    expect(tokens.colors.text.light).not.toBe(tokens.colors.text.dark);
  });

  it("centralises breakpoints for responsive rules", () => {
    expect(tokens.breakpoints.laptop).toBeLessThan(tokens.breakpoints.desktop);
    expect(tokens.breakpoints.desktop).toBeLessThan(tokens.breakpoints.largeDesktop);
  });

  it("type scale is ordered", () => {
    expect(tokens.typeScale.display).toBeGreaterThan(tokens.typeScale.h1);
    expect(tokens.typeScale.h1).toBeGreaterThan(tokens.typeScale.body);
  });
});

describe("StatusBadge accessibility semantics", () => {
  it("renders icon + text, so status is never color-only", () => {
    render(<StatusBadge status="verified" />);
    const badge = screen.getByText(/Verified/);
    expect(badge).toBeInTheDocument();
    expect(badge.closest("span")?.querySelector("svg")).toBeInTheDocument();
  });

  it("falls back gracefully for unknown statuses", () => {
    render(<StatusBadge status="mystery_state" />);
    expect(screen.getByText(/mystery_state/)).toBeInTheDocument();
  });
});

describe("Button primitives", () => {
  it("supports semantic variants and is a real <button>", () => {
    render(<Button variant="danger">Delete</Button>);
    const button = screen.getByRole("button", { name: "Delete" });
    expect(button).toBeInTheDocument();
    expect(button.className).toContain("bg-(--color-error)");
  });
});