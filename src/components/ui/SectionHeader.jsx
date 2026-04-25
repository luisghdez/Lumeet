import React from 'react';

export default function SectionHeader({
  eyebrow,
  title,
  description,
  action,
  align = 'split',
  className = '',
}) {
  const isSplit = align === 'split';

  return (
    <header
      className={`flex flex-col gap-6 ${
        isSplit ? 'md:flex-row md:items-end md:justify-between' : 'items-start'
      } ${className}`}
    >
      <div className="max-w-2xl">
        {eyebrow && (
          <p className="text-xs uppercase tracking-[0.2em] text-nimbus-700 mb-3 font-medium">
            {eyebrow}
          </p>
        )}
        {typeof title === 'string' ? (
          <h1 className="font-display font-medium text-display-xs md:text-display-sm text-ink-950 tracking-tightest">
            {title}
          </h1>
        ) : (
          title
        )}
      </div>

      {(description || action) && (
        <div className={`flex flex-col gap-4 ${isSplit ? 'md:items-end md:max-w-sm' : ''}`}>
          {description && (
            <p className="text-base text-nimbus-700 leading-relaxed">{description}</p>
          )}
          {action && <div>{action}</div>}
        </div>
      )}
    </header>
  );
}
