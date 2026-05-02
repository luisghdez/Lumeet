import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  Film,
  Music,
  Loader2,
  CheckCircle2,
  Circle,
  XCircle,
  ArrowLeft,
  Download,
  X,
  Type,
  Play,
  Volume2,
  Plus,
  Trash2,
} from 'lucide-react';
import ScheduleToSocial from './ScheduleToSocial';
import { startRemix, getGeneration, deleteHook } from '../lib/lateApi';
import { useHooks, useSounds } from '../lib/mediaLibrary';

const POLL_INTERVAL = 2000;

// ---------- Hook Picker ----------

function HookPicker({ hooks, selectedHookId, onSelect, onDelete, loading }) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 size={24} className="text-purple-500 animate-spin" />
        <span className="ml-2 text-sm text-gray-500">Loading hooks…</span>
      </div>
    );
  }

  if (!hooks.length) {
    return (
      <div className="text-center py-12 text-gray-500">
        <Film size={32} className="mx-auto mb-3 text-gray-300" />
        <p className="text-sm font-medium">No hooks saved yet</p>
        <p className="text-xs mt-1">Generate a video first to create hooks</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3 max-h-72 overflow-y-auto pr-1">
      {hooks.map((hook) => {
        const isSelected = hook.hookId === selectedHookId;
        return (
          <div key={hook.hookId} className="relative group">
            <button
              type="button"
              onClick={() => onSelect(hook.hookId)}
              className={`relative rounded-xl overflow-hidden border-2 transition-all duration-200 aspect-[9/16] w-full shadow-[inset_0_1px_0_0_rgba(255,255,255,0.2)]
                ${isSelected
                  ? 'border-nimbus-600 ring-2 ring-white/65 shadow-lg'
                  : 'border-nimbus-400/40 hover:border-nimbus-500/48'}`}
            >
              <video
                src={hook.url}
                muted
                playsInline
                preload="metadata"
                className="w-full h-full object-cover"
                onMouseOver={(e) => e.target.play()}
                onMouseOut={(e) => { e.target.pause(); e.target.currentTime = 0; }}
              />
              {isSelected && (
                <div className="absolute top-1.5 right-1.5 bg-purple-500 rounded-full p-0.5">
                  <CheckCircle2 size={14} className="text-white" />
                </div>
              )}
              <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent px-2 py-1.5">
                <p className="text-[10px] text-white truncate font-medium">
                  {hook.label || hook.hookId.slice(0, 8)}
                </p>
              </div>
            </button>
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onDelete(hook.hookId); }}
              className="absolute top-1.5 left-1.5 bg-red-500 text-white rounded-full p-1 shadow transition-colors hover:bg-red-600 focus:outline-none focus:ring-2 focus:ring-white/80"
              title="Delete hook"
              aria-label={`Delete hook ${hook.label || hook.hookId}`}
            >
              <Trash2 size={12} />
            </button>
          </div>
        );
      })}
    </div>
  );
}

// ---------- Sound Selector ----------

function SoundSelector({ sounds, selectedSoundId, originalSoundId, onSelect, loading }) {
  const audioRefs = useRef({});
  const [playingId, setPlayingId] = useState(null);

  // Preload all sound URLs into Audio objects on mount / when sounds change
  useEffect(() => {
    const refs = audioRefs.current;
    sounds.forEach((s) => {
      if (s.url && !refs[s.soundId]) {
        const audio = new Audio(s.url);
        audio.preload = 'auto';
        audio.addEventListener('ended', () => setPlayingId(null));
        refs[s.soundId] = audio;
      }
    });
    // Cleanup on unmount
    return () => {
      Object.values(refs).forEach((a) => { a.pause(); a.src = ''; });
      audioRefs.current = {};
    };
  }, [sounds]);

  const togglePreview = useCallback((id) => {
    const refs = audioRefs.current;
    // Stop whatever is currently playing
    if (playingId && refs[playingId]) {
      refs[playingId].pause();
      refs[playingId].currentTime = 0;
    }
    if (playingId === id) {
      // Was playing this one → just stop
      setPlayingId(null);
      return;
    }
    // Play the new one
    if (refs[id]) {
      refs[id].currentTime = 0;
      refs[id].play().catch(() => {});
      setPlayingId(id);
    }
  }, [playingId]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-4">
        <Loader2 size={16} className="text-purple-500 animate-spin" />
        <span className="text-sm text-gray-500">Loading sounds…</span>
      </div>
    );
  }

  const options = [
    { id: '__none__', label: 'No sound', icon: <X size={14} /> },
    ...sounds.map((s) => ({
      id: s.soundId,
      label: s.label || `Sound ${s.soundId.replace('snd_', '').slice(0, 6)}`,
      duration: s.durationSec,
      isOriginal: s.soundId === originalSoundId,
      url: s.url,
    })),
  ];

  return (
    <div className="flex flex-wrap gap-2 max-h-36 overflow-y-auto">
      {options.map((opt) => {
        const isSelected = opt.id === selectedSoundId;
        const isPlaying = playingId === opt.id;
        return (
          <div key={opt.id} className="inline-flex items-center gap-0">
            <button
              type="button"
              onClick={() => onSelect(opt.id)}
              className={`inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium border-2 transition-all duration-200 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.35)]
                ${opt.url ? 'rounded-l-xl border-r-0' : 'rounded-xl'}
                ${isSelected
                  ? 'border-nimbus-500/45 bg-white/45 text-nimbus-900'
                  : 'border-nimbus-400/38 bg-white/40 text-nimbus-800 hover:border-nimbus-500/45'}`}
            >
              {opt.icon || <Volume2 size={14} />}
              <span className="truncate max-w-[120px]">{opt.label}</span>
              {opt.isOriginal && (
                <span className="bg-purple-200 text-purple-700 text-[9px] px-1.5 py-0.5 rounded-full font-bold">
                  ORIGINAL
                </span>
              )}
              {opt.duration && (
                <span className="text-gray-400">{opt.duration.toFixed(1)}s</span>
              )}
            </button>
            {opt.url && (
              <button
                type="button"
                onClick={() => togglePreview(opt.id)}
                title={isPlaying ? 'Stop preview' : 'Preview sound'}
                className={`inline-flex items-center justify-center w-8 h-full py-2 rounded-r-xl border-2 border-l-0 transition-all duration-200 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.35)]
                  ${isSelected
                    ? 'border-nimbus-500/45 bg-white/45 text-nimbus-900 hover:bg-white/55'
                    : 'border-nimbus-400/38 bg-white/40 text-nimbus-600 hover:text-nimbus-900 hover:border-nimbus-500/45'}`}
              >
                {isPlaying ? <Volume2 size={13} className="animate-pulse" /> : <Play size={13} />}
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ---------- Step Progress Item ----------

function StepItem({ step, index }) {
  const statusIcon = {
    pending: <Circle size={18} className="text-gray-300" />,
    running: <Loader2 size={18} className="text-purple-600 animate-spin" />,
    completed: <CheckCircle2 size={18} className="text-green-500" />,
    failed: <XCircle size={18} className="text-red-500" />,
  };

  return (
    <div
      className="flex items-center gap-3 py-3 px-4 rounded-xl transition-colors duration-200"
      style={{
        opacity: 0,
        animation: `slideDownFade 0.4s ease-out ${index * 100}ms forwards`,
      }}
    >
      {statusIcon[step.status] || statusIcon.pending}
      <div className="flex-1">
        <p className={`text-sm font-medium ${step.status === 'running' ? 'text-purple-700' : step.status === 'completed' ? 'text-gray-700' : 'text-gray-500'}`}>
          {step.label}
        </p>
        {step.message && step.status !== 'pending' && (
          <p className="text-xs text-gray-500 mt-0.5">{step.message}</p>
        )}
      </div>
    </div>
  );
}

// ---------- Drop Zone for Extension Video ----------

function ExtensionDropZone({ file, onFileSelect }) {
  const inputRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);
  const [preview, setPreview] = useState(null);

  useEffect(() => {
    if (file) {
      const url = URL.createObjectURL(file);
      setPreview(url);
      return () => URL.revokeObjectURL(url);
    }
    setPreview(null);
  }, [file]);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) onFileSelect(dropped);
  }, [onFileSelect]);

  return (
    <div
      className={`relative flex flex-col items-center justify-center rounded-2xl border-2 transition-all duration-200 cursor-pointer shadow-[inset_0_1px_0_0_rgba(255,255,255,0.35)]
        ${
          isDragging
            ? 'border-dashed border-nimbus-600/45 bg-white/28'
            : file
              ? 'border-solid border-nimbus-500/40 bg-white/25'
              : 'border-dashed border-nimbus-400/45 bg-white/15 hover:border-nimbus-500/50 hover:bg-white/22'
        }
        ${file ? 'p-3' : 'p-6'}`}
      onClick={() => inputRef.current?.click()}
      onDrop={handleDrop}
      onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
      onDragLeave={() => setIsDragging(false)}
    >
      <input
        ref={inputRef}
        type="file"
        accept="video/*"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files[0];
          if (f) onFileSelect(f);
        }}
      />
      {file ? (
        <div className="flex items-center gap-3 w-full">
          {preview ? (
            <div className="w-14 h-14 rounded-lg overflow-hidden flex-shrink-0 bg-black/10">
              <video src={preview} className="w-full h-full object-cover" muted />
            </div>
          ) : (
            <div className="w-14 h-14 rounded-lg bg-purple-100 flex items-center justify-center flex-shrink-0">
              <Film size={20} className="text-purple-600" />
            </div>
          )}
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-gray-900 truncate">{file.name}</p>
            <p className="text-xs text-gray-500">{(file.size / (1024 * 1024)).toFixed(1)} MB</p>
          </div>
          <button
            type="button"
            className="p-1.5 rounded-full hover:bg-gray-200 transition-colors"
            onClick={(e) => { e.stopPropagation(); onFileSelect(null); }}
          >
            <X size={16} className="text-gray-500" />
          </button>
        </div>
      ) : (
        <>
          <Plus size={24} className="text-gray-400 mb-2" />
          <p className="text-sm font-semibold text-gray-700">Extension Video</p>
          <p className="text-xs text-gray-500 mt-1">Appended after the hook (optional)</p>
        </>
      )}
    </div>
  );
}


// ---------- Main Component ----------

function RemixStudio() {
  const [viewState, setViewState] = useState('setup'); // 'setup' | 'processing' | 'result' | 'error'

  // Data — shared cache (preloaded at app boot, reused across remounts)
  const { hooks, loading: loadingHooks, setHooks } = useHooks();
  const { sounds, loading: loadingSounds } = useSounds();

  // Selections
  const [selectedHookId, setSelectedHookId] = useState(null);
  const [caption, setCaption] = useState('');
  const [selectedSoundId, setSelectedSoundId] = useState(null);
  const [extensionFile, setExtensionFile] = useState(null);

  // Processing state
  const [generationId, setGenerationId] = useState(null);
  const [steps, setSteps] = useState([]);
  const [error, setError] = useState(null);
  const [resultUrl, setResultUrl] = useState(null);
  const [videoGcsUrl, setVideoGcsUrl] = useState(null);
  const pollRef = useRef(null);

  // When selecting a hook, default sound to its original sound
  useEffect(() => {
    if (!selectedHookId) {
      setSelectedSoundId(null);
      return;
    }
    const hook = hooks.find((h) => h.hookId === selectedHookId);
    if (hook?.originalSoundId) {
      setSelectedSoundId(hook.originalSoundId);
    } else {
      setSelectedSoundId('__none__');
    }
  }, [selectedHookId, hooks]);

  // Cleanup poll on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const selectedHook = hooks.find((h) => h.hookId === selectedHookId);

  // Poll generation status
  const startPolling = useCallback((genId) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const data = await getGeneration(genId);
        if (data.steps) setSteps(data.steps);

        if (data.status === 'completed') {
          clearInterval(pollRef.current);
          pollRef.current = null;
          const gcsUrl = data.output?.videoGcs?.url || data.output?.videoUrl || null;
          setVideoGcsUrl(gcsUrl);
          setResultUrl(gcsUrl || '');
          setViewState('result');
        } else if (data.status === 'failed') {
          clearInterval(pollRef.current);
          pollRef.current = null;
          setError(data.error || 'Remix failed.');
          setViewState('error');
        }
      } catch (err) {
        console.error('Poll error:', err);
      }
    }, POLL_INTERVAL);
  }, []);

  // Submit remix
  const handleSubmit = useCallback(async () => {
    if (!selectedHookId) return;

    setViewState('processing');
    setError(null);

    const formData = new FormData();
    formData.append('hookId', selectedHookId);
    if (caption.trim()) formData.append('caption', caption.trim());
    if (selectedSoundId) formData.append('soundId', selectedSoundId);
    if (extensionFile) formData.append('extension_video', extensionFile);

    try {
      const data = await startRemix(formData);
      setGenerationId(data.generationId);
      // Immediately fetch the generation to get the steps
      const gen = await getGeneration(data.generationId);
      if (gen.steps) setSteps(gen.steps);
      startPolling(data.generationId);
    } catch (err) {
      setError(err.message);
      setViewState('error');
    }
  }, [selectedHookId, caption, selectedSoundId, extensionFile, startPolling]);

  const handleDeleteHook = useCallback(async (hookId) => {
    try {
      await deleteHook(hookId);
      setHooks((prev) => prev.filter((hook) => hook.hookId !== hookId));
      if (selectedHookId === hookId) {
        setSelectedHookId(null);
      }
    } catch (err) {
      console.error('Failed to delete hook:', err);
    }
  }, [selectedHookId, setHooks]);

  // Reset
  const handleReset = useCallback(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    setViewState('setup');
    setSelectedHookId(null);
    setCaption('');
    setSelectedSoundId(null);
    setExtensionFile(null);
    setGenerationId(null);
    setSteps([]);
    setError(null);
    setResultUrl(null);
    setVideoGcsUrl(null);
  }, []);

  // ---------- Setup View ----------
  if (viewState === 'setup') {
    return (
      <div className="h-full flex flex-col items-center px-4 pt-2 pb-6 md:pt-4 md:pb-8 overflow-y-auto">
        <div className="w-full max-w-2xl">

          {/* 1. Hook Picker */}
          <section className="mb-6">
            <h3 className="text-sm font-bold text-gray-700 mb-3 flex items-center gap-2">
              <Film size={16} className="text-purple-500" />
              Select Hook Video
            </h3>
            <div className="glass-card rounded-2xl p-4">
              <HookPicker
                hooks={hooks}
                selectedHookId={selectedHookId}
                onSelect={setSelectedHookId}
                onDelete={handleDeleteHook}
                loading={loadingHooks}
              />
            </div>
          </section>

          {/* 2. Caption Input */}
          <section className="mb-6">
            <h3 className="text-sm font-bold text-gray-700 mb-3 flex items-center gap-2">
              <Type size={16} className="text-purple-500" />
              Caption <span className="text-gray-400 font-normal">(optional)</span>
            </h3>
            <textarea
              value={caption}
              onChange={(e) => setCaption(e.target.value)}
              placeholder="Enter caption text to overlay on the video…"
              rows={3}
              className="w-full rounded-2xl border-2 border-nimbus-400/38 bg-white/50 px-4 py-3 text-sm text-gray-800 placeholder-nimbus-500 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.4)]
                focus:border-nimbus-500/45 focus:outline-none focus:ring-2 focus:ring-white/55 transition-all duration-200 resize-none"
            />
          </section>

          {/* 3. Sound Selector */}
          <section className="mb-6">
            <h3 className="text-sm font-bold text-gray-700 mb-3 flex items-center gap-2">
              <Music size={16} className="text-purple-500" />
              Sound
            </h3>
            <div className="glass-card rounded-2xl p-4">
              <SoundSelector
                sounds={sounds}
                selectedSoundId={selectedSoundId}
                originalSoundId={selectedHook?.originalSoundId}
                onSelect={setSelectedSoundId}
                loading={loadingSounds}
              />
            </div>
          </section>

          {/* 4. Extension Video */}
          <section className="mb-8">
            <h3 className="text-sm font-bold text-gray-700 mb-3 flex items-center gap-2">
              <Play size={16} className="text-purple-500" />
              Extension Video <span className="text-gray-400 font-normal">(optional)</span>
            </h3>
            <ExtensionDropZone file={extensionFile} onFileSelect={setExtensionFile} />
          </section>

          {/* Generate Button */}
          <div className="flex justify-center mb-12">
            <button
              onClick={handleSubmit}
              disabled={!selectedHookId}
              className={`px-8 py-4 font-semibold rounded-2xl transition-all duration-200 shadow-lg hover:shadow-xl
                ${selectedHookId
                  ? 'bg-gradient-to-r from-purple-600 to-purple-500 text-white hover:from-purple-700 hover:to-purple-600'
                  : 'bg-gray-200 text-gray-400 cursor-not-allowed shadow-none'}`}
            >
              Generate Remix
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ---------- Processing View ----------
  if (viewState === 'processing') {
    const completedCount = steps.filter((s) => s.status === 'completed').length;
    const progressPercent = steps.length ? Math.round((completedCount / steps.length) * 100) : 0;

    return (
      <div className="h-full flex flex-col items-center justify-center px-4 py-8">
        <div className="w-full max-w-lg flex-1 flex flex-col justify-center">
          <div className="text-center mb-8">
            <h2 className="text-2xl font-bold text-gray-900 mb-2">Remixing Your Video</h2>
            <p className="text-gray-600">This should only take a moment…</p>
          </div>

          {/* Progress bar */}
          <div className="w-full h-2 bg-gray-200 rounded-full mb-8 overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-purple-500 to-purple-600 rounded-full transition-all duration-500"
              style={{ width: `${progressPercent}%` }}
            />
          </div>

          {/* Steps list */}
          <div className="glass-card rounded-2xl divide-y divide-nimbus-400/15">
            {steps.map((step, i) => (
              <StepItem key={step.key} step={step} index={i} />
            ))}
          </div>
        </div>
      </div>
    );
  }

  // ---------- Result View ----------
  if (viewState === 'result') {
    return (
      <div className="h-full flex flex-col items-center justify-center px-4 py-8">
        <div className="w-full max-w-4xl flex-1 flex flex-col justify-center items-center">
          <div className="text-center mb-6">
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-green-100 mb-4">
              <CheckCircle2 size={28} className="text-green-600" />
            </div>
            <h2 className="text-2xl font-bold text-gray-900 mb-1">Remix Ready!</h2>
            <p className="text-gray-600">Your remixed video is ready</p>
          </div>

          {resultUrl && (
            <div className="w-full max-w-xs aspect-[9/16] rounded-2xl overflow-hidden bg-black shadow-xl mb-6">
              <video
                src={resultUrl}
                controls
                autoPlay
                className="w-full h-full object-contain"
              />
            </div>
          )}

          <div className="flex flex-col sm:flex-row gap-3 w-full sm:w-auto">
            <button
              onClick={handleReset}
              className="w-full sm:w-auto px-6 py-3 bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold rounded-xl transition-all duration-200"
            >
              <span className="flex items-center gap-2">
                <ArrowLeft size={18} />
                New Remix
              </span>
            </button>
            {resultUrl && (
              <a
                href={resultUrl}
                download="nflncrai_remix.mp4"
                className="w-full sm:w-auto px-6 py-3 bg-gradient-to-r from-purple-600 to-purple-500 text-white font-semibold rounded-xl hover:from-purple-700 hover:to-purple-600 transition-all duration-200"
              >
                <span className="flex items-center gap-2">
                  <Download size={18} />
                  Download
                </span>
              </a>
            )}
          </div>

          <ScheduleToSocial resultUrl={resultUrl} videoGcsUrl={videoGcsUrl} />
        </div>
      </div>
    );
  }

  // ---------- Error View ----------
  if (viewState === 'error') {
    return (
      <div className="h-full flex flex-col items-center justify-center px-4 py-8">
        <div className="w-full max-w-lg flex-1 flex flex-col justify-center items-center">
          <div className="text-center mb-6">
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-red-100 mb-4">
              <XCircle size={28} className="text-red-600" />
            </div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">Remix Failed</h2>
            <p className="text-gray-600 text-sm max-w-md">{error}</p>
          </div>

          <button
            onClick={handleReset}
            className="px-6 py-3 bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold rounded-xl transition-all duration-200"
          >
            <span className="flex items-center gap-2">
              <ArrowLeft size={18} />
              Try Again
            </span>
          </button>
        </div>
      </div>
    );
  }

  return null;
}

export default RemixStudio;
