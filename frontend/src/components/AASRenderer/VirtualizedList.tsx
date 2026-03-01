/**
 * VirtualizedList component for efficient rendering of large lists.
 *
 * Uses @tanstack/react-virtual to render only visible items,
 * dramatically improving performance for lists with 20+ items.
 */

import React, { useRef } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import type { FieldArrayWithId } from 'react-hook-form';

// Estimated item height for virtualization calculations
const ESTIMATED_ITEM_HEIGHT = 120;
// Extra items to render outside the visible area
const OVERSCAN_COUNT = 3;

interface VirtualizedListProps {
  /** React Hook Form field array */
  fields: FieldArrayWithId[];
  /** Render function for each item */
  renderItem: (field: FieldArrayWithId, index: number) => React.ReactNode;
  /** Container class name */
  className?: string;
  /** Container height. Defaults to 500px. Use '100%' for parent-controlled sizing. */
  height?: string | number;
}

/**
 * Renders a virtualized list that only mounts visible items.
 *
 * This component is used when lists exceed the virtualization threshold
 * (typically 20 items) to avoid DOM bloat and improve scroll performance.
 */
export const VirtualizedList: React.FC<VirtualizedListProps> = ({
  fields,
  renderItem,
  className = '',
  height = 500,
}) => {
  const parentRef = useRef<HTMLDivElement>(null);

  // eslint-disable-next-line react-hooks/incompatible-library -- TanStack Virtual hook is intentionally non-memoizable.
  const virtualizer = useVirtualizer({
    count: fields.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ESTIMATED_ITEM_HEIGHT,
    overscan: OVERSCAN_COUNT,
  });

  const items = virtualizer.getVirtualItems();

  return (
    <div
      ref={parentRef}
      className={`virtualized-list-container ${className}`}
      style={{
        height: typeof height === 'number' ? `${height}px` : height,
        overflow: 'auto',
      }}
    >
      <div
        style={{
          height: `${virtualizer.getTotalSize()}px`,
          width: '100%',
          position: 'relative',
        }}
      >
        {items.map((virtualItem) => {
          const field = fields[virtualItem.index];
          return (
            <div
              key={virtualItem.key}
              data-index={virtualItem.index}
              ref={virtualizer.measureElement}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                transform: `translateY(${virtualItem.start}px)`,
              }}
            >
              {renderItem(field, virtualItem.index)}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default VirtualizedList;
