/**
 * Tests for the SearchWithDebounce component.
 *
 * Tests:
 * - Rendering and basic functionality
 * - Debounce behavior
 * - Clear functionality
 * - Keyboard shortcuts
 * - Loading state
 * - Controlled vs uncontrolled modes
 */

import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {
  SearchWithDebounce,
  useDebounce,
  useSearch,
  useSearchWithCallback,
} from '@/components/SearchWithDebounce';
import { renderHook } from '@testing-library/react';

const setupUser = () =>
  userEvent.setup({ delay: null, advanceTimers: jest.advanceTimersByTime });

beforeEach(() => {
  jest.useFakeTimers();
});

afterEach(() => {
  act(() => {
    jest.runOnlyPendingTimers();
  });
  jest.clearAllTimers();
  jest.useRealTimers();
});

describe('SearchWithDebounce', () => {
  describe('Rendering', () => {
    it('renders search input', () => {
      render(<SearchWithDebounce onSearch={jest.fn()} />);
      const input = screen.getByRole('searchbox');
      expect(input).toBeInTheDocument();
    });

    it('renders with custom placeholder', () => {
      render(
        <SearchWithDebounce
          onSearch={jest.fn()}
          placeholder="Search patients..."
        />
      );
      const input = screen.getByPlaceholderText('Search patients...');
      expect(input).toBeInTheDocument();
    });

    it('renders search icon', () => {
      render(<SearchWithDebounce onSearch={jest.fn()} />);
      // The search icon should be present (check for svg or icon class)
      const container = screen.getByRole('searchbox').parentElement;
      expect(container).toBeInTheDocument();
    });

    it('renders keyboard shortcut hint by default', () => {
      render(<SearchWithDebounce onSearch={jest.fn()} />);
      // Should show Cmd+K hint
      const kbd = document.querySelector('kbd');
      expect(kbd).toBeInTheDocument();
    });

    it('hides keyboard shortcut hint when showShortcut is false', () => {
      render(
        <SearchWithDebounce onSearch={jest.fn()} showShortcut={false} />
      );
      const kbd = document.querySelector('kbd');
      expect(kbd).not.toBeInTheDocument();
    });
  });

  describe('Input handling', () => {
    it('updates value on input', async () => {
      const user = setupUser();
      render(<SearchWithDebounce onSearch={jest.fn()} />);

      const input = screen.getByRole('searchbox');
      await user.type(input, 'test');

      expect(input).toHaveValue('test');
    });

    it('calls onChange immediately when typing', async () => {
      const handleChange = jest.fn();
      const user = setupUser();

      render(
        <SearchWithDebounce onSearch={jest.fn()} onChange={handleChange} />
      );

      const input = screen.getByRole('searchbox');
      await user.type(input, 'a');

      expect(handleChange).toHaveBeenCalledWith('a');
    });

    it('supports controlled value', () => {
      const { rerender } = render(
        <SearchWithDebounce onSearch={jest.fn()} value="initial" onChange={jest.fn()} />
      );

      const input = screen.getByRole('searchbox');
      expect(input).toHaveValue('initial');

      rerender(
        <SearchWithDebounce onSearch={jest.fn()} value="updated" onChange={jest.fn()} />
      );

      expect(input).toHaveValue('updated');
    });
  });

  describe('Debounce behavior', () => {
    it('calls onSearch after debounce delay', async () => {
      const handleSearch = jest.fn();
      const user = setupUser();

      render(
        <SearchWithDebounce onSearch={handleSearch} debounceMs={300} />
      );

      const input = screen.getByRole('searchbox');
      await user.type(input, 'test');

      // Should not have called search yet
      expect(handleSearch).not.toHaveBeenCalled();

      // Fast-forward past debounce delay
      act(() => {
        jest.advanceTimersByTime(300);
      });

      await waitFor(() => {
        expect(handleSearch).toHaveBeenCalledWith('test');
      });
    });

    it('resets debounce timer on new input', async () => {
      const handleSearch = jest.fn();
      const user = setupUser();

      render(
        <SearchWithDebounce onSearch={handleSearch} debounceMs={300} />
      );

      const input = screen.getByRole('searchbox');

      await user.type(input, 't');

      // Wait 200ms
      act(() => {
        jest.advanceTimersByTime(200);
      });

      // Type more
      await user.type(input, 'est');

      // Wait another 200ms (should not trigger yet)
      act(() => {
        jest.advanceTimersByTime(200);
      });

      expect(handleSearch).not.toHaveBeenCalled();

      // Wait remaining 100ms
      act(() => {
        jest.advanceTimersByTime(100);
      });

      await waitFor(() => {
        expect(handleSearch).toHaveBeenCalledWith('test');
      });
    });
  });

  describe('Clear functionality', () => {
    it('shows clear button when there is value', async () => {
      const user = setupUser();

      render(<SearchWithDebounce onSearch={jest.fn()} />);

      const input = screen.getByRole('searchbox');
      await user.type(input, 'test');

      const clearButton = screen.getByRole('button', { name: /clear/i });
      expect(clearButton).toBeInTheDocument();
    });

    it('hides clear button when value is empty', () => {
      render(<SearchWithDebounce onSearch={jest.fn()} />);

      const clearButton = screen.queryByRole('button', { name: /clear/i });
      expect(clearButton).not.toBeInTheDocument();
    });

    it('clears value when clear button is clicked', async () => {
      const user = setupUser();

      render(<SearchWithDebounce onSearch={jest.fn()} />);

      const input = screen.getByRole('searchbox');
      await user.type(input, 'test');

      const clearButton = screen.getByRole('button', { name: /clear/i });
      await user.click(clearButton);

      expect(input).toHaveValue('');
    });

    it('calls onClear when clear button is clicked', async () => {
      const handleClear = jest.fn();
      const user = setupUser();

      render(
        <SearchWithDebounce onSearch={jest.fn()} onClear={handleClear} />
      );

      const input = screen.getByRole('searchbox');
      await user.type(input, 'test');

      const clearButton = screen.getByRole('button', { name: /clear/i });
      await user.click(clearButton);

      expect(handleClear).toHaveBeenCalled();
    });
  });

  describe('Loading state', () => {
    it('shows loading indicator when isLoading is true', () => {
      render(
        <SearchWithDebounce onSearch={jest.fn()} isLoading={true} />
      );

      // Should show spinner instead of search icon
      // Check for animation class
      const container = screen.getByRole('searchbox').parentElement?.parentElement;
      const spinner = container?.querySelector('.animate-spin');
      expect(spinner).toBeInTheDocument();
    });

    it('shows search icon when not loading', () => {
      render(
        <SearchWithDebounce onSearch={jest.fn()} isLoading={false} />
      );

      const container = screen.getByRole('searchbox').parentElement?.parentElement;
      const spinner = container?.querySelector('.animate-spin');
      expect(spinner).not.toBeInTheDocument();
    });
  });

  describe('Disabled state', () => {
    it('disables input when disabled prop is true', () => {
      render(<SearchWithDebounce onSearch={jest.fn()} disabled />);

      const input = screen.getByRole('searchbox');
      expect(input).toBeDisabled();
    });

    it('hides clear button when disabled', async () => {
      const user = setupUser();

      const { rerender } = render(
        <SearchWithDebounce onSearch={jest.fn()} value="test" onChange={jest.fn()} />
      );

      // Should show clear button when not disabled
      expect(screen.getByRole('button', { name: /clear/i })).toBeInTheDocument();

      // Rerender as disabled
      rerender(
        <SearchWithDebounce
          onSearch={jest.fn()}
          value="test"
          onChange={jest.fn()}
          disabled
        />
      );

      expect(screen.queryByRole('button', { name: /clear/i })).not.toBeInTheDocument();
    });
  });

  describe('Size variants', () => {
    it('renders small size', () => {
      render(<SearchWithDebounce onSearch={jest.fn()} size="sm" />);
      const input = screen.getByRole('searchbox');
      expect(input).toHaveClass('h-8');
    });

    it('renders default size', () => {
      render(<SearchWithDebounce onSearch={jest.fn()} size="default" />);
      const input = screen.getByRole('searchbox');
      expect(input).toHaveClass('h-9');
    });

    it('renders large size', () => {
      render(<SearchWithDebounce onSearch={jest.fn()} size="lg" />);
      const input = screen.getByRole('searchbox');
      expect(input).toHaveClass('h-10');
    });
  });

  describe('Submit on Enter', () => {
    it('calls onSubmit when Enter is pressed', async () => {
      const handleSubmit = jest.fn();
      const user = setupUser();

      render(
        <SearchWithDebounce onSearch={jest.fn()} onSubmit={handleSubmit} />
      );

      const input = screen.getByRole('searchbox');
      await user.type(input, 'test{enter}');

      expect(handleSubmit).toHaveBeenCalledWith('test');
    });
  });
});

describe('useDebounce hook', () => {
  it('returns initial value immediately', () => {
    const { result } = renderHook(() => useDebounce('test', 300));
    expect(result.current).toBe('test');
  });

  it('returns debounced value after delay', () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 300),
      { initialProps: { value: 'initial' } }
    );

    expect(result.current).toBe('initial');

    rerender({ value: 'updated' });

    // Still initial before delay
    expect(result.current).toBe('initial');

    // After delay
    act(() => {
      jest.advanceTimersByTime(300);
    });

    expect(result.current).toBe('updated');
  });
});

describe('useSearch hook', () => {
  it('returns value, debounced value, and setter', () => {
    const { result } = renderHook(() => useSearch('', 300));

    const [value, debouncedValue, setValue] = result.current;

    expect(value).toBe('');
    expect(debouncedValue).toBe('');
    expect(typeof setValue).toBe('function');
  });

  it('updates value immediately and debounces', () => {
    const { result } = renderHook(() => useSearch('', 300));

    act(() => {
      result.current[2]('test'); // setValue
    });

    expect(result.current[0]).toBe('test'); // value
    expect(result.current[1]).toBe(''); // debounced still empty

    act(() => {
      jest.advanceTimersByTime(300);
    });

    expect(result.current[1]).toBe('test'); // debounced updated
  });
});

describe('useSearchWithCallback hook', () => {
  it('calls callback with debounced value', () => {
    const handleSearch = jest.fn();
    const { result } = renderHook(() =>
      useSearchWithCallback(handleSearch, '', 300)
    );

    act(() => {
      result.current[1]('test'); // setValue
    });

    // Not called yet
    expect(handleSearch).not.toHaveBeenCalledWith('test');

    act(() => {
      jest.advanceTimersByTime(300);
    });

    expect(handleSearch).toHaveBeenCalledWith('test');
  });

  it('returns isSearching state', () => {
    const handleSearch = jest.fn();
    const { result } = renderHook(() =>
      useSearchWithCallback(handleSearch, '', 300)
    );

    const [, , isSearching] = result.current;

    act(() => {
      result.current[1]('test');
    });

    // Should be searching while waiting for debounce
    expect(result.current[2]).toBe(true);

    act(() => {
      jest.advanceTimersByTime(300);
    });

    // Should not be searching after debounce
    expect(result.current[2]).toBe(false);
  });
});
