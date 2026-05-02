import React, { useEffect, useRef, useState, useCallback } from 'react';
import {
  Activity,
  CheckCircle2,
  XCircle,
  Loader2,
  Image,
  Video,
  X,
  ChevronDown,
  CalendarClock,
  Trash2,
  UserCircle2,
} from 'lucide-react';
import { listGenerations, cancelGeneration, dismissGeneration } from '../lib/lateApi';

const POLL_INTERVAL = 2500;

function statusIcon(status) {
  if (status === 'completed') return <CheckCircle2 size={16} className="text-emerald-400" />;
  if (status === 'failed') return <XCircle size={16} className="text-red-400" />;
  if (status === 'processing') return <Loader2 size={16} className="text-white animate-spin" />;
  return <Loader2 size={16} className="text-white/40" />;
}

function typeIcon(type) {
  if (type === 'carousel') return <Image size={14} className="text-nimbus-300" />;
  if (type === 'avatar') return <UserCircle2 size={14} className="text-nimbus-300" />;
  return <Video size={14} className="text-nimbus-200" />;
}

function timeSince(ts) {
  if (!ts) return '';
  const sec = Math.floor((Date.now() / 1000) - ts);
  if (sec < 60) return 'just now';
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
  return `${Math.floor(sec / 86400)}d ago`;
}

function hasActive(gens) {
  return gens.some((g) => g.status === 'queued' || g.status === 'processing');
}

export default function GenerationCenter({ onSchedule, refreshKey, focusKey }) {
  const [open, setOpen] = useState(false);
  const [generations, setGenerations] = useState([]);
  const [cancellingById, setCancellingById] = useState({});
  const [cancelErrorById, setCancelErrorById] = useState({});
  const [dismissingById, setDismissingById] = useState({});
  const [dismissErrorById, setDismissErrorById] = useState({});
  const pollRef = useRef(null);
  const panelRef = useRef(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const fetchGenerations = useCallback(async () => {
    try {
      const data = await listGenerations(30);
      const gens = data.generations || [];
      setGenerations(gens);
      return gens;
    } catch {
      return [];
    }
  }, []);

  const startPolling = useCallback(() => {
    stopPolling();
    pollRef.current = setInterval(async () => {
      const gens = await fetchGenerations();
      // Auto-stop when no more active jobs
      if (!hasActive(gens)) {
        stopPolling();
      }
    }, POLL_INTERVAL);
  }, [fetchGenerations, stopPolling]);

  // Initial fetch on mount
  useEffect(() => {
    (async () => {
      const gens = await fetchGenerations();
      if (hasActive(gens)) {
        startPolling();
      }
    })();
    return () => stopPolling();
  }, [fetchGenerations, startPolling, stopPolling]);

  // When refreshKey changes (e.g. after scheduling or a new submission),
  // re-fetch and restart polling if there are active jobs.
  useEffect(() => {
    if (refreshKey === undefined || refreshKey === 0) return;
    (async () => {
      const gens = await fetchGenerations();
      if (hasActive(gens)) {
        startPolling();
      }
    })();
  }, [refreshKey, fetchGenerations, startPolling]);

  // New run from Create (video): refetch, resume polling, open panel so the job is visible.
  useEffect(() => {
    if (focusKey === undefined || focusKey === 0) return;
    (async () => {
      const gens = await fetchGenerations();
      if (hasActive(gens)) {
        startPolling();
      }
      setOpen(true);
    })();
  }, [focusKey, fetchGenerations, startPolling]);

  // Close on outside click
  useEffect(() => {
    function handle(e) {
      if (panelRef.current && !panelRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, [open]);

  const activeCount = generations.filter(
    (g) => g.status === 'queued' || g.status === 'processing',
  ).length;
  const completedCount = generations.filter(
    (g) => g.status === 'completed' && !g.scheduled,
  ).length;

  const handleCancel = useCallback(async (generationId) => {
    setCancellingById((prev) => ({ ...prev, [generationId]: true }));
    setCancelErrorById((prev) => ({ ...prev, [generationId]: '' }));
    try {
      await cancelGeneration(generationId);
      const gens = await fetchGenerations();
      if (hasActive(gens)) {
        startPolling();
      } else {
        stopPolling();
      }
    } catch (err) {
      setCancelErrorById((prev) => ({
        ...prev,
        [generationId]: err?.message || 'Unable to cancel generation.',
      }));
    } finally {
      setCancellingById((prev) => ({ ...prev, [generationId]: false }));
    }
  }, [fetchGenerations, startPolling, stopPolling]);

  const handleDismiss = useCallback(async (generationId) => {
    setDismissingById((prev) => ({ ...prev, [generationId]: true }));
    setDismissErrorById((prev) => ({ ...prev, [generationId]: '' }));
    try {
      await dismissGeneration(generationId);
      await fetchGenerations();
    } catch (err) {
      setDismissErrorById((prev) => ({
        ...prev,
        [generationId]: err?.message || 'Could not dismiss.',
      }));
    } finally {
      setDismissingById((prev) => ({ ...prev, [generationId]: false }));
    }
  }, [fetchGenerations]);

  const hasCount = activeCount > 0 || completedCount > 0;
  const mobileCount = activeCount > 0 ? activeCount : completedCount;
  const mobileBadgeTone = activeCount > 0 ? 'bg-white text-ink-950' : 'bg-emerald-400 text-ink-950';

  return (
    <div ref={panelRef} className="fixed top-3 right-3 sm:top-5 sm:right-5 z-50">
      {/* Trigger pill (ink-frosted, matches the spectreAI primary CTA language) */}
      <button
        onClick={() => setOpen((p) => !p)}
        aria-expanded={open}
        aria-label="Generations"
        className="relative flex items-center gap-2 pl-2 pr-2 sm:pl-3 sm:pr-3 py-1.5 rounded-full glass-ink shadow-pill hover:-translate-y-0.5 transition-transform duration-200"
      >
        <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-white/15">
          {activeCount > 0 ? (
            <Loader2 size={14} className="text-white animate-spin" />
          ) : (
            <Activity size={14} className="text-white" />
          )}
        </span>

        {/* Desktop label */}
        <span className="hidden sm:inline text-sm font-medium tracking-tight text-white">
          {activeCount > 0 ? `${activeCount} running` : 'Generations'}
        </span>

        {/* Mobile-only count pill */}
        {hasCount && (
          <span
            className={`sm:hidden min-w-[20px] h-5 flex items-center justify-center rounded-full ${mobileBadgeTone} text-[11px] font-semibold px-1.5`}
          >
            {mobileCount}
          </span>
        )}

        {/* Desktop completed badge */}
        {completedCount > 0 && activeCount === 0 && (
          <span className="hidden sm:inline-flex ml-1 min-w-[20px] h-5 items-center justify-center rounded-full bg-emerald-400 text-ink-950 text-xs font-semibold px-1.5">
            {completedCount}
          </span>
        )}

        <ChevronDown
          size={14}
          className={`hidden sm:inline text-white/70 transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {/* Popover — CSS enter/exit (see .generation-center-popover in index.css) */}
      <div
        aria-hidden={!open}
        className={`generation-center-popover absolute right-0 mt-2 w-[calc(100vw-1.5rem)] sm:w-96 max-w-sm max-h-[70vh] rounded-3xl glass-ink shadow-pill overflow-hidden flex flex-col transform-gpu ${
          open ? 'generation-center-popover-open' : ''
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-white/10">
          <div>
            <p className="text-[10px] uppercase tracking-[0.22em] text-white/50 font-medium">
              Activity
            </p>
            <h3 className="font-display font-medium text-white text-base tracking-tight">
              Generation Center
            </h3>
          </div>
          <button
            onClick={() => setOpen(false)}
            className="p-1.5 rounded-full hover:bg-white/10 transition-colors"
          >
            <X size={14} className="text-white/70" />
          </button>
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto">
          {generations.length === 0 ? (
            <div className="px-5 py-10 text-center text-sm text-white/60">
              No generation jobs yet. Start one from Create or Carousel Studio.
            </div>
          ) : (
            <div className="divide-y divide-white/10">
              {generations.map((gen) => (
                <GenerationRow
                  key={gen.generationId}
                  gen={gen}
                  onSchedule={onSchedule}
                  onCancel={handleCancel}
                  onDismiss={handleDismiss}
                  isCancelling={Boolean(cancellingById[gen.generationId])}
                  cancelError={cancelErrorById[gen.generationId]}
                  isDismissing={Boolean(dismissingById[gen.generationId])}
                  dismissError={dismissErrorById[gen.generationId]}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}


function GenerationRow({
  gen,
  onSchedule,
  onCancel,
  onDismiss,
  isCancelling,
  cancelError,
  isDismissing,
  dismissError,
}) {
  const isActive = gen.status === 'queued' || gen.status === 'processing';
  const isCompleted = gen.status === 'completed';
  const isFailed = gen.status === 'failed';
  const isScheduled = isCompleted && gen.scheduled;
  const canDismiss = isCompleted || isFailed;

  return (
    <div className="px-4 py-3 hover:bg-white/5 transition-colors">
      <div className="flex items-start gap-3">
        {/* Type + Status icon */}
        <div className="flex flex-col items-center gap-1 pt-0.5">
          {typeIcon(gen.type)}
          {statusIcon(gen.status)}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0 flex-1">
              <p className="text-sm font-medium text-white truncate tracking-tight">
                {gen.label || gen.type}
              </p>
              <span className="text-[10px] text-white/40 flex-shrink-0">
                {timeSince(gen.createdAt)}
              </span>
            </div>
            {canDismiss && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onDismiss && onDismiss(gen.generationId);
                }}
                disabled={isDismissing}
                title="Dismiss from list"
                aria-label="Dismiss from list"
                className="flex-shrink-0 p-1.5 rounded-lg text-white/50 hover:text-white hover:bg-white/10 disabled:opacity-50 transition-colors"
              >
                {isDismissing ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <Trash2 size={14} strokeWidth={2} />
                )}
              </button>
            )}
          </div>

          {/* Progress bar for active jobs */}
          {isActive && (
            <div className="mt-1.5">
              <div className="w-full h-1 bg-white/10 rounded-full overflow-hidden">
                <div
                  className="h-full bg-white rounded-full transition-all duration-500"
                  style={{ width: `${gen.progress || 0}%` }}
                />
              </div>
              <p className="text-[11px] text-white/50 mt-1">
                {gen.currentStep
                  ? `${gen.currentStep} — ${gen.progress || 0}%`
                  : 'Queued...'}
              </p>
            </div>
          )}

          {/* Error for failed */}
          {isFailed && (
            <p className="text-[11px] text-red-300 mt-1 line-clamp-2">{gen.error}</p>
          )}

          {dismissError && (
            <p className="text-[11px] text-red-300 mt-1 line-clamp-2">{dismissError}</p>
          )}

          {isActive && (
            <div className="mt-2">
              <button
                onClick={() => onCancel && onCancel(gen.generationId)}
                disabled={isCancelling}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-red-500/15 text-red-200 hover:bg-red-500/25 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
              >
                {isCancelling ? <Loader2 size={12} className="animate-spin" /> : <XCircle size={12} />}
                {isCancelling ? 'Cancelling...' : 'Cancel'}
              </button>
              {cancelError && (
                <p className="text-[11px] text-red-300 mt-1 line-clamp-2">{cancelError}</p>
              )}
            </div>
          )}

          {/* Completed: scheduled indicator OR schedule button (avatar jobs are not schedulable) */}
          {isCompleted && gen.type !== 'avatar' && (
            <div className="mt-2 flex items-center gap-2">
              {isScheduled && (
                <span className="inline-flex items-center gap-1 text-xs text-emerald-300 font-medium">
                  <CheckCircle2 size={13} />
                  Scheduled
                </span>
              )}
              <button
                onClick={() => onSchedule && onSchedule(gen)}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium tracking-tight transition-colors ${
                  isScheduled
                    ? 'bg-white/10 text-white/70 hover:bg-white/20'
                    : 'bg-white text-ink-950 hover:bg-white/90'
                }`}
              >
                <CalendarClock size={12} />
                {isScheduled ? 'Reschedule' : 'Schedule'}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
