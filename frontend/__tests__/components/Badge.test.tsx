/**
 * Tests for Badge component.
 *
 * Tests:
 * - Basic rendering
 * - Variant styles (default, secondary, destructive, outline)
 * - Custom className
 * - asChild composition
 * - Accessibility attributes
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import { Badge, badgeVariants } from "@/components/ui/badge";

describe("Badge Component", () => {
  describe("Basic Rendering", () => {
    it("should render a span element by default", () => {
      render(<Badge>Test Badge</Badge>);
      const badge = screen.getByText("Test Badge");
      expect(badge.tagName).toBe("SPAN");
    });

    it("should render children correctly", () => {
      render(<Badge>Status Active</Badge>);
      expect(screen.getByText("Status Active")).toBeInTheDocument();
    });

    it("should have data-slot attribute", () => {
      render(<Badge data-testid="badge">Test</Badge>);
      expect(screen.getByTestId("badge")).toHaveAttribute("data-slot", "badge");
    });

    it("should have default styling classes", () => {
      render(<Badge data-testid="badge">Test</Badge>);
      const badge = screen.getByTestId("badge");
      expect(badge).toHaveClass("inline-flex");
      expect(badge).toHaveClass("rounded-full");
      expect(badge).toHaveClass("text-xs");
    });
  });

  describe("Variants", () => {
    it("should render default variant", () => {
      render(<Badge data-testid="badge">Default</Badge>);
      const badge = screen.getByTestId("badge");
      expect(badge).toHaveClass("bg-primary");
      expect(badge).toHaveClass("text-primary-foreground");
    });

    it("should render secondary variant", () => {
      render(
        <Badge variant="secondary" data-testid="badge">
          Secondary
        </Badge>
      );
      const badge = screen.getByTestId("badge");
      expect(badge).toHaveClass("bg-secondary");
      expect(badge).toHaveClass("text-secondary-foreground");
    });

    it("should render destructive variant", () => {
      render(
        <Badge variant="destructive" data-testid="badge">
          Destructive
        </Badge>
      );
      const badge = screen.getByTestId("badge");
      expect(badge).toHaveClass("bg-destructive");
      expect(badge).toHaveClass("text-white");
    });

    it("should render outline variant", () => {
      render(
        <Badge variant="outline" data-testid="badge">
          Outline
        </Badge>
      );
      const badge = screen.getByTestId("badge");
      expect(badge).toHaveClass("text-foreground");
    });
  });

  describe("Custom Styling", () => {
    it("should apply custom className", () => {
      render(
        <Badge className="custom-badge" data-testid="badge">
          Custom
        </Badge>
      );
      expect(screen.getByTestId("badge")).toHaveClass("custom-badge");
    });

    it("should merge custom className with default classes", () => {
      render(
        <Badge className="my-custom-class" data-testid="badge">
          Test
        </Badge>
      );
      const badge = screen.getByTestId("badge");
      expect(badge).toHaveClass("my-custom-class");
      expect(badge).toHaveClass("inline-flex");
    });
  });

  describe("asChild Composition", () => {
    it("should render as child element when asChild is true", () => {
      render(
        <Badge asChild data-testid="badge">
          <a href="/link">Link Badge</a>
        </Badge>
      );
      const badge = screen.getByText("Link Badge");
      expect(badge.tagName).toBe("A");
      expect(badge).toHaveAttribute("href", "/link");
    });

    it("should apply badge styles to child element", () => {
      render(
        <Badge asChild variant="secondary">
          <button>Button Badge</button>
        </Badge>
      );
      const badge = screen.getByRole("button");
      expect(badge).toHaveClass("bg-secondary");
      expect(badge).toHaveClass("inline-flex");
    });
  });

  describe("With Icons", () => {
    it("should render with icon content", () => {
      render(
        <Badge data-testid="badge">
          <svg data-testid="icon" />
          With Icon
        </Badge>
      );
      expect(screen.getByTestId("icon")).toBeInTheDocument();
      expect(screen.getByText("With Icon")).toBeInTheDocument();
    });
  });

  describe("Accessibility", () => {
    it("should support aria-label", () => {
      render(<Badge aria-label="Status indicator">Active</Badge>);
      expect(screen.getByLabelText("Status indicator")).toBeInTheDocument();
    });

    it("should support role attribute", () => {
      render(<Badge role="status">Processing</Badge>);
      expect(screen.getByRole("status")).toBeInTheDocument();
    });
  });

  describe("badgeVariants Export", () => {
    it("should export badgeVariants function", () => {
      expect(typeof badgeVariants).toBe("function");
    });

    it("should return class string for default variant", () => {
      const classes = badgeVariants({ variant: "default" });
      expect(classes).toContain("bg-primary");
    });

    it("should return class string for different variants", () => {
      const secondary = badgeVariants({ variant: "secondary" });
      const destructive = badgeVariants({ variant: "destructive" });
      const outline = badgeVariants({ variant: "outline" });

      expect(secondary).toContain("bg-secondary");
      expect(destructive).toContain("bg-destructive");
      expect(outline).toContain("text-foreground");
    });
  });
});
