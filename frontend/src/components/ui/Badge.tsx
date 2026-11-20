import React from 'react';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'high' | 'medium' | 'low' | 'neutral' | 'brand' | 'demonstrated' | 'listed';
  size?: 'sm' | 'md';
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'neutral',
  size = 'md',
  className = '',
  ...props
}) => {
  const variants = {
    high: 'bg-emerald-50 text-emerald-700 border-emerald-200 font-semibold',
    medium: 'bg-amber-50 text-amber-700 border-amber-200 font-semibold',
    low: 'bg-rose-50 text-rose-700 border-rose-200 font-semibold',
    neutral: 'bg-slate-100 text-slate-700 border-slate-200',
    brand: 'bg-brand-50 text-brand-700 border-brand-200 font-medium',
    demonstrated: 'bg-blue-50 text-blue-700 border-blue-200 text-xs font-medium',
    listed: 'bg-slate-100 text-slate-600 border-slate-200 text-xs',
  };

  const sizes = {
    sm: 'text-[11px] px-2 py-0.5',
    md: 'text-xs px-2.5 py-1',
  };

  return (
    <span
      className={`inline-flex items-center rounded-md border tracking-wide uppercase ${variants[variant]} ${sizes[size]} ${className}`}
      {...props}
    >
      {children}
    </span>
  );
};

export const StatusBadge: React.FC<{ status: 'HIGH' | 'MEDIUM' | 'LOW'; className?: string }> = ({
  status,
  className = '',
}) => {
  const variantMap = {
    HIGH: 'high' as const,
    MEDIUM: 'medium' as const,
    LOW: 'low' as const,
  };
  return (
    <Badge variant={variantMap[status] || 'neutral'} className={className}>
      {status}
    </Badge>
  );
};
