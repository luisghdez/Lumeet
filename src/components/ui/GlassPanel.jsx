import React from 'react';

const TONE_CLASS = {
  light: 'glass-card',
  pane: 'glass-pane',
  ink: 'glass-ink',
};

export default function GlassPanel({
  children,
  className = '',
  tone = 'light',
  rounded = 'rounded-3xl',
  as: Tag = 'div',
}) {
  const surface = TONE_CLASS[tone] || TONE_CLASS.light;
  return <Tag className={`${surface} ${rounded} shadow-card ${className}`}>{children}</Tag>;
}
