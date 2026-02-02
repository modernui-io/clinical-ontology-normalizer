/**
 * Tests for Dialog component.
 *
 * Tests:
 * - Dialog opening and closing
 * - Dialog title and description
 * - Dialog content rendering
 * - Close button functionality
 * - Overlay click behavior
 * - Accessibility attributes
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogClose,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

describe("Dialog Component", () => {
  describe("Basic Rendering", () => {
    it("should not render content when closed", () => {
      render(
        <Dialog>
          <DialogTrigger>Open Dialog</DialogTrigger>
          <DialogContent>
            <DialogTitle>Dialog Title</DialogTitle>
            <DialogDescription>Dialog content</DialogDescription>
          </DialogContent>
        </Dialog>
      );

      expect(screen.queryByText("Dialog Title")).not.toBeInTheDocument();
    });

    it("should render trigger button", () => {
      render(
        <Dialog>
          <DialogTrigger>Open Dialog</DialogTrigger>
          <DialogContent>
            <DialogTitle>Dialog Title</DialogTitle>
            <DialogDescription>Dialog description</DialogDescription>
          </DialogContent>
        </Dialog>
      );

      expect(screen.getByText("Open Dialog")).toBeInTheDocument();
    });
  });

  describe("Opening Dialog", () => {
    it("should open dialog when trigger is clicked", async () => {
      render(
        <Dialog>
          <DialogTrigger>Open Dialog</DialogTrigger>
          <DialogContent>
            <DialogTitle>Dialog Title</DialogTitle>
            <DialogDescription>This is the dialog content.</DialogDescription>
          </DialogContent>
        </Dialog>
      );

      await userEvent.click(screen.getByText("Open Dialog"));

      await waitFor(() => {
        expect(screen.getByText("Dialog Title")).toBeInTheDocument();
        expect(screen.getByText("This is the dialog content.")).toBeInTheDocument();
      });
    });

    it("should open dialog when controlled open prop is true", () => {
      render(
        <Dialog open={true}>
          <DialogContent>
            <DialogTitle>Controlled Dialog</DialogTitle>
            <DialogDescription>Controlled dialog content</DialogDescription>
          </DialogContent>
        </Dialog>
      );

      expect(screen.getByText("Controlled Dialog")).toBeInTheDocument();
    });
  });

  describe("Closing Dialog", () => {
    it("should close dialog when close button is clicked", async () => {
      render(
        <Dialog defaultOpen>
          <DialogContent>
            <DialogTitle>Dialog Title</DialogTitle>
            <DialogDescription>Dialog description</DialogDescription>
            <DialogClose data-testid="close-btn">Close</DialogClose>
          </DialogContent>
        </Dialog>
      );

      expect(screen.getByText("Dialog Title")).toBeInTheDocument();

      await userEvent.click(screen.getByTestId("close-btn"));

      await waitFor(() => {
        expect(screen.queryByText("Dialog Title")).not.toBeInTheDocument();
      });
    });

    it("should call onOpenChange when dialog state changes", async () => {
      const handleOpenChange = jest.fn();

      render(
        <Dialog onOpenChange={handleOpenChange}>
          <DialogTrigger>Open Dialog</DialogTrigger>
          <DialogContent>
            <DialogTitle>Dialog Title</DialogTitle>
            <DialogDescription>Dialog description</DialogDescription>
          </DialogContent>
        </Dialog>
      );

      await userEvent.click(screen.getByText("Open Dialog"));

      expect(handleOpenChange).toHaveBeenCalledWith(true);
    });
  });

  describe("Dialog Structure", () => {
    it("should render header with title and description", async () => {
      render(
        <Dialog defaultOpen>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Header Title</DialogTitle>
              <DialogDescription>Header Description</DialogDescription>
            </DialogHeader>
          </DialogContent>
        </Dialog>
      );

      expect(screen.getByText("Header Title")).toBeInTheDocument();
      expect(screen.getByText("Header Description")).toBeInTheDocument();
    });

    it("should render footer with action buttons", async () => {
      render(
        <Dialog defaultOpen>
          <DialogContent>
            <DialogTitle>Dialog</DialogTitle>
            <DialogDescription>Dialog description</DialogDescription>
            <DialogFooter>
              <Button variant="outline">Cancel</Button>
              <Button>Save</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      );

      expect(screen.getByText("Cancel")).toBeInTheDocument();
      expect(screen.getByText("Save")).toBeInTheDocument();
    });

    it("should render custom content", async () => {
      render(
        <Dialog defaultOpen>
          <DialogContent>
            <DialogTitle>Form Dialog</DialogTitle>
            <DialogDescription>Dialog description</DialogDescription>
            <form data-testid="dialog-form">
              <input placeholder="Name" />
              <input placeholder="Email" />
            </form>
          </DialogContent>
        </Dialog>
      );

      expect(screen.getByTestId("dialog-form")).toBeInTheDocument();
      expect(screen.getByPlaceholderText("Name")).toBeInTheDocument();
      expect(screen.getByPlaceholderText("Email")).toBeInTheDocument();
    });
  });

  describe("Accessibility", () => {
    it("should have dialog role", async () => {
      render(
        <Dialog defaultOpen>
          <DialogContent>
            <DialogTitle>Accessible Dialog</DialogTitle>
            <DialogDescription>Dialog description</DialogDescription>
          </DialogContent>
        </Dialog>
      );

      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    it("should have aria-labelledby for title", async () => {
      render(
        <Dialog defaultOpen>
          <DialogContent>
            <DialogTitle>Dialog Title</DialogTitle>
            <DialogDescription>Dialog description</DialogDescription>
          </DialogContent>
        </Dialog>
      );

      const dialog = screen.getByRole("dialog");
      expect(dialog).toHaveAttribute("aria-labelledby");
    });

    it("should have aria-describedby for description", async () => {
      render(
        <Dialog defaultOpen>
          <DialogContent>
            <DialogTitle>Dialog Title</DialogTitle>
            <DialogDescription>Dialog description text</DialogDescription>
          </DialogContent>
        </Dialog>
      );

      const dialog = screen.getByRole("dialog");
      expect(dialog).toHaveAttribute("aria-describedby");
    });

    it("should trap focus within dialog", async () => {
      render(
        <Dialog defaultOpen>
          <DialogContent>
            <DialogTitle>Focus Trap Dialog</DialogTitle>
            <DialogDescription>Dialog description</DialogDescription>
            <Button>First Button</Button>
            <Button>Second Button</Button>
          </DialogContent>
        </Dialog>
      );

      // The close button or first focusable element should be focused
      await waitFor(() => {
        const dialog = screen.getByRole("dialog");
        expect(dialog.contains(document.activeElement)).toBe(true);
      });
    });
  });

  describe("Controlled Dialog", () => {
    it("should work with controlled open state", async () => {
      const ControlledDialog = () => {
        const [open, setOpen] = React.useState(false);
        return (
          <>
            <Button onClick={() => setOpen(true)}>Open</Button>
            <Dialog open={open} onOpenChange={setOpen}>
              <DialogContent>
                <DialogTitle>Controlled</DialogTitle>
                <DialogDescription>Dialog description</DialogDescription>
                <Button data-testid="close-dialog-btn" onClick={() => setOpen(false)}>
                  Close Dialog
                </Button>
              </DialogContent>
            </Dialog>
          </>
        );
      };

      render(<ControlledDialog />);

      expect(screen.queryByText("Controlled")).not.toBeInTheDocument();

      await userEvent.click(screen.getByText("Open"));

      await waitFor(() => {
        expect(screen.getByText("Controlled")).toBeInTheDocument();
      });

      await userEvent.click(screen.getByTestId("close-dialog-btn"));

      await waitFor(() => {
        expect(screen.queryByText("Controlled")).not.toBeInTheDocument();
      });
    });
  });

  describe("Styling", () => {
    it("should apply custom className to DialogContent", async () => {
      render(
        <Dialog defaultOpen>
          <DialogContent className="custom-dialog" data-testid="dialog-content">
            <DialogTitle>Styled Dialog</DialogTitle>
            <DialogDescription>Dialog description</DialogDescription>
          </DialogContent>
        </Dialog>
      );

      expect(screen.getByTestId("dialog-content")).toHaveClass("custom-dialog");
    });
  });

  describe("Keyboard Navigation", () => {
    it("should close dialog on Escape key", async () => {
      render(
        <Dialog defaultOpen>
          <DialogContent>
            <DialogTitle>Escape Dialog</DialogTitle>
            <DialogDescription>Dialog description</DialogDescription>
          </DialogContent>
        </Dialog>
      );

      expect(screen.getByText("Escape Dialog")).toBeInTheDocument();

      fireEvent.keyDown(document, { key: "Escape" });

      await waitFor(() => {
        expect(screen.queryByText("Escape Dialog")).not.toBeInTheDocument();
      });
    });
  });
});
