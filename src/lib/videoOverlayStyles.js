export const OVERLAY_STYLE_PRESETS = [
  { id: 'classic', label: 'Classic' },
  { id: 'bold', label: 'Bold' },
  { id: 'background', label: 'Background' },
  { id: 'minimal', label: 'Minimal' },
];

export const OVERLAY_FONT_SIZE_OPTIONS = [
  { id: 'small', label: 'S', value: 36 },
  { id: 'medium', label: 'M', value: 48 },
  { id: 'large', label: 'L', value: 60 },
];

export const OVERLAY_FONT_COLORS = [
  { id: 'white', label: 'White', value: '#FFFFFF' },
  { id: 'yellow', label: 'Yellow', value: '#FFE135' },
  { id: 'pink', label: 'Pink', value: '#FF0050' },
  { id: 'cyan', label: 'Cyan', value: '#00F2EA' },
];

export const DEFAULT_OVERLAY = {
  enabled: true,
  text: '',
  fontSize: 48,
  fontColor: '#FFFFFF',
  style: 'classic',
  verticalPosition: 0.55,
};

export function normalizeFontSize(value) {
  if (typeof value === 'string') {
    const match = OVERLAY_FONT_SIZE_OPTIONS.find((item) => item.id === value.toLowerCase());
    if (match) return match.value;
    const parsed = Number.parseInt(value, 10);
    if (Number.isFinite(parsed)) return Math.max(24, Math.min(72, parsed));
  }
  const parsed = Number.parseInt(value ?? DEFAULT_OVERLAY.fontSize, 10);
  return Number.isFinite(parsed) ? Math.max(24, Math.min(72, parsed)) : DEFAULT_OVERLAY.fontSize;
}

export function normalizeFontColor(value) {
  const raw = String(value || DEFAULT_OVERLAY.fontColor).trim();
  const match = OVERLAY_FONT_COLORS.find((item) => item.id === raw.toLowerCase() || item.value === raw.toUpperCase());
  if (match) return match.value;
  if (/^#[0-9A-Fa-f]{3}$/.test(raw) || /^#[0-9A-Fa-f]{6}$/.test(raw)) return raw.toUpperCase();
  return DEFAULT_OVERLAY.fontColor;
}

export function normalizeOverlaySpec(raw) {
  const payload = raw && typeof raw === 'object' ? raw : {};
  const text = String(payload.text || '').trim();
  const enabled = payload.enabled !== false && Boolean(text);
  return {
    enabled,
    text,
    fontSize: normalizeFontSize(payload.fontSize),
    fontColor: normalizeFontColor(payload.fontColor),
    style: OVERLAY_STYLE_PRESETS.some((item) => item.id === payload.style) ? payload.style : DEFAULT_OVERLAY.style,
    verticalPosition: Number(payload.verticalPosition ?? DEFAULT_OVERLAY.verticalPosition),
  };
}

export function overlaySpecsEqual(a, b) {
  const left = normalizeOverlaySpec(a);
  const right = normalizeOverlaySpec(b);
  return (
    left.enabled === right.enabled
    && left.text === right.text
    && left.fontSize === right.fontSize
    && left.fontColor === right.fontColor
    && left.style === right.style
  );
}

export function mediaUrlWithVersion(url, version) {
  if (!url) return '';
  if (!version) return url;
  const [base, query = ''] = url.split('?');
  const params = new URLSearchParams(query);
  params.set('v', String(version));
  return `${base}?${params.toString()}`;
}

export function overlayPreviewStyle(spec, scale = 1) {
  const normalized = normalizeOverlaySpec(spec);
  const fontSize = Math.max(10, Math.round(normalized.fontSize * scale));
  const base = {
    color: normalized.fontColor,
    fontSize: `${fontSize}px`,
    lineHeight: 1.35,
    fontWeight: 700,
    fontFamily: '"Arial Black", "Helvetica Neue", Arial, sans-serif',
    textAlign: 'center',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
    maxWidth: '88%',
  };

  if (normalized.style === 'bold') {
    return {
      ...base,
      textShadow: `
        -2px -2px 0 #000,
        2px -2px 0 #000,
        -2px 2px 0 #000,
        2px 2px 0 #000,
        0 0 4px rgba(0,0,0,0.9)
      `,
    };
  }

  if (normalized.style === 'background') {
    return {
      ...base,
      background: 'rgba(0, 0, 0, 0.66)',
      borderRadius: '12px',
      padding: '8px 14px',
    };
  }

  if (normalized.style === 'minimal') {
    return {
      ...base,
      textShadow: '0 1px 3px rgba(0,0,0,0.65)',
    };
  }

  return {
    ...base,
    textShadow: `
      -1px -1px 0 #000,
      1px -1px 0 #000,
      -1px 1px 0 #000,
      1px 1px 0 #000
    `,
  };
}

export function fontSizeOptionId(value) {
  const normalized = normalizeFontSize(value);
  const match = OVERLAY_FONT_SIZE_OPTIONS.find((item) => item.value === normalized);
  return match?.id || 'medium';
}

export function fontColorOptionId(value) {
  const normalized = normalizeFontColor(value);
  const match = OVERLAY_FONT_COLORS.find((item) => item.value === normalized);
  return match?.id || 'white';
}
