import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlignJustify,
  AlignVerticalJustifyStart,
  ArrowUpRight,
  Asterisk,
  Activity,
  Ban,
  Beer,
  ChevronDown,
  Circle,
  CircleDot,
  Clock,
  Dot,
  Droplet,
  Dumbbell,
  Eye,
  Gem,
  Glasses,
  Globe,
  Heart,
  Image as ImageIcon,
  Layers,
  Loader2,
  Minus,
  MoveVertical,
  Palette,
  PersonStanding,
  Plus,
  RefreshCw,
  RotateCcw,
  Ruler,
  Scissors,
  Shirt,
  Shuffle,
  Slash,
  Smile,
  Sparkle,
  Sparkles,
  Stars,
  Trash2,
  Triangle,
  User,
  XCircle,
  CheckCircle2,
} from 'lucide-react';
import {
  AVATAR_SECTIONS,
  buildPromptFromSelections,
  findOption,
  getMissingRequired,
  randomizeSelections,
} from '../lib/avatarOptions';
import { useModels, modelStore } from '../lib/mediaLibrary';
import { startAvatarGeneration, getGeneration, deleteModel } from '../lib/lateApi';

// ---------- Lucide icon registry ----------
// AvatarStudio renders icon names from the manifest at runtime; keep this in sync
// with any icon ids referenced in src/lib/avatarOptions.js.
const ICONS = {
  AlignJustify,
  AlignVerticalJustifyStart,
  ArrowUpRight,
  Asterisk,
  Activity,
  Ban,
  Beer,
  Circle,
  CircleDot,
  Clock,
  Dot,
  Droplet,
  Dumbbell,
  Eye,
  Gem,
  Glasses,
  Globe,
  Heart,
  Layers,
  Minus,
  MoveVertical,
  Palette,
  PersonStanding,
  Ruler,
  Scissors,
  Shirt,
  Slash,
  Smile,
  Sparkle,
  Sparkles,
  Stars,
  Triangle,
  User,
};

function Icon({ name, ...props }) {
  const Component = ICONS[name] || User;
  return <Component {...props} />;
}

const POLL_INTERVAL = 2200;

// ---------- Avatar Rail (left column) ----------

function AvatarRail({ avatars, selectedId, onSelect, onDelete, onCreateNew, loading }) {
  return (
    <div className="h-full flex flex-col gap-2 overflow-y-auto pr-1 scrollbar-hide">
      <button
        type="button"
        onClick={onCreateNew}
        className={`relative w-full aspect-[4/5] rounded-2xl border-2 border-dashed border-nimbus-400/45 bg-white/15 hover:border-nimbus-500/55 hover:bg-white/22 flex flex-col items-center justify-center transition-all duration-200 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.3)] ${
          selectedId === null ? 'border-solid border-nimbus-500/55 bg-white/25 ring-2 ring-white/60' : ''
        }`}
      >
        <div className="w-9 h-9 rounded-full bg-white/40 flex items-center justify-center mb-1.5">
          <Plus size={18} className="text-nimbus-700" />
        </div>
        <span className="text-[11px] font-semibold text-nimbus-800">Create new</span>
      </button>

      {loading && (
        <div className="flex items-center justify-center py-3">
          <Loader2 size={14} className="text-purple-500 animate-spin" />
        </div>
      )}

      {avatars.map((avatar) => {
        const isSelected = avatar.modelId === selectedId;
        const label = avatar.label || avatar.modelId.slice(0, 6);
        return (
          <div key={avatar.modelId} className="relative group">
            <button
              type="button"
              onClick={() => onSelect(avatar.modelId)}
              className={`relative w-full aspect-[4/5] rounded-2xl overflow-hidden border-2 transition-all duration-200 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.25)] ${
                isSelected
                  ? 'border-nimbus-600 ring-2 ring-white/70 shadow-md'
                  : 'border-nimbus-400/40 hover:border-nimbus-500/55'
              }`}
            >
              <img src={avatar.url} alt={label} className="w-full h-full object-cover" loading="lazy" />
              <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 via-black/30 to-transparent px-2 py-1">
                <p className="text-[11px] font-semibold text-white truncate">{label}</p>
              </div>
              {isSelected && (
                <div className="absolute top-1 right-1 bg-purple-500 rounded-full p-0.5">
                  <CheckCircle2 size={12} className="text-white" />
                </div>
              )}
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onDelete(avatar.modelId);
              }}
              className="absolute top-1 left-1 bg-red-500 text-white rounded-full p-1 opacity-0 group-hover:opacity-100 transition-opacity"
              title="Delete avatar"
            >
              <Trash2 size={10} />
            </button>
          </div>
        );
      })}
    </div>
  );
}

// ---------- Center Preview ----------

function AvatarPreview({ status, previewUrl, summaryChips, onUseForVideo, error }) {
  return (
    <div className="h-full flex flex-col">
      <div className="relative flex-1 min-h-0 rounded-3xl glass-card overflow-hidden flex items-center justify-center">
        {previewUrl ? (
          <img
            src={previewUrl}
            alt="Avatar preview"
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="text-center px-6 py-10">
            <div className="mx-auto mb-4 inline-flex h-14 w-14 items-center justify-center rounded-full bg-white/55">
              {status === 'generating' ? (
                <Loader2 size={26} className="text-nimbus-700 animate-spin" />
              ) : status === 'error' ? (
                <XCircle size={28} className="text-red-500" />
              ) : (
                <ImageIcon size={26} className="text-nimbus-600" />
              )}
            </div>
            <h3 className="font-display text-xl font-medium tracking-tight text-ink-950 mb-1">
              {status === 'generating'
                ? 'Crafting your avatar…'
                : status === 'error'
                  ? 'Generation failed'
                  : 'Your AI avatar lives here'}
            </h3>
            <p className="text-sm text-nimbus-700 max-w-xs mx-auto">
              {status === 'generating'
                ? 'Hang tight — this usually takes 20–40 seconds.'
                : status === 'error'
                  ? error || 'Try adjusting your selections and generate again.'
                  : 'Design and build your AI influencer from scratch.'}
            </p>
          </div>
        )}

        <div className="absolute top-3 left-3 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-black/35 backdrop-blur-sm text-white text-[10px] font-semibold uppercase tracking-wider">
          <User size={11} />
          Human
        </div>

        {previewUrl && status === 'completed' && (
          <button
            type="button"
            onClick={onUseForVideo}
            className="absolute bottom-3 right-3 inline-flex items-center gap-1.5 px-3 py-2 rounded-full bg-white text-ink-950 text-xs font-semibold shadow-lg hover:-translate-y-0.5 transition-transform"
          >
            Use for Video
            <ArrowUpRight size={14} />
          </button>
        )}
      </div>

      {summaryChips.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {summaryChips.slice(0, 8).map((chip) => (
            <span
              key={chip.key}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-white/55 border border-white/60 text-[11px] font-medium text-nimbus-800"
            >
              {chip.label}
            </span>
          ))}
          {summaryChips.length > 8 && (
            <span className="text-[11px] text-nimbus-700 self-center">+{summaryChips.length - 8} more</span>
          )}
        </div>
      )}
    </div>
  );
}

// ---------- Option Card variants ----------

function PhotoCard({ option, isSelected, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={isSelected}
      className={`relative aspect-[4/5] rounded-xl overflow-hidden border-2 transition-all duration-200 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.25)] ${
        isSelected
          ? 'border-nimbus-600 ring-2 ring-white/70 shadow-md'
          : 'border-nimbus-400/40 hover:border-nimbus-500/55'
      }`}
    >
      <img src={option.thumbnail} alt={option.label} className="w-full h-full object-cover" loading="lazy" />
      <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/75 via-black/30 to-transparent px-1.5 py-1">
        <p className="text-[10px] font-semibold text-white truncate text-center">{option.label}</p>
      </div>
      {isSelected && (
        <div className="absolute top-1 right-1 bg-purple-500 rounded-full p-0.5">
          <CheckCircle2 size={10} className="text-white" />
        </div>
      )}
    </button>
  );
}

function SwatchCard({ option, isSelected, onClick }) {
  const isGradient = typeof option.swatch === 'string' && option.swatch.includes('gradient');
  const style = isGradient
    ? { backgroundImage: option.swatch }
    : { backgroundColor: option.swatch };
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={isSelected}
      title={option.label}
      className={`group flex flex-col items-center gap-1 transition-transform duration-150 ${
        isSelected ? 'scale-[1.02]' : 'hover:scale-[1.02]'
      }`}
    >
      <div
        style={style}
        className={`relative w-full aspect-square rounded-xl border-2 transition-all duration-200 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.3),0_2px_4px_rgba(0,0,0,0.06)] ${
          isSelected
            ? 'border-nimbus-700 ring-2 ring-white/70'
            : 'border-white/55 hover:border-white/80'
        }`}
      >
        {isSelected && (
          <div className="absolute -top-1 -right-1 bg-purple-500 rounded-full p-0.5 shadow">
            <CheckCircle2 size={10} className="text-white" />
          </div>
        )}
      </div>
      <span className="text-[10px] font-medium text-nimbus-800 truncate w-full text-center">
        {option.label}
      </span>
    </button>
  );
}

function IconCard({ option, isSelected, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={isSelected}
      className={`relative flex flex-col items-center justify-center gap-1.5 aspect-square rounded-xl border-2 transition-all duration-200 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.3)] ${
        isSelected
          ? 'border-nimbus-600 bg-white/55 ring-2 ring-white/70 shadow-md'
          : 'border-nimbus-400/40 bg-white/30 hover:border-nimbus-500/55 hover:bg-white/45'
      }`}
    >
      <Icon name={option.icon} size={22} className={isSelected ? 'text-nimbus-900' : 'text-nimbus-700'} />
      <span className={`text-[10px] font-semibold text-center px-1 leading-tight ${
        isSelected ? 'text-nimbus-900' : 'text-nimbus-700'
      }`}>
        {option.label}
      </span>
      {isSelected && (
        <div className="absolute top-1 right-1 bg-purple-500 rounded-full p-0.5">
          <CheckCircle2 size={9} className="text-white" />
        </div>
      )}
    </button>
  );
}

// ---------- Builder Section ----------

function BuilderSection({ section, value, onChange, defaultOpen }) {
  const [open, setOpen] = useState(defaultOpen);
  const isMulti = Boolean(section.allowMultiple);
  const selectedSet = useMemo(() => {
    if (isMulti) return new Set(Array.isArray(value) ? value : []);
    return new Set(value ? [value] : []);
  }, [value, isMulti]);

  const handleClick = useCallback(
    (optId) => {
      if (isMulti) {
        const next = new Set(selectedSet);
        if (next.has(optId)) next.delete(optId);
        else next.add(optId);
        onChange(Array.from(next));
      } else {
        onChange(selectedSet.has(optId) && !section.required ? null : optId);
      }
    },
    [isMulti, onChange, section.required, selectedSet],
  );

  const grid = `grid grid-cols-${section.columns || 3} gap-2`;

  return (
    <div className="rounded-2xl glass-card overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between gap-2 px-3.5 py-2.5 text-left"
      >
        <div className="flex items-center gap-2 min-w-0">
          <Icon name={section.icon} size={14} className="text-nimbus-700 flex-shrink-0" />
          <span className="text-sm font-semibold text-nimbus-900 tracking-tight truncate">
            {section.label}
          </span>
          {section.required && !selectedSet.size && (
            <span className="text-[9px] font-bold text-amber-700 bg-amber-100 px-1.5 py-0.5 rounded-full uppercase">
              Required
            </span>
          )}
        </div>
        <ChevronDown
          size={15}
          className={`text-nimbus-600 flex-shrink-0 transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {open && (
        <div className="px-3.5 pb-3.5 pt-1">
          <div className={grid} style={{ gridTemplateColumns: `repeat(${section.columns || 3}, minmax(0, 1fr))` }}>
            {section.options.map((opt) => {
              const isSelected = selectedSet.has(opt.id);
              if (section.kind === 'photo') {
                return <PhotoCard key={opt.id} option={opt} isSelected={isSelected} onClick={() => handleClick(opt.id)} />;
              }
              if (section.kind === 'swatch') {
                return <SwatchCard key={opt.id} option={opt} isSelected={isSelected} onClick={() => handleClick(opt.id)} />;
              }
              return <IconCard key={opt.id} option={opt} isSelected={isSelected} onClick={() => handleClick(opt.id)} />;
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------- Main Component ----------

export default function AvatarStudio({ onUseAvatarForVideo, onGenerationStarted }) {
  const { models, loading: loadingModels, setModels } = useModels();
  const [selections, setSelections] = useState({});
  const [selectedAvatarId, setSelectedAvatarId] = useState(null);
  const [status, setStatus] = useState('idle'); // idle | generating | completed | error
  const [error, setError] = useState('');
  const [generationId, setGenerationId] = useState('');
  const [livePreviewUrl, setLivePreviewUrl] = useState('');
  const pollRef = useRef(null);

  // Avatars are saved models with source: 'avatar_studio'. Filter to that subset.
  const avatars = useMemo(
    () => models.filter((m) => m?.source === 'avatar_studio'),
    [models],
  );

  // Derive preview from selected avatar OR live generation result
  const selectedAvatar = useMemo(
    () => avatars.find((a) => a.modelId === selectedAvatarId) || null,
    [avatars, selectedAvatarId],
  );
  const previewUrl = livePreviewUrl || selectedAvatar?.url || '';

  const summaryChips = useMemo(() => {
    const chips = [];
    for (const section of AVATAR_SECTIONS) {
      const value = selections[section.id];
      if (!value) continue;
      const ids = Array.isArray(value) ? value : [value];
      for (const id of ids) {
        const opt = findOption(section.id, id);
        if (opt) chips.push({ key: `${section.id}:${id}`, label: opt.label });
      }
    }
    return chips;
  }, [selections]);

  const missing = useMemo(() => getMissingRequired(selections), [selections]);
  const canGenerate = missing.length === 0 && status !== 'generating';

  const handleSelectionChange = useCallback((sectionId) => (next) => {
    setSelections((prev) => {
      if (next === null || (Array.isArray(next) && !next.length)) {
        const copy = { ...prev };
        delete copy[sectionId];
        return copy;
      }
      return { ...prev, [sectionId]: next };
    });
  }, []);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => () => stopPolling(), [stopPolling]);

  const handleReset = useCallback(() => {
    setSelections({});
    setStatus('idle');
    setError('');
    setGenerationId('');
    setLivePreviewUrl('');
    setSelectedAvatarId(null);
  }, []);

  const handleRandomize = useCallback(() => {
    setSelections(randomizeSelections());
  }, []);

  const handleSelectAvatar = useCallback((modelId) => {
    setSelectedAvatarId((prev) => (prev === modelId ? null : modelId));
    setLivePreviewUrl('');
    setStatus('idle');
    setError('');
  }, []);

  const handleDeleteAvatar = useCallback(async (modelId) => {
    try {
      await deleteModel(modelId);
      setModels((prev) => prev.filter((m) => m.modelId !== modelId));
      if (selectedAvatarId === modelId) {
        setSelectedAvatarId(null);
      }
    } catch (err) {
      console.error('Failed to delete avatar:', err);
    }
  }, [selectedAvatarId, setModels]);

  const handleGenerate = useCallback(async () => {
    if (!canGenerate) return;
    setStatus('generating');
    setError('');
    setLivePreviewUrl('');
    setSelectedAvatarId(null);

    try {
      const summary = buildPromptFromSelections(selections);
      const labelChips = summaryChips
        .slice(0, 3)
        .map((c) => c.label)
        .join(' · ');
      const result = await startAvatarGeneration({
        selections,
        promptSummary: summary,
        label: labelChips || 'AI Avatar',
      });
      const genId = result.generationId;
      setGenerationId(genId);
      onGenerationStarted?.();

      stopPolling();
      pollRef.current = setInterval(async () => {
        try {
          const gen = await getGeneration(genId);
          if (gen.status === 'completed') {
            stopPolling();
            const out = gen.output || {};
            const newModel = out.model;
            if (newModel) {
              setModels((prev) => {
                const exists = prev.some((m) => m.modelId === newModel.modelId);
                if (exists) return prev;
                return [newModel, ...prev];
              });
              modelStore.load(true);
              setSelectedAvatarId(newModel.modelId);
              setLivePreviewUrl(newModel.url || '');
            }
            setStatus('completed');
          } else if (gen.status === 'failed') {
            stopPolling();
            setStatus('error');
            setError(gen.error || 'Avatar generation failed.');
          }
        } catch (err) {
          stopPolling();
          setStatus('error');
          setError(err?.message || 'Lost connection while generating.');
        }
      }, POLL_INTERVAL);
    } catch (err) {
      setStatus('error');
      setError(err?.message || 'Failed to start avatar generation.');
    }
  }, [canGenerate, selections, summaryChips, stopPolling, setModels, onGenerationStarted]);

  const handleUseForVideo = useCallback(() => {
    if (!selectedAvatar) return;
    onUseAvatarForVideo?.(selectedAvatar);
  }, [selectedAvatar, onUseAvatarForVideo]);

  return (
    <div className="h-full flex flex-col px-3 pt-2 pb-4 md:pb-6">
      {/* Three-panel layout — left rail | preview | builder */}
      <div className="flex-1 min-h-0 grid grid-cols-12 gap-3">
        {/* Left rail */}
        <aside className="col-span-3 lg:col-span-2 min-h-0">
          <div className="h-full glass-pane rounded-2xl p-2.5 flex flex-col">
            <div className="flex items-center gap-1.5 px-1.5 pb-2 border-b border-white/40 mb-2">
              <Sparkles size={13} className="text-nimbus-700" />
              <span className="text-[11px] font-semibold uppercase tracking-wider text-nimbus-800">
                AI Avatars
              </span>
            </div>
            <div className="flex-1 min-h-0">
              <AvatarRail
                avatars={avatars}
                selectedId={selectedAvatarId}
                onSelect={handleSelectAvatar}
                onDelete={handleDeleteAvatar}
                onCreateNew={handleReset}
                loading={loadingModels}
              />
            </div>
          </div>
        </aside>

        {/* Center preview */}
        <section className="col-span-5 lg:col-span-6 min-h-0 flex flex-col">
          <div className="flex-1 min-h-0">
            <AvatarPreview
              status={status}
              previewUrl={previewUrl}
              summaryChips={summaryChips}
              onUseForVideo={handleUseForVideo}
              error={error}
            />
          </div>
        </section>

        {/* Right builder panel */}
        <aside className="col-span-4 min-h-0">
          <div className="h-full glass-pane rounded-2xl p-2.5 flex flex-col">
            <div className="flex items-center justify-between gap-2 px-1.5 pb-2 border-b border-white/40 mb-2">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-nimbus-800">
                Builder
              </span>
              <button
                type="button"
                onClick={handleReset}
                className="inline-flex items-center gap-1 text-[11px] font-semibold text-nimbus-700 hover:text-nimbus-900 transition-colors"
              >
                <RotateCcw size={12} />
                Reset
              </button>
            </div>
            <div className="flex-1 min-h-0 overflow-y-auto pr-1 space-y-2">
              {AVATAR_SECTIONS.map((section, idx) => (
                <BuilderSection
                  key={section.id}
                  section={section}
                  value={selections[section.id]}
                  onChange={handleSelectionChange(section.id)}
                  defaultOpen={idx < 3}
                />
              ))}
            </div>
          </div>
        </aside>
      </div>

      {/* Bottom action bar */}
      <div className="mt-3 flex items-center justify-between gap-3 rounded-2xl glass-card px-3 py-2.5">
        <div className="flex items-center gap-2 min-w-0">
          <button
            type="button"
            onClick={handleRandomize}
            className="inline-flex items-center justify-center w-9 h-9 rounded-xl bg-white/65 border border-white/70 text-nimbus-800 hover:bg-white/85 transition-colors"
            title="Randomize"
          >
            <Shuffle size={15} />
          </button>
          {missing.length > 0 ? (
            <p className="text-[11px] text-amber-700 font-medium truncate">
              Pick {missing.slice(0, 3).join(', ')}
              {missing.length > 3 ? `, +${missing.length - 3} more` : ''} to continue
            </p>
          ) : (
            <p className="text-[11px] text-nimbus-700 font-medium truncate">
              Ready to generate · {summaryChips.length} attributes selected
            </p>
          )}
        </div>

        <button
          type="button"
          onClick={handleGenerate}
          disabled={!canGenerate}
          className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-2xl text-sm font-semibold transition-all duration-200 ${
            canGenerate
              ? 'bg-gradient-to-r from-purple-600 to-purple-500 text-white shadow-lg hover:from-purple-700 hover:to-purple-600 hover:-translate-y-0.5'
              : 'bg-gray-200 text-gray-400 cursor-not-allowed'
          }`}
        >
          {status === 'generating' ? (
            <>
              <Loader2 size={16} className="animate-spin" />
              Generating…
            </>
          ) : status === 'error' ? (
            <>
              <RefreshCw size={16} />
              Retry
            </>
          ) : (
            <>
              <Sparkles size={16} />
              Generate Avatar
            </>
          )}
        </button>
      </div>
    </div>
  );
}
