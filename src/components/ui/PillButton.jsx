import React from 'react';
import { ArrowRight } from 'lucide-react';

const VARIANT_CLASS = {
  primary: 'btn-primary',
  secondary: 'btn-secondary',
  ghost: 'btn-ghost',
};

export default function PillButton({
  variant = 'primary',
  arrow = true,
  icon: Icon,
  iconRight,
  className = '',
  children,
  as: Tag = 'button',
  ...rest
}) {
  const base = VARIANT_CLASS[variant] || VARIANT_CLASS.primary;
  const showArrow = arrow && variant !== 'ghost';

  return (
    <Tag className={`${base} ${className}`} {...rest}>
      {Icon && <Icon size={16} className="-ml-1" />}
      <span>{children}</span>
      {showArrow && (
        <span className="arrow-chip">
          {iconRight ? React.createElement(iconRight, { size: 14, strokeWidth: 2.25 }) : (
            <ArrowRight size={14} strokeWidth={2.25} />
          )}
        </span>
      )}
    </Tag>
  );
}
