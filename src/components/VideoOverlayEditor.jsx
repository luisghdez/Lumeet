import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Loader2, RotateCcw, Save, Type, X } from 'lucide-react';
import {
  getAccountPlanPostOverlay,
  renderAccountPlanPostOverlay,
  revertAccountPlanPostOverlay,
} from '../lib/organizerApi';
import {
  DEFAULT_OVERLAY,
  OVERLAY_FONT_COLORS,
  OVERLAY_FONT_SIZE_OPTIONS,
  OVERLAY_STYLE_PRESETS,
  fontColorOptionId,
  fontSizeOptionId,
  normalizeOverlaySpec,
  overlayPreviewStyle,
  overlaySpecsEqual,
} from '../lib/videoOverlayStyles';

function OverlayPreview({ videoUrl, overlay, scale = 0.42, showOverlay = true }) {
  const videoRef = useRef(null);
  const normalized = normalizeOverlaySpec(overlay);
  const shouldRenderOverlay = showOverlay && normalized.enabled && normalized.text && videoUrl;

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return undefined;
    const prime = () => {
      try {
        video.pause();
        video.currentTime = 0;
      } catch {
        // Ignore seek failures for signed URLs.
      }
    };
    video.addEventListener('loadeddata', prime);
    video.addEventListener('loadedmetadata', prime);
    return () => {
      video.removeEventListener('loadeddata', prime);
      video.removeEventListener('loadedmetadata', prime);
    };
  }, [videoUrl]);

  return (
    <div className="relative mx-auto aspect-[9/16] w-full max-w-[16rem] overflow-hidden rounded-2xl bg-black">
      {videoUrl ? (
        <video
          ref={videoRef}
          src={videoUrl}
          className="h-full w-full object-cover"
          playsInline
          preload="metadata"
          muted
          loop
          controlsList="nofullscreen nodownload noremoteplayback"
          disablePictureInPicture
        />
      ) : (
        <div className="flex h-full w-full items-center justify-center text-sm text-white/40">
          Preview unavailable
        </div>
      )}
      {shouldRenderOverlay && (
        <div
          className="pointer-events-none absolute inset-x-0 flex justify-center px-3"
          style={{ top: `${normalized.verticalPosition * 100}%`, transform: 'translateY(-50%)' }}
        >
          <div style={overlayPreviewStyle(normalized, scale)}>
            {normalized.text}
          </div>
        </div>
      )}
    </div>
  );
}

export default function VideoOverlayEditor({
  planId,
  slot,
  onClose,
  onSaved,
}) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [reverting, setReverting] = useState(false);
  const [error, setError] = useState('');
  const [savedOverlay, setSavedOverlay] = useState(DEFAULT_OVERLAY);
  const [originalOverlay, setOriginalOverlay] = useState(DEFAULT_OVERLAY);
  const [draft, setDraft] = useState(DEFAULT_OVERLAY);
  const [rawVideoAvailable, setRawVideoAvailable] = useState(false);
  const [rawVideoUrl, setRawVideoUrl] = useState('');

  useEffect(() => {
    let cancelled = false;
    async function loadOverlay() {
      setLoading(true);
      setError('');
      try {
        const result = await getAccountPlanPostOverlay({ planId, slot });
        if (cancelled) return;
        const current = normalizeOverlaySpec(result.videoOverlay || DEFAULT_OVERLAY);
        const original = normalizeOverlaySpec(result.videoOverlayOriginal || current);
        setSavedOverlay(current);
        setOriginalOverlay(original);
        setDraft(current);
        setRawVideoAvailable(Boolean(result.rawVideoAvailable));
        setRawVideoUrl(result.rawVideoUrl || '');
      } catch (err) {
        if (!cancelled) setError(err.message || 'Could not load overlay settings.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    loadOverlay();
    return () => {
      cancelled = true;
    };
  }, [planId, slot]);

  useEffect(() => {
    const onKey = (event) => {
      if (event.key === 'Escape' && !saving && !reverting) onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose, saving, reverting]);

  const dirty = useMemo(
    () => !overlaySpecsEqual(draft, savedOverlay),
    [draft, savedOverlay],
  );
  const differsFromOriginal = useMemo(
    () => !overlaySpecsEqual(savedOverlay, originalOverlay),
    [savedOverlay, originalOverlay],
  );

  const updateDraft = (updates) => {
    setDraft((current) => normalizeOverlaySpec({ ...current, ...updates }));
  };

  const handleToggleDelete = () => {
    if (draft.enabled) {
      updateDraft({ enabled: false });
      return;
    }
    updateDraft({ enabled: true, text: savedOverlay.text || originalOverlay.text || '' });
  };

  const handleSave = async () => {
    setSaving(true);
    setError('');
    try {
      const plan = await renderAccountPlanPostOverlay({ planId, slot, overlay: draft });
      const post = (plan.plannedPosts || []).find((item) => Number(item.slot) === Number(slot));
      const next = normalizeOverlaySpec(post?.videoOverlay || draft);
      setSavedOverlay(next);
      setDraft(next);
      onSaved(plan);
      onClose();
    } catch (err) {
      setError(err.message || 'Could not save overlay changes.');
    } finally {
      setSaving(false);
    }
  };

  const handleRevert = async () => {
    setReverting(true);
    setError('');
    try {
      const plan = await revertAccountPlanPostOverlay({ planId, slot });
      const post = (plan.plannedPosts || []).find((item) => Number(item.slot) === Number(slot));
      const next = normalizeOverlaySpec(post?.videoOverlay || originalOverlay);
      const original = normalizeOverlaySpec(post?.videoOverlayOriginal || next);
      setSavedOverlay(next);
      setOriginalOverlay(original);
      setDraft(next);
      onSaved(plan);
    } catch (err) {
      setError(err.message || 'Could not revert overlay changes.');
    } finally {
      setReverting(false);
    }
  };

  const busy = saving || reverting;

  return (
    <div
      className="fixed inset-0 z-[110] flex items-center justify-center p-4 sm:p-6"
      onClick={busy ? undefined : onClose}
    >
      <div className="absolute inset-0 bg-ink-950/55 backdrop-blur-[2px]" aria-hidden />
      <div
        className="relative flex max-h-[92vh] w-full max-w-4xl flex-col overflow-hidden rounded-3xl border border-white/10 bg-ink-950 shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
          <div>
            <p className="inline-flex items-center gap-2 text-sm font-semibold text-white">
              <Type size={16} aria-hidden />
              Edit on-screen text
            </p>
            <p className="mt-1 text-xs text-white/45">Slot {slot} · changes re-render the final video</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="rounded-full bg-white/10 p-2 text-white/70 transition hover:bg-white/20 hover:text-white disabled:opacity-40"
            aria-label="Close editor"
          >
            <X size={16} aria-hidden />
          </button>
        </div>

        {loading ? (
          <div className="flex flex-1 items-center justify-center px-6 py-16 text-sm text-white/50">
            <Loader2 size={18} className="mr-2 animate-spin" aria-hidden />
            Loading overlay settings...
          </div>
        ) : (
          <>
            <div className="grid flex-1 gap-5 overflow-y-auto px-5 py-5 md:grid-cols-[minmax(0,16rem)_minmax(0,1fr)]">
              <div>
                <p className="mb-3 text-xs font-semibold uppercase tracking-[0.14em] text-white/35">Preview</p>
                <OverlayPreview
                  videoUrl={rawVideoUrl}
                  overlay={draft}
                  showOverlay={rawVideoAvailable}
                />
                {!rawVideoAvailable && (
                  <p className="mt-3 rounded-2xl bg-amber-400/10 px-3 py-2 text-xs text-amber-100">
                    Captionless source video is unavailable, so the live preview cannot show editable text without duplicating the burned-in caption.
                  </p>
                )}
              </div>

              <div className="grid gap-4">
                <label className="grid gap-1 text-xs text-white/40">
                  On-screen text
                  <textarea
                    value={draft.text}
                    rows={4}
                    disabled={busy || !draft.enabled}
                    onChange={(event) => updateDraft({ text: event.target.value, enabled: true })}
                    className="resize-none rounded-2xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-white outline-none disabled:opacity-50"
                    placeholder="Enter the text that appears on the video"
                  />
                </label>

                <label className="inline-flex items-center gap-2 text-sm text-white/70">
                  <input
                    type="checkbox"
                    checked={!draft.enabled}
                    disabled={busy}
                    onChange={handleToggleDelete}
                    className="rounded border-white/20 bg-black/20"
                  />
                  Remove on-screen text
                </label>

                <div className="grid gap-2">
                  <p className="text-xs text-white/40">Font size</p>
                  <div className="flex flex-wrap gap-2">
                    {OVERLAY_FONT_SIZE_OPTIONS.map((option) => {
                      const selected = fontSizeOptionId(draft.fontSize) === option.id;
                      return (
                        <button
                          key={option.id}
                          type="button"
                          disabled={busy || !draft.enabled}
                          onClick={() => updateDraft({ fontSize: option.value })}
                          className={`rounded-full px-3 py-1.5 text-xs font-semibold transition ${
                            selected ? 'bg-white text-ink-950' : 'bg-white/10 text-white/60 hover:bg-white/15'
                          } disabled:opacity-40`}
                        >
                          {option.label}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div className="grid gap-2">
                  <p className="text-xs text-white/40">Font color</p>
                  <div className="flex flex-wrap gap-2">
                    {OVERLAY_FONT_COLORS.map((option) => {
                      const selected = fontColorOptionId(draft.fontColor) === option.id;
                      return (
                        <button
                          key={option.id}
                          type="button"
                          disabled={busy || !draft.enabled}
                          onClick={() => updateDraft({ fontColor: option.value })}
                          className={`inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-semibold transition ${
                            selected ? 'bg-white text-ink-950' : 'bg-white/10 text-white/60 hover:bg-white/15'
                          } disabled:opacity-40`}
                        >
                          <span
                            className="h-3 w-3 rounded-full border border-white/20"
                            style={{ backgroundColor: option.value }}
                            aria-hidden
                          />
                          {option.label}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div className="grid gap-2">
                  <p className="text-xs text-white/40">Style</p>
                  <div className="flex flex-wrap gap-2">
                    {OVERLAY_STYLE_PRESETS.map((option) => {
                      const selected = draft.style === option.id;
                      return (
                        <button
                          key={option.id}
                          type="button"
                          disabled={busy || !draft.enabled}
                          onClick={() => updateDraft({ style: option.id })}
                          className={`rounded-full px-3 py-1.5 text-xs font-semibold transition ${
                            selected ? 'bg-cyan-300 text-ink-950' : 'bg-white/10 text-white/60 hover:bg-white/15'
                          } disabled:opacity-40`}
                        >
                          {option.label}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>

            <div className="border-t border-white/10 px-5 py-4">
              {error && (
                <p className="mb-3 rounded-2xl bg-red-400/10 px-3 py-2 text-xs text-red-100">{error}</p>
              )}
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-xs text-white/40">
                  {dirty ? 'Unsaved changes' : differsFromOriginal ? 'Saved, different from original' : 'Matches saved version'}
                </p>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={handleRevert}
                    disabled={busy || (!differsFromOriginal && !dirty)}
                    className="inline-flex items-center gap-2 rounded-2xl bg-white/10 px-4 py-2 text-xs font-semibold text-white/70 hover:bg-white/15 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {reverting ? <Loader2 size={14} className="animate-spin" aria-hidden /> : <RotateCcw size={14} aria-hidden />}
                    Revert to original
                  </button>
                  <button
                    type="button"
                    onClick={handleSave}
                    disabled={busy || !dirty || !rawVideoAvailable}
                    className="inline-flex items-center gap-2 rounded-2xl bg-emerald-300 px-4 py-2 text-xs font-semibold text-ink-950 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {saving ? <Loader2 size={14} className="animate-spin" aria-hidden /> : <Save size={14} aria-hidden />}
                    Save changes
                  </button>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
