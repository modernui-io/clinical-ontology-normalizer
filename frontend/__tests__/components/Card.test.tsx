/**
 * Tests for the Card components.
 *
 * Tests:
 * - Card rendering
 * - CardHeader, CardTitle, CardDescription
 * - CardContent, CardFooter
 * - CardAction
 * - Custom styling
 */

import { render, screen } from '@testing-library/react';
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
  CardAction,
} from '@/components/ui/card';

describe('Card', () => {
  describe('Card Base', () => {
    it('renders card element', () => {
      render(<Card data-testid="card">Content</Card>);
      const card = screen.getByTestId('card');
      expect(card).toBeInTheDocument();
    });

    it('renders children', () => {
      render(<Card>Card Content</Card>);
      expect(screen.getByText('Card Content')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      render(
        <Card className="custom-class" data-testid="card">
          Content
        </Card>
      );
      const card = screen.getByTestId('card');
      expect(card).toHaveClass('custom-class');
    });

    it('has data-slot attribute', () => {
      render(<Card data-testid="card">Content</Card>);
      const card = screen.getByTestId('card');
      expect(card).toHaveAttribute('data-slot', 'card');
    });

    it('has default styling classes', () => {
      render(<Card data-testid="card">Content</Card>);
      const card = screen.getByTestId('card');
      expect(card).toHaveClass('rounded-xl');
      expect(card).toHaveClass('border');
    });
  });

  describe('CardHeader', () => {
    it('renders header element', () => {
      render(<CardHeader data-testid="header">Header</CardHeader>);
      const header = screen.getByTestId('header');
      expect(header).toBeInTheDocument();
    });

    it('has data-slot attribute', () => {
      render(<CardHeader data-testid="header">Header</CardHeader>);
      const header = screen.getByTestId('header');
      expect(header).toHaveAttribute('data-slot', 'card-header');
    });

    it('applies custom className', () => {
      render(
        <CardHeader className="custom-header" data-testid="header">
          Header
        </CardHeader>
      );
      const header = screen.getByTestId('header');
      expect(header).toHaveClass('custom-header');
    });
  });

  describe('CardTitle', () => {
    it('renders title element', () => {
      render(<CardTitle>Card Title</CardTitle>);
      expect(screen.getByText('Card Title')).toBeInTheDocument();
    });

    it('has data-slot attribute', () => {
      render(<CardTitle data-testid="title">Title</CardTitle>);
      const title = screen.getByTestId('title');
      expect(title).toHaveAttribute('data-slot', 'card-title');
    });

    it('has font styling', () => {
      render(<CardTitle data-testid="title">Title</CardTitle>);
      const title = screen.getByTestId('title');
      expect(title).toHaveClass('font-semibold');
    });
  });

  describe('CardDescription', () => {
    it('renders description element', () => {
      render(<CardDescription>Card description text</CardDescription>);
      expect(screen.getByText('Card description text')).toBeInTheDocument();
    });

    it('has data-slot attribute', () => {
      render(<CardDescription data-testid="desc">Description</CardDescription>);
      const desc = screen.getByTestId('desc');
      expect(desc).toHaveAttribute('data-slot', 'card-description');
    });

    it('has muted foreground color', () => {
      render(<CardDescription data-testid="desc">Description</CardDescription>);
      const desc = screen.getByTestId('desc');
      expect(desc).toHaveClass('text-muted-foreground');
    });

    it('has smaller text size', () => {
      render(<CardDescription data-testid="desc">Description</CardDescription>);
      const desc = screen.getByTestId('desc');
      expect(desc).toHaveClass('text-sm');
    });
  });

  describe('CardContent', () => {
    it('renders content element', () => {
      render(<CardContent data-testid="content">Content here</CardContent>);
      const content = screen.getByTestId('content');
      expect(content).toBeInTheDocument();
    });

    it('has data-slot attribute', () => {
      render(<CardContent data-testid="content">Content</CardContent>);
      const content = screen.getByTestId('content');
      expect(content).toHaveAttribute('data-slot', 'card-content');
    });

    it('has padding', () => {
      render(<CardContent data-testid="content">Content</CardContent>);
      const content = screen.getByTestId('content');
      expect(content).toHaveClass('px-6');
    });
  });

  describe('CardFooter', () => {
    it('renders footer element', () => {
      render(<CardFooter data-testid="footer">Footer content</CardFooter>);
      const footer = screen.getByTestId('footer');
      expect(footer).toBeInTheDocument();
    });

    it('has data-slot attribute', () => {
      render(<CardFooter data-testid="footer">Footer</CardFooter>);
      const footer = screen.getByTestId('footer');
      expect(footer).toHaveAttribute('data-slot', 'card-footer');
    });

    it('has flex layout', () => {
      render(<CardFooter data-testid="footer">Footer</CardFooter>);
      const footer = screen.getByTestId('footer');
      expect(footer).toHaveClass('flex');
    });
  });

  describe('CardAction', () => {
    it('renders action element', () => {
      render(<CardAction data-testid="action">Action</CardAction>);
      const action = screen.getByTestId('action');
      expect(action).toBeInTheDocument();
    });

    it('has data-slot attribute', () => {
      render(<CardAction data-testid="action">Action</CardAction>);
      const action = screen.getByTestId('action');
      expect(action).toHaveAttribute('data-slot', 'card-action');
    });
  });

  describe('Full Card Composition', () => {
    it('renders complete card with all parts', () => {
      render(
        <Card data-testid="card">
          <CardHeader>
            <CardTitle>Card Title</CardTitle>
            <CardDescription>Card description</CardDescription>
          </CardHeader>
          <CardContent>
            <p>Card content goes here</p>
          </CardContent>
          <CardFooter>
            <button>Action</button>
          </CardFooter>
        </Card>
      );

      expect(screen.getByTestId('card')).toBeInTheDocument();
      expect(screen.getByText('Card Title')).toBeInTheDocument();
      expect(screen.getByText('Card description')).toBeInTheDocument();
      expect(screen.getByText('Card content goes here')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /action/i })).toBeInTheDocument();
    });

    it('renders card with action button in header', () => {
      render(
        <Card data-testid="card">
          <CardHeader>
            <CardTitle>Title</CardTitle>
            <CardAction>
              <button>Edit</button>
            </CardAction>
          </CardHeader>
        </Card>
      );

      expect(screen.getByRole('button', { name: /edit/i })).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('card is accessible as a container', () => {
      render(
        <Card role="article" aria-label="Patient information">
          <CardContent>Patient data</CardContent>
        </Card>
      );

      const card = screen.getByRole('article');
      expect(card).toHaveAttribute('aria-label', 'Patient information');
    });

    it('supports heading levels in title', () => {
      render(
        <Card>
          <CardHeader>
            <CardTitle>
              <h2>Heading Title</h2>
            </CardTitle>
          </CardHeader>
        </Card>
      );

      expect(screen.getByRole('heading', { level: 2 })).toBeInTheDocument();
    });
  });
});
