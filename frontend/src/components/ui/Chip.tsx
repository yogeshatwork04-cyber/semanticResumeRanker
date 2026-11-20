import React from 'react';
import { X } from 'lucide-react';

export interface ChipProps {
  label: string;
  onRemove?: () => void;
  variant?: 'default' | 'matched' | 'partial' | 'missing' | 'brand';
  subLabel?: string;
  badge?: React.ReactNode;
  className?: string;
}

export const Chip: React.FC<ChipProps> = ({
  label,
  onRemove,
  variant = 'default',
  subLabel,
  badge,
  className = '',
}) => {
  const variants = {
    default: 'bg-slate-100 text-slate-800 border-slate-200',
    matched: 'bg-emerald-50/80 text-emerald-900 border-emerald-300',
    partial: 'bg-amber-50/80 text-amber-900 border-amber-300',
    missing: 'bg-rose-50/80 text-rose-900 border-rose-300',
    brand: 'bg-brand-50 text-brand-900 border-brand-200',
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium transition-all ${variants[variant]} ${className}`}
    >
      <span className="font-semibold">{label}</span>
      {subLabel && <span className="text-[11px] opacity-80">({subLabel})</span>}
      {badge && <span className="inline-flex shrink-0">{badge}</span>}
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          className="p-0.5 ml-0.5 rounded-full hover:bg-black/10 focus:outline-none transition-colors"
          aria-label={`Remove ${label}`}
        >
          <X className="w-3 h-3" />
        </button>
      )}
    </span>
  );
};

