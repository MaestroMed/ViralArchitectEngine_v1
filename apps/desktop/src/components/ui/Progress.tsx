import { forwardRef } from 'react';
import * as ProgressPrimitive from '@radix-ui/react-progress';
import { cn } from '@/lib/utils';

interface ProgressProps {
  value: number;
  max?: number;
  /** Accessible name for the bar, e.g. "Progression du job". */
  label?: string;
  className?: string;
  indicatorClassName?: string;
}

const Progress = forwardRef<HTMLDivElement, ProgressProps>(
  ({ value, max = 100, label, className, indicatorClassName }, ref) => (
    <ProgressPrimitive.Root
      ref={ref}
      // Radix sets role="progressbar" + aria-valuemin/max/now from value/max.
      value={value}
      max={max}
      aria-label={label}
      aria-valuetext={`${Math.round((value / max) * 100)}%`}
      className={cn(
        'relative h-1 w-full overflow-hidden rounded-full bg-[var(--border-color)]',
        className
      )}
    >
      <ProgressPrimitive.Indicator
        className={cn(
          'h-full bg-[var(--accent-color)] transition-all duration-300 ease-out',
          indicatorClassName
        )}
        style={{ width: `${value}%` }}
      />
    </ProgressPrimitive.Root>
  )
);

Progress.displayName = 'Progress';

export { Progress };




