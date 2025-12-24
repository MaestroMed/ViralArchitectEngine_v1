import { cn } from '@/lib/utils';
import { getScoreColor } from '@/lib/utils';

interface ScoreBarProps {
  score: number;
  max?: number;
  label?: string;
  showValue?: boolean;
  size?: 'sm' | 'md';
  className?: string;
}

export function ScoreBar({
  score,
  max = 100,
  label,
  showValue = true,
  size = 'md',
  className,
}: ScoreBarProps) {
  const percentage = (score / max) * 100;
  const color = getScoreColor(score);

  const colorClasses = {
    high: 'bg-viral-high',
    medium: 'bg-viral-medium',
    low: 'bg-viral-low',
  };

  return (
    <div className={cn('space-y-1', className)}>
      {(label || showValue) && (
        <div className="flex items-center justify-between text-xs">
          {label && <span className="text-[var(--text-muted)]">{label}</span>}
          {showValue && (
            <span className={cn('font-medium', `text-viral-${color}`)}>
              {score.toFixed(0)}
            </span>
          )}
        </div>
      )}
      <div
        className={cn(
          'w-full bg-[var(--border-color)] rounded-full overflow-hidden',
          size === 'sm' ? 'h-1' : 'h-1.5'
        )}
      >
        <div
          className={cn(
            'h-full rounded-full transition-all duration-500',
            colorClasses[color]
          )}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

interface ScoreCircleProps {
  score: number;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export function ScoreCircle({ score, size = 'md', className }: ScoreCircleProps) {
  const color = getScoreColor(score);
  
  const sizeClasses = {
    sm: 'w-8 h-8 text-xs',
    md: 'w-12 h-12 text-sm',
    lg: 'w-16 h-16 text-lg',
  };

  const colorClasses = {
    high: 'bg-viral-high/10 text-viral-high border-viral-high',
    medium: 'bg-viral-medium/10 text-viral-medium border-viral-medium',
    low: 'bg-viral-low/10 text-viral-low border-viral-low',
  };

  return (
    <div
      className={cn(
        'rounded-full flex items-center justify-center font-bold border-2',
        sizeClasses[size],
        colorClasses[color],
        className
      )}
    >
      {score.toFixed(0)}
    </div>
  );
}




