import { forwardRef } from 'react';
import * as ProgressPrimitive from '@radix-ui/react-progress';
import { cn } from '@/lib/utils';

interface ProgressProps {
  value: number;
  className?: string;
  indicatorClassName?: string;
}

const Progress = forwardRef<HTMLDivElement, ProgressProps>(
  ({ value, className, indicatorClassName }, ref) => (
    <ProgressPrimitive.Root
      ref={ref}
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




