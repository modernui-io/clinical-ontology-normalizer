/**
 * Tests for Table component.
 *
 * Tests:
 * - Basic table structure rendering
 * - Header rendering
 * - Body rendering with rows
 * - Empty state
 * - Custom styling
 * - Accessibility attributes
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

describe("Table Components", () => {
  describe("Basic Table Rendering", () => {
    it("should render a table element", () => {
      render(
        <Table>
          <TableBody>
            <TableRow>
              <TableCell>Content</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      expect(screen.getByRole("table")).toBeInTheDocument();
    });

    it("should render table with caption", () => {
      render(
        <Table>
          <TableCaption>Table Caption</TableCaption>
          <TableBody>
            <TableRow>
              <TableCell>Content</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      expect(screen.getByText("Table Caption")).toBeInTheDocument();
    });
  });

  describe("TableHeader", () => {
    it("should render header with column names", () => {
      render(
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow>
              <TableCell>John</TableCell>
              <TableCell>john@example.com</TableCell>
              <TableCell>Active</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      expect(screen.getByText("Name")).toBeInTheDocument();
      expect(screen.getByText("Email")).toBeInTheDocument();
      expect(screen.getByText("Status")).toBeInTheDocument();
    });

    it("should render column headers as th elements", () => {
      render(
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Column 1</TableHead>
              <TableHead>Column 2</TableHead>
            </TableRow>
          </TableHeader>
        </Table>
      );

      const headers = screen.getAllByRole("columnheader");
      expect(headers).toHaveLength(2);
    });
  });

  describe("TableBody", () => {
    it("should render multiple rows", () => {
      render(
        <Table>
          <TableBody>
            <TableRow>
              <TableCell>Row 1</TableCell>
            </TableRow>
            <TableRow>
              <TableCell>Row 2</TableCell>
            </TableRow>
            <TableRow>
              <TableCell>Row 3</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      expect(screen.getByText("Row 1")).toBeInTheDocument();
      expect(screen.getByText("Row 2")).toBeInTheDocument();
      expect(screen.getByText("Row 3")).toBeInTheDocument();
    });

    it("should render cells as td elements", () => {
      render(
        <Table>
          <TableBody>
            <TableRow>
              <TableCell>Cell 1</TableCell>
              <TableCell>Cell 2</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      const cells = screen.getAllByRole("cell");
      expect(cells).toHaveLength(2);
    });
  });

  describe("TableFooter", () => {
    it("should render footer row", () => {
      render(
        <Table>
          <TableBody>
            <TableRow>
              <TableCell>Data</TableCell>
              <TableCell>100</TableCell>
            </TableRow>
          </TableBody>
          <TableFooter>
            <TableRow>
              <TableCell>Total</TableCell>
              <TableCell>100</TableCell>
            </TableRow>
          </TableFooter>
        </Table>
      );

      expect(screen.getByText("Total")).toBeInTheDocument();
    });
  });

  describe("Complex Table", () => {
    const renderCompleteTable = () => {
      const data = [
        { id: 1, name: "John Doe", email: "john@example.com", role: "Admin" },
        { id: 2, name: "Jane Smith", email: "jane@example.com", role: "User" },
        { id: 3, name: "Bob Johnson", email: "bob@example.com", role: "User" },
      ];

      return render(
        <Table>
          <TableCaption>A list of users</TableCaption>
          <TableHeader>
            <TableRow>
              <TableHead>ID</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Role</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((user) => (
              <TableRow key={user.id}>
                <TableCell>{user.id}</TableCell>
                <TableCell>{user.name}</TableCell>
                <TableCell>{user.email}</TableCell>
                <TableCell>{user.role}</TableCell>
              </TableRow>
            ))}
          </TableBody>
          <TableFooter>
            <TableRow>
              <TableCell colSpan={3}>Total Users</TableCell>
              <TableCell>{data.length}</TableCell>
            </TableRow>
          </TableFooter>
        </Table>
      );
    };

    it("should render all table parts correctly", () => {
      renderCompleteTable();

      // Caption
      expect(screen.getByText("A list of users")).toBeInTheDocument();

      // Headers
      expect(screen.getByText("ID")).toBeInTheDocument();
      expect(screen.getByText("Name")).toBeInTheDocument();

      // Data rows
      expect(screen.getByText("John Doe")).toBeInTheDocument();
      expect(screen.getByText("jane@example.com")).toBeInTheDocument();

      // Footer
      expect(screen.getByText("Total Users")).toBeInTheDocument();
    });

    it("should have correct number of rows", () => {
      renderCompleteTable();

      const rows = screen.getAllByRole("row");
      // 1 header row + 3 data rows + 1 footer row = 5
      expect(rows).toHaveLength(5);
    });
  });

  describe("Styling", () => {
    it("should apply custom className to Table", () => {
      render(
        <Table className="custom-table" data-testid="table">
          <TableBody>
            <TableRow>
              <TableCell>Content</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      expect(screen.getByTestId("table")).toHaveClass("custom-table");
    });

    it("should apply custom className to TableRow", () => {
      render(
        <Table>
          <TableBody>
            <TableRow className="highlighted-row" data-testid="row">
              <TableCell>Content</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      expect(screen.getByTestId("row")).toHaveClass("highlighted-row");
    });

    it("should apply custom className to TableCell", () => {
      render(
        <Table>
          <TableBody>
            <TableRow>
              <TableCell className="custom-cell" data-testid="cell">
                Content
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      expect(screen.getByTestId("cell")).toHaveClass("custom-cell");
    });
  });

  describe("Accessibility", () => {
    it("should have proper table structure", () => {
      render(
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Column</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow>
              <TableCell>Data</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      expect(screen.getByRole("table")).toBeInTheDocument();
      expect(screen.getByRole("columnheader")).toBeInTheDocument();
      expect(screen.getByRole("cell")).toBeInTheDocument();
    });

    it("should support aria-label on table", () => {
      render(
        <Table aria-label="User data table">
          <TableBody>
            <TableRow>
              <TableCell>Content</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      expect(screen.getByLabelText("User data table")).toBeInTheDocument();
    });
  });

  describe("Empty Table", () => {
    it("should render empty table body", () => {
      render(
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Email</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow>
              <TableCell colSpan={2} className="text-center">
                No data available
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      expect(screen.getByText("No data available")).toBeInTheDocument();
    });
  });
});
