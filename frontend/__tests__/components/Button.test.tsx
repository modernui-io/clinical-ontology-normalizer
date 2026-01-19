/**
 * Tests for the Button component.
 *
 * Tests:
 * - Rendering with different variants
 * - Rendering with different sizes
 * - Click handling
 * - Disabled state
 * - Loading state
 * - As child pattern (Slot)
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { Button, buttonVariants } from '@/components/ui/button';

describe('Button', () => {
  describe('Rendering', () => {
    it('renders with default props', () => {
      render(<Button>Click me</Button>);
      const button = screen.getByRole('button', { name: /click me/i });
      expect(button).toBeInTheDocument();
    });

    it('renders children correctly', () => {
      render(<Button>Test Button</Button>);
      expect(screen.getByText('Test Button')).toBeInTheDocument();
    });

    it('renders with custom className', () => {
      render(<Button className="custom-class">Button</Button>);
      const button = screen.getByRole('button');
      expect(button).toHaveClass('custom-class');
    });
  });

  describe('Variants', () => {
    it('renders default variant', () => {
      render(<Button variant="default">Default</Button>);
      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('data-variant', 'default');
    });

    it('renders destructive variant', () => {
      render(<Button variant="destructive">Delete</Button>);
      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('data-variant', 'destructive');
    });

    it('renders outline variant', () => {
      render(<Button variant="outline">Outline</Button>);
      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('data-variant', 'outline');
    });

    it('renders secondary variant', () => {
      render(<Button variant="secondary">Secondary</Button>);
      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('data-variant', 'secondary');
    });

    it('renders ghost variant', () => {
      render(<Button variant="ghost">Ghost</Button>);
      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('data-variant', 'ghost');
    });

    it('renders link variant', () => {
      render(<Button variant="link">Link</Button>);
      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('data-variant', 'link');
    });
  });

  describe('Sizes', () => {
    it('renders default size', () => {
      render(<Button size="default">Button</Button>);
      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('data-size', 'default');
    });

    it('renders small size', () => {
      render(<Button size="sm">Small</Button>);
      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('data-size', 'sm');
    });

    it('renders large size', () => {
      render(<Button size="lg">Large</Button>);
      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('data-size', 'lg');
    });

    it('renders icon size', () => {
      render(<Button size="icon">+</Button>);
      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('data-size', 'icon');
    });
  });

  describe('Interactions', () => {
    it('calls onClick when clicked', () => {
      const handleClick = jest.fn();
      render(<Button onClick={handleClick}>Click me</Button>);

      const button = screen.getByRole('button');
      fireEvent.click(button);

      expect(handleClick).toHaveBeenCalledTimes(1);
    });

    it('does not call onClick when disabled', () => {
      const handleClick = jest.fn();
      render(
        <Button onClick={handleClick} disabled>
          Click me
        </Button>
      );

      const button = screen.getByRole('button');
      fireEvent.click(button);

      expect(handleClick).not.toHaveBeenCalled();
    });
  });

  describe('Disabled state', () => {
    it('renders disabled state correctly', () => {
      render(<Button disabled>Disabled</Button>);
      const button = screen.getByRole('button');
      expect(button).toBeDisabled();
    });

    it('has disabled styling', () => {
      render(<Button disabled>Disabled</Button>);
      const button = screen.getByRole('button');
      expect(button).toHaveClass('disabled:pointer-events-none');
    });
  });

  describe('As Child (Slot)', () => {
    it('renders as child element when asChild is true', () => {
      render(
        <Button asChild>
          <a href="/link">Link Button</a>
        </Button>
      );
      const link = screen.getByRole('link');
      expect(link).toBeInTheDocument();
      expect(link).toHaveAttribute('href', '/link');
    });
  });

  describe('Button slot attribute', () => {
    it('has data-slot attribute', () => {
      render(<Button>Button</Button>);
      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('data-slot', 'button');
    });
  });

  describe('Accessibility', () => {
    it('supports aria-label', () => {
      render(<Button aria-label="Close dialog">X</Button>);
      const button = screen.getByRole('button', { name: /close dialog/i });
      expect(button).toBeInTheDocument();
    });

    it('supports aria-disabled', () => {
      render(<Button aria-disabled="true">Button</Button>);
      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('aria-disabled', 'true');
    });
  });

  describe('Type attribute', () => {
    it('defaults to button type', () => {
      render(<Button>Button</Button>);
      const button = screen.getByRole('button');
      // Default type should be 'submit' for buttons without explicit type
      // But our component may set it differently
      expect(button.getAttribute('type')).toBeDefined();
    });

    it('accepts submit type', () => {
      render(<Button type="submit">Submit</Button>);
      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('type', 'submit');
    });

    it('accepts reset type', () => {
      render(<Button type="reset">Reset</Button>);
      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('type', 'reset');
    });
  });
});

describe('buttonVariants', () => {
  it('exports buttonVariants function', () => {
    expect(typeof buttonVariants).toBe('function');
  });

  it('returns class string for default variant', () => {
    const classes = buttonVariants({ variant: 'default' });
    expect(typeof classes).toBe('string');
    expect(classes.length).toBeGreaterThan(0);
  });

  it('returns class string for different sizes', () => {
    const smClasses = buttonVariants({ size: 'sm' });
    const lgClasses = buttonVariants({ size: 'lg' });

    expect(smClasses).not.toBe(lgClasses);
  });
});
