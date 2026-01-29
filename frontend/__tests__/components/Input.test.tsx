/**
 * Tests for Input component.
 *
 * Tests:
 * - Basic rendering
 * - Input types (text, email, password, number)
 * - Placeholder text
 * - Disabled state
 * - onChange handler
 * - Custom className
 * - Error styling
 */

import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { Input } from "@/components/ui/input";

describe("Input Component", () => {
  describe("Basic Rendering", () => {
    it("should render an input element", () => {
      render(<Input />);
      expect(screen.getByRole("textbox")).toBeInTheDocument();
    });

    it("should render with placeholder text", () => {
      render(<Input placeholder="Enter text" />);
      expect(screen.getByPlaceholderText("Enter text")).toBeInTheDocument();
    });

    it("should render with initial value", () => {
      render(<Input defaultValue="Initial value" />);
      expect(screen.getByDisplayValue("Initial value")).toBeInTheDocument();
    });
  });

  describe("Input Types", () => {
    it("should render text input by default", () => {
      render(<Input data-testid="input" />);
      // Input component doesn't explicitly set type, but HTML defaults to "text"
      // The getByRole("textbox") succeeds, confirming it behaves as text input
      expect(screen.getByTestId("input")).toBeInTheDocument();
      expect(screen.getByRole("textbox")).toBeInTheDocument();
    });

    it("should render email input", () => {
      render(<Input type="email" data-testid="input" />);
      expect(screen.getByTestId("input")).toHaveAttribute("type", "email");
    });

    it("should render password input", () => {
      render(<Input type="password" data-testid="input" />);
      expect(screen.getByTestId("input")).toHaveAttribute("type", "password");
    });

    it("should render number input", () => {
      render(<Input type="number" data-testid="input" />);
      expect(screen.getByTestId("input")).toHaveAttribute("type", "number");
    });
  });

  describe("States", () => {
    it("should be disabled when disabled prop is true", () => {
      render(<Input disabled />);
      expect(screen.getByRole("textbox")).toBeDisabled();
    });

    it("should be required when required prop is true", () => {
      render(<Input required />);
      expect(screen.getByRole("textbox")).toBeRequired();
    });

    it("should be readonly when readOnly prop is true", () => {
      render(<Input readOnly />);
      expect(screen.getByRole("textbox")).toHaveAttribute("readonly");
    });
  });

  describe("Event Handlers", () => {
    it("should call onChange when value changes", () => {
      const handleChange = jest.fn();
      render(<Input onChange={handleChange} />);

      fireEvent.change(screen.getByRole("textbox"), {
        target: { value: "new value" },
      });

      expect(handleChange).toHaveBeenCalled();
    });

    it("should call onFocus when input is focused", () => {
      const handleFocus = jest.fn();
      render(<Input onFocus={handleFocus} />);

      fireEvent.focus(screen.getByRole("textbox"));

      expect(handleFocus).toHaveBeenCalled();
    });

    it("should call onBlur when input loses focus", () => {
      const handleBlur = jest.fn();
      render(<Input onBlur={handleBlur} />);

      fireEvent.blur(screen.getByRole("textbox"));

      expect(handleBlur).toHaveBeenCalled();
    });

    it("should call onKeyDown when key is pressed", () => {
      const handleKeyDown = jest.fn();
      render(<Input onKeyDown={handleKeyDown} />);

      fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter" });

      expect(handleKeyDown).toHaveBeenCalled();
    });
  });

  describe("Styling", () => {
    it("should apply custom className", () => {
      render(<Input className="custom-class" data-testid="input" />);
      expect(screen.getByTestId("input")).toHaveClass("custom-class");
    });

    it("should have default styling classes", () => {
      render(<Input data-testid="input" />);
      const input = screen.getByTestId("input");
      expect(input).toHaveClass("rounded-md");
      expect(input).toHaveClass("border");
      expect(input).toHaveClass("bg-transparent");
    });
  });

  describe("Accessibility", () => {
    it("should associate label with input via id", () => {
      render(
        <>
          <label htmlFor="test-input">Test Label</label>
          <Input id="test-input" />
        </>
      );

      expect(screen.getByLabelText("Test Label")).toBeInTheDocument();
    });

    it("should support aria-label", () => {
      render(<Input aria-label="Search input" />);
      expect(screen.getByLabelText("Search input")).toBeInTheDocument();
    });

    it("should support aria-describedby", () => {
      render(
        <>
          <Input aria-describedby="help-text" data-testid="input" />
          <span id="help-text">Help text</span>
        </>
      );
      expect(screen.getByTestId("input")).toHaveAttribute(
        "aria-describedby",
        "help-text"
      );
    });
  });

  describe("Controlled vs Uncontrolled", () => {
    it("should work as controlled input", () => {
      const ControlledInput = () => {
        const [value, setValue] = React.useState("initial");
        return (
          <>
            <Input
              value={value}
              onChange={(e) => setValue(e.target.value)}
              data-testid="input"
            />
            <span data-testid="value">{value}</span>
          </>
        );
      };

      render(<ControlledInput />);

      expect(screen.getByTestId("value")).toHaveTextContent("initial");

      fireEvent.change(screen.getByTestId("input"), {
        target: { value: "updated" },
      });

      expect(screen.getByTestId("value")).toHaveTextContent("updated");
    });

    it("should work as uncontrolled input", () => {
      const ref = React.createRef<HTMLInputElement>();
      render(<Input ref={ref} defaultValue="initial" />);

      expect(ref.current?.value).toBe("initial");
    });
  });
});
