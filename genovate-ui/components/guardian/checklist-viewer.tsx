'use client';

import { useState } from 'react';

export interface ChecklistItem {
  id: string;
  label: string;
  required?: boolean;
}

interface ChecklistViewerProps {
  items: ChecklistItem[];
  /** Notifies parent of pass/fail state. */
  onChange?: (state: Record<string, boolean>) => void;
}

export function ChecklistViewer({ items, onChange }: ChecklistViewerProps) {
  const [state, setState] = useState<Record<string, boolean>>({});

  const toggle = (id: string) => {
    const next = { ...state, [id]: !state[id] };
    setState(next);
    onChange?.(next);
  };

  return (
    <ul className="space-y-2">
      {items.map((item) => (
        <li key={item.id} className="flex items-start gap-2">
          <input
            type="checkbox"
            id={`chk-${item.id}`}
            checked={!!state[item.id]}
            onChange={() => toggle(item.id)}
            className="mt-1 h-4 w-4 rounded border-input"
          />
          <label htmlFor={`chk-${item.id}`} className="text-sm">
            {item.label}
            {item.required && <span className="ml-1 text-destructive">*</span>}
          </label>
        </li>
      ))}
    </ul>
  );
}
