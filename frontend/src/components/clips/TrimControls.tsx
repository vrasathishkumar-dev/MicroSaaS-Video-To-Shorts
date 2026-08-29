import { useState } from 'react';
import { GradientButton } from '@/components/ui/GradientButton';
import { cn } from '@/lib/utils';

export interface TrimControlsProps {
  startTime: number;
  endTime: number;
  onSave: (startTime: number, endTime: number) => Promise<void> | void;
  className?: string;
}

/**
 * Numeric start/end time editor for trimming a clip. Validates that
 * end_time stays greater than start_time before allowing a save.
 */
export function TrimControls({
  startTime,
  endTime,
  onSave,
  className,
}: TrimControlsProps) {
  const [start, setStart] = useState(startTime);
  const [end, setEnd] = useState(endTime);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isValid = start >= 0 && end > start;
  const isDirty = start !== startTime || end !== endTime;

  const handleSave = async () => {
    if (!isValid) {
      setError('End time must be greater than start time.');
      return;
    }
    setError(null);
    setIsSaving(true);
    try {
      await onSave(start, end);
    } catch {
      setError('Could not save the trim. Please try again.');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className={cn('space-y-4', className)}>
      <div className="grid grid-cols-2 gap-4">
        <label className="flex flex-col gap-1 text-sm font-medium text-foreground">
          Start time (s)
          <input
            type="number"
            min={0}
            step={0.1}
            value={start}
            onChange={(event) => setStart(Number(event.target.value))}
            className="rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-ring"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium text-foreground">
          End time (s)
          <input
            type="number"
            min={0}
            step={0.1}
            value={end}
            onChange={(event) => setEnd(Number(event.target.value))}
            className="rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-ring"
          />
        </label>
      </div>

      {!isValid && (
        <p className="text-sm text-destructive">
          End time must be greater than start time.
        </p>
      )}
      {error && <p className="text-sm text-destructive">{error}</p>}

      <GradientButton
        type="button"
        onClick={handleSave}
        disabled={!isValid || !isDirty || isSaving}
      >
        {isSaving ? 'Saving...' : 'Save trim'}
      </GradientButton>
    </div>
  );
}
