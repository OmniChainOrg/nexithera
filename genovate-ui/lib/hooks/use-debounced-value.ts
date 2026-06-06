import { useEffect, useRef, useState } from 'react';

/**
 * Returns a value that updates only after `delay` ms have passed without a
 * new change. Used by the Scenario Explorer to throttle re-calls to
 * `POST /forecast/clinical` while sliders are dragged.
 */
export function useDebouncedValue<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  const handleRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (handleRef.current) clearTimeout(handleRef.current);
    handleRef.current = setTimeout(() => setDebounced(value), delay);
    return () => {
      if (handleRef.current) clearTimeout(handleRef.current);
    };
  }, [value, delay]);

  return debounced;
}
