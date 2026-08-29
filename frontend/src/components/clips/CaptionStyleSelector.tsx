import { Check, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { CaptionStylePreset } from '@/types';

export interface CaptionStyleOption {
  id: CaptionStylePreset;
  name: string;
  description: string;
  previewText: string;
  previewClass: string;
}

export const CAPTION_PRESETS: CaptionStyleOption[] = [
  {
    id: 'hormozi',
    name: 'Hormozi Pop',
    description: 'High-contrast bold font with bright yellow & lime green keywords',
    previewText: 'THIS SECRET CHANGES EVERYTHING',
    previewClass: 'bg-black/90 text-yellow-300 font-black uppercase tracking-wider border-2 border-lime-400 shadow-[0_0_15px_rgba(163,230,53,0.5)]',
  },
  {
    id: 'neon',
    name: 'Neon Cyber',
    description: 'Glowing cyan and magenta text with modern dropshadow',
    previewText: 'UNBELIEVABLE RESULTS',
    previewClass: 'bg-black/80 text-cyan-300 font-extrabold tracking-wide border border-cyan-400 shadow-[0_0_12px_rgba(34,211,238,0.7)]',
  },
  {
    id: 'bold_box',
    name: 'Viral Box',
    description: 'Crisp white typography on semi-transparent dark backdrop',
    previewText: 'Watch Until The End',
    previewClass: 'bg-black/75 text-white font-bold px-3 py-1 rounded shadow-lg',
  },
  {
    id: 'karaoke',
    name: 'Karaoke Wave',
    description: 'Word-by-word active speaker highlight with gradient fill',
    previewText: 'Step by Step Blueprint',
    previewClass: 'bg-black/60 text-emerald-300 font-extrabold uppercase border-b-2 border-emerald-400',
  },
  {
    id: 'minimal',
    name: 'Clean Minimal',
    description: 'Clean modern sans-serif subtitles for podcasts & interviews',
    previewText: 'The essential technique for creators',
    previewClass: 'text-white font-medium drop-shadow-[0_2px_4px_rgba(0,0,0,0.9)]',
  },
];

export interface CaptionStyleSelectorProps {
  selectedPreset: CaptionStylePreset;
  onSelect: (preset: CaptionStylePreset) => void;
  className?: string;
}

export function CaptionStyleSelector({
  selectedPreset,
  onSelect,
  className,
}: CaptionStyleSelectorProps) {
  return (
    <div className={cn('space-y-3', className)}>
      <div className="flex items-center justify-between">
        <label className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          <Sparkles className="h-3.5 w-3.5 text-primary" />
          Caption Style & Animation
        </label>
        <span className="text-xs text-muted-foreground">AI Subtitle Engine</span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
        {CAPTION_PRESETS.map((preset) => {
          const isSelected = selectedPreset === preset.id;
          return (
            <button
              key={preset.id}
              type="button"
              onClick={() => onSelect(preset.id)}
              className={cn(
                'relative flex flex-col gap-2 rounded-xl border p-3 text-left transition-all',
                isSelected
                  ? 'border-primary bg-primary/10 shadow-[0_0_12px_rgba(30,215,96,0.2)]'
                  : 'border-glass-border bg-glass-bg hover:border-border hover:bg-muted/40',
              )}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-foreground">
                  {preset.name}
                </span>
                {isSelected && (
                  <span className="flex h-4 w-4 items-center justify-center rounded-full bg-primary text-primary-foreground">
                    <Check className="h-2.5 w-2.5 stroke-[3]" />
                  </span>
                )}
              </div>

              <div className="flex items-center justify-center rounded-lg bg-black/70 p-2.5">
                <span className={cn('px-2 py-1 text-xs text-center', preset.previewClass)}>
                  {preset.previewText}
                </span>
              </div>

              <p className="text-[11px] text-muted-foreground leading-snug">
                {preset.description}
              </p>
            </button>
          );
        })}
      </div>
    </div>
  );
}
