import { useState } from 'react';
import { GradientButton } from '@/components/ui/GradientButton';
import { cn } from '@/lib/utils';

export interface CaptionEditorProps {
  captionText: string | null;
  onSave: (captionText: string) => Promise<void> | void;
  className?: string;
}

/** Textarea editor for a clip's caption text, with a save button. */
export function CaptionEditor({
  captionText,
  onSave,
  className,
}: CaptionEditorProps) {
  const [value, setValue] = useState(captionText ?? '');
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isDirty = value !== (captionText ?? '');

  const handleSave = async () => {
    setError(null);
    setIsSaving(true);
    try {
      await onSave(value);
    } catch {
      setError('Could not save the caption. Please try again.');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className={cn('space-y-3', className)}>
      <textarea
        value={value}
        onChange={(event) => setValue(event.target.value)}
        rows={4}
        placeholder="Add a caption for this clip..."
        className="w-full resize-none rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-ring"
      />
      {error && <p className="text-sm text-destructive">{error}</p>}
      <GradientButton
        type="button"
        onClick={handleSave}
        disabled={!isDirty || isSaving}
      >
        {isSaving ? 'Saving...' : 'Save caption'}
      </GradientButton>
    </div>
  );
}
