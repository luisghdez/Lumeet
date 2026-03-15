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
} from 'lucide-react';
import { listGenerations, getGeneration } from '../lib/lateApi';

const POLL_INTERVAL = 2500;

function statusIcon(status) {
  if (status === 'completed') return <CheckCircle2 size={16} className="text-green-500" />;
  if (status === 'failed') return <XCircle size={16} className="text-red-500" />;
  if (status === 'processing') return <Loader2 size={16} className="text-purple-600 animate-spin" />;
  return <Loader2 size={16} className="text-gray-400" />;
}

function typeIcon(type) {
  if (type === 'carousel') return <Image size={14} className="text-pink-500" />;
  return <Video size={14} className="text-indigo-500" />;
}

function timeSince(ts) {
  if (!ts) return '';
  const sec = Math.floor((Date.now() / 1000) - ts);
  if (sec < 60) return 'just now';
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
  return `${Math.floor(sec / 86400)}d ago`;
}

export default function GenerationCenter({ onSchedule }) {
  const [open, setOpen] = useState(false);
  const [generations, setGenerations] = useState([]);
  const pollRef = useRef(null);
  const panelRef = useRef(null);

  const fetchGenerations = useCallback(async () => {
    try {
      const data = await listGenerations(30);
      setGenerations(data.generations || []);
    } catch {
      // silently ignore
    }
  }, []);

  // Start polling when mounted
  useEffect(() => {
    fetchGenerations();
    pollRef.current = setInterval(fetchGenerations, POLL_INTERVAL);
    return () => clearInterval(pollRef.current);
  }, [fetchGenerations]);

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
  const completedCount = generations.filter((g) => g.status === 'completed').length;

  return (
    <div ref={panelRef} className="fixed top-5 right-5 z-50">
      {/* Trigger button */}
      <button
        onClick={() => setOpen((p) => !p)}
        className="relative flex items-center gap-2 px-3.5 py-2 rounded-2xl glass-card border border-white/40 shadow-lg hover:shadow-xl transition-all duration-200"
      >
        {activeCount > 0 ? (
          <Loader2 size={18} className="text-purple-600 animate-spin" />
        ) : (
          <Activity size={18} className="text-purple-600" />
        )}
        <span className="text-sm font-semibold text-gray-800">
          {activeCount > 0 ? `${activeCount} running` : 'Generations'}
        </span>
        {completedCount > 0 && activeCount === 0 && (
          <span className="ml-1 min-w-[20px] h-5 flex items-center justify-center rounded-full bg-green-500 text-white text-xs font-bold px-1.5">
            {completedCount}
          </span>
        )}
        <ChevronDown
          size={14}
          className={`text-gray-500 transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {/* Popover panel */}
      {open && (
        <div className="absolute right-0 mt-2 w-96 max-h-[70vh] rounded-2xl glass-heavy border border-white/40 shadow-2xl overflow-hidden flex flex-col animate-in fade-in slide-in-from-top-2">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-white/20">
            <h3 className="font-bold text-gray-900 text-sm">Generation Center</h3>
            <button
              onClick={() => setOpen(false)}
              className="p-1 rounded-lg hover:bg-gray-100 transition-colors"
            >
              <X size={14} className="text-gray-500" />
            </button>
          </div>

          {/* List */}
          <div className="flex-1 overflow-y-auto">
            {generations.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-gray-500">
                No generation jobs yet. Start one from Create or Carousel Studio.
              </div>
            ) : (
              <div className="divide-y divide-white/10">
                {generations.map((gen) => (
                  <GenerationRow
                    key={gen.generationId}
                    gen={gen}
                    onSchedule={onSchedule}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}


function GenerationRow({ gen, onSchedule }) {
  const isActive = gen.status === 'queued' || gen.status === 'processing';
  const isCompleted = gen.status === 'completed';
  const isFailed = gen.status === 'failed';

  return (
    <div className="px-4 py-3 hover:bg-white/30 transition-colors">
      <div className="flex items-start gap-3">
        {/* Type + Status icon */}
        <div className="flex flex-col items-center gap-1 pt-0.5">
          {typeIcon(gen.type)}
          {statusIcon(gen.status)}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="text-sm font-semibold text-gray-900 truncate">{gen.label || gen.type}</p>
            <span className="text-[10px] text-gray-400 flex-shrink-0">
              {timeSince(gen.createdAt)}
            </span>
          </div>

          {/* Progress bar for active jobs */}
          {isActive && (
            <div className="mt-1.5">
              <div className="w-full h-1.5 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-purple-500 to-purple-600 rounded-full transition-all duration-500"
                  style={{ width: `${gen.progress || 0}%` }}
                />
              </div>
              <p className="text-[11px] text-gray-500 mt-1">
                {gen.currentStep
                  ? `${gen.currentStep} — ${gen.progress || 0}%`
                  : 'Queued...'}
              </p>
            </div>
          )}

          {/* Error for failed */}
          {isFailed && (
            <p className="text-[11px] text-red-500 mt-1 line-clamp-2">{gen.error}</p>
          )}

          {/* Schedule button for completed */}
          {isCompleted && (
            <button
              onClick={() => onSchedule && onSchedule(gen)}
              className="mt-1.5 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gradient-to-r from-purple-600 to-purple-500 text-white text-xs font-semibold hover:from-purple-700 hover:to-purple-600 transition-all"
            >
              <CalendarClock size={12} />
              Schedule
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
