import React from 'react';

const SIZE_CLASS = {
  sm: 'text-lg',
  md: 'text-2xl',
  lg: 'text-3xl',
  xl: 'text-4xl',
};

export default function Wordmark({ className = '', size = 'md', light = false }) {
  return (
    <span
      className={`font-display font-medium tracking-tightest lowercase ${SIZE_CLASS[size] || SIZE_CLASS.md} ${
        light ? 'text-white' : 'text-ink-950'
      } ${className}`}
    >
      lumeet
    </span>
  );
}
