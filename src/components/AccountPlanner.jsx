import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  ArrowUpRight,
  CalendarClock,
  CheckCircle2,
  Loader2,
  PlayCircle,
  RefreshCw,
  Sparkles,
  Video,
} from 'lucide-react';
import {
  createStudyTokSimplePlan,
  generateAccountPlanPosts,
  getAccountPlan,
  scheduleAccountPlanPosts,
  swapAccountPlanPost,
  updateAccountPlan,
  updateAccountPlanPost,
} from '../lib/organizerApi';
import {
  DEFAULT_SESSION_ID,
  createLatePost,
  listLateAccounts,
} from '../lib/lateApi';
import { useExtensionVideos, useModels } from '../lib/mediaLibrary';

const DEFAULT_TIMES = ['09:00', '12:30', '16:30', '20:00'];

function todayInputValue() {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

function tagValue(value) {
  return value ? String(value).replaceAll('_', ' ') : 'n/a';
}

function statusClass(status) {
  if (status === 'generated' || status === 'scheduled') return 'bg-emerald-400/15 text-emerald-100';
  if (status === 'generating' || status === 'queued') return 'bg-cyan-400/15 text-cyan-100';
  if (status === 'failed' || status === 'rejected') return 'bg-red-400/15 text-red-100';
  return 'bg-white/10 text-white/60';
}

function toIsoLocal(value) {
  if (!value) return '';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toISOString();
}

function formatSchedule(value) {
  if (!value) return 'No date';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
}

function assetLabel(asset, idKey) {
  if (!asset) return 'Not selected';
  const id = asset[idKey] || '';
  return asset.label || asset.filename || (id ? id.slice(0, 8) : 'Untitled asset');
}

function primeVideoFrame(event) {
  const video = event.currentTarget;
  if (!Number.isFinite(video.duration) || video.duration <= 0) return;
  try {
    video.currentTime = Math.min(0.15, video.duration / 10);
  } catch {
    // Some browsers block seeking before enough data is buffered.
  }
}

function playPreview(event) {
  event.currentTarget.play().catch(() => {});
}

function resetPreview(event) {
  const video = event.currentTarget;
  video.pause();
  try {
    video.currentTime = 0;
  } catch {
    // Ignore reset failures for signed/streaming videos.
  }
}

function ModelImagePicker({ models, loading, selectedModelId, onSelect }) {
  if (loading) {
    return (
      <div className="flex items-center gap-2 rounded-2xl border border-white/10 bg-black/20 px-3 py-3 text-sm text-white/45">
        <Loader2 size={16} className="animate-spin" aria-hidden />
        Loading saved models...
      </div>
    );
  }

  if (!models.length) {
    return (
      <div className="rounded-2xl border border-white/10 bg-black/20 px-3 py-3 text-sm text-white/45">
        No saved models yet. Create or upload a model first.
      </div>
    );
  }

  return (
    <div className="grid max-h-56 grid-cols-3 gap-2 overflow-y-auto pr-1 sm:grid-cols-4 md:grid-cols-5">
      {models.map((model) => {
        const selected = model.modelId === selectedModelId;
        return (
          <button
            key={model.modelId}
            type="button"
            onClick={() => onSelect(model.modelId)}
            aria-pressed={selected}
            className={`group overflow-hidden rounded-2xl border bg-black/20 text-left transition ${
              selected
                ? 'border-cyan-300 ring-2 ring-cyan-300/40'
                : 'border-white/10 hover:border-white/35'
            }`}
            title={assetLabel(model, 'modelId')}
          >
            <div className="aspect-[4/5] bg-white/10">
              {model.url ? (
                <img
                  src={model.url}
                  alt={assetLabel(model, 'modelId')}
                  className="h-full w-full object-cover"
                  loading="lazy"
                />
              ) : (
                <div className="flex h-full w-full items-center justify-center text-white/35">
                  <Video size={18} aria-hidden />
                </div>
              )}
            </div>
            <div className="px-2 py-1.5">
              <p className="truncate text-[11px] font-semibold text-white/70">
                {assetLabel(model, 'modelId')}
              </p>
            </div>
          </button>
        );
      })}
    </div>
  );
}

function ExtensionVideoPicker({ videos, loading, disabled, selectedVideoId, onSelect }) {
  if (loading) {
    return (
      <div className="flex items-center gap-2 rounded-2xl border border-white/10 bg-black/20 px-3 py-3 text-sm text-white/45">
        <Loader2 size={16} className="animate-spin" aria-hidden />
        Loading extension videos...
      </div>
    );
  }

  if (disabled) {
    return (
      <div className="rounded-2xl border border-white/10 bg-black/20 px-3 py-3 text-sm text-white/45">
        No hook + demo posts in this plan.
      </div>
    );
  }

  if (!videos.length) {
    return (
      <div className="rounded-2xl border border-white/10 bg-black/20 px-3 py-3 text-sm text-white/45">
        No extension videos yet. Upload a demo extension first.
      </div>
    );
  }

  return (
    <div className="grid max-h-56 grid-cols-2 gap-2 overflow-y-auto pr-1 sm:grid-cols-3">
      {videos.map((video) => {
        const selected = video.extensionVideoId === selectedVideoId;
        return (
          <button
            key={video.extensionVideoId}
            type="button"
            onClick={() => onSelect(video.extensionVideoId)}
            aria-pressed={selected}
            className={`group overflow-hidden rounded-2xl border bg-black/20 text-left transition ${
              selected
                ? 'border-violet-300 ring-2 ring-violet-300/40'
                : 'border-white/10 hover:border-white/35'
            }`}
            title={assetLabel(video, 'extensionVideoId')}
          >
            <div className="aspect-video bg-white/10">
              {video.url ? (
                <div className="relative h-full w-full">
                  <video
                    src={video.url}
                    className="h-full w-full object-cover"
                    muted
                    playsInline
                    preload="metadata"
                    onLoadedMetadata={primeVideoFrame}
                    onMouseOver={playPreview}
                    onMouseOut={resetPreview}
                    onFocus={playPreview}
                    onBlur={resetPreview}
                  />
                  <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-black/5 text-white/80 opacity-0 transition group-hover:opacity-100">
                    <PlayCircle size={18} aria-hidden />
                  </div>
                </div>
              ) : (
                <div className="flex h-full w-full items-center justify-center text-white/35">
                  <Video size={18} aria-hidden />
                </div>
              )}
            </div>
            <div className="px-2 py-1.5">
              <p className="truncate text-[11px] font-semibold text-white/70">
                {assetLabel(video, 'extensionVideoId')}
              </p>
            </div>
          </button>
        );
      })}
    </div>
  );
}

function PostCard({
  post,
  canSchedule,
  selectedPlatforms,
  onPatchPost,
  onSchedulePost,
  onSwapPost,
  isScheduling,
  isSwapping,
}) {
  const source = post.sourceVideo || {};
  const tags = post.keyTags || {};
  const generated = post.status === 'generated' || post.generatedMediaUrl;
  return (
    <article className="rounded-3xl border border-white/10 bg-white/[0.04] p-4">
      <div className="grid gap-4 lg:grid-cols-[84px_minmax(0,1fr)_260px]">
        <a
          href={source.url}
          target="_blank"
          rel="noreferrer"
          className="relative h-28 overflow-hidden rounded-2xl bg-white/10"
        >
          {source.thumbnailUrl ? (
            <img src={source.thumbnailUrl} alt="" className="h-full w-full object-cover" loading="lazy" />
          ) : (
            <div className="flex h-full w-full items-center justify-center text-white/40">
              <Video size={18} aria-hidden />
            </div>
          )}
        </a>

        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-white/10 px-2.5 py-1 text-xs font-semibold text-white/60">
              Slot {post.slot}
            </span>
            <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${post.purpose === 'hook_demo' ? 'bg-violet-400/15 text-violet-100' : 'bg-sky-400/15 text-sky-100'}`}>
              {tagValue(post.purpose)}
            </span>
            <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${statusClass(post.status)}`}>
              {tagValue(post.status)}
            </span>
            {post.weakMatch && (
              <span className="rounded-full bg-amber-400/15 px-2.5 py-1 text-xs font-semibold text-amber-100">
                weak match
              </span>
            )}
          </div>
          <div className="mt-3 flex items-center gap-2">
            <p className="truncate text-sm font-semibold text-white/75">@{source.creatorHandle || 'unknown'}</p>
            {source.url && (
              <a href={source.url} target="_blank" rel="noreferrer" className="text-white/40 hover:text-white">
                <ArrowUpRight size={14} aria-hidden />
              </a>
            )}
          </div>
          <p className="mt-2 line-clamp-2 text-sm leading-6 text-white/50">
            {source.caption || 'No source caption.'}
          </p>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {(post.selectionReasons || []).slice(0, 4).map((reason) => (
              <span key={reason} className="rounded-full bg-white/10 px-2 py-1 text-[11px] text-white/45">
                {reason}
              </span>
            ))}
            {tags.study_content_type && (
              <span className="rounded-full bg-white/10 px-2 py-1 text-[11px] text-white/45">
                {tagValue(tags.study_content_type)}
              </span>
            )}
          </div>
        </div>

        <div className="grid gap-2">
          <label className="grid gap-1 text-xs text-white/40">
            Caption draft
            <textarea
              value={post.captionDraft || ''}
              rows={3}
              onChange={(event) => onPatchPost(post.slot, { captionDraft: event.target.value })}
              className="resize-none rounded-2xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-white outline-none"
            />
          </label>
          <label className="grid gap-1 text-xs text-white/40">
            Suggested schedule
            <input
              type="datetime-local"
              value={(post.suggestedScheduledFor || '').slice(0, 16)}
              onChange={(event) => onPatchPost(post.slot, { suggestedScheduledFor: event.target.value })}
              className="rounded-2xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-white outline-none"
            />
          </label>
          {generated ? (
            <div className="grid gap-2">
              <div className="flex gap-2">
                <a
                  href={post.generatedMediaUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex flex-1 items-center justify-center gap-2 rounded-2xl bg-white/10 px-3 py-2 text-xs font-semibold text-white/70 hover:bg-white/15"
                >
                  <PlayCircle size={14} aria-hidden />
                  Review
                </a>
                <button
                  type="button"
                  disabled={!canSchedule || isScheduling}
                  onClick={() => onSchedulePost(post)}
                  className="inline-flex flex-1 items-center justify-center gap-2 rounded-2xl bg-emerald-300 px-3 py-2 text-xs font-semibold text-ink-950 disabled:cursor-not-allowed disabled:opacity-50"
                  title={!selectedPlatforms.length ? 'Select a connected account first' : undefined}
                >
                  {isScheduling ? <Loader2 size={14} className="animate-spin" aria-hidden /> : <CalendarClock size={14} aria-hidden />}
                  Schedule
                </button>
              </div>
              {post.scheduleError && (
                <p className="rounded-2xl bg-red-400/10 px-3 py-2 text-xs text-red-100">
                  {post.scheduleError}
                </p>
              )}
              <button
                type="button"
                disabled={isSwapping || post.status === 'generating'}
                onClick={() => onSwapPost(post.slot)}
                className="inline-flex items-center justify-center gap-2 rounded-2xl bg-white/10 px-3 py-2 text-xs font-semibold text-white/70 hover:bg-white/15 disabled:cursor-not-allowed disabled:opacity-50"
                title="Swap this source for a similar unused tagged video"
              >
                {isSwapping ? <Loader2 size={14} className="animate-spin" aria-hidden /> : <RefreshCw size={14} aria-hidden />}
                Swap similar
              </button>
            </div>
          ) : (
            <div className="grid gap-2">
              <p className="rounded-2xl bg-black/20 px-3 py-2 text-xs text-white/40">
                {post.error || `Scheduled for ${formatSchedule(post.suggestedScheduledFor)} after generation.`}
              </p>
              <button
                type="button"
                disabled={isSwapping || post.status === 'generating'}
                onClick={() => onSwapPost(post.slot)}
                className="inline-flex items-center justify-center gap-2 rounded-2xl bg-white/10 px-3 py-2 text-xs font-semibold text-white/70 hover:bg-white/15 disabled:cursor-not-allowed disabled:opacity-50"
                title="Swap this source for a similar unused tagged video"
              >
                {isSwapping ? <Loader2 size={14} className="animate-spin" aria-hidden /> : <RefreshCw size={14} aria-hidden />}
                Swap similar
              </button>
            </div>
          )}
        </div>
      </div>
    </article>
  );
}

function AccountPlanner({ onGenerationStarted }) {
  const [postCount, setPostCount] = useState(30);
  const [relatablePerDay, setRelatablePerDay] = useState(3);
  const [hookDemoPerDay, setHookDemoPerDay] = useState(1);
  const [startDate, setStartDate] = useState(todayInputValue());
  const [dailyTimes, setDailyTimes] = useState(DEFAULT_TIMES);
  const [plan, setPlan] = useState(null);
  const [accounts, setAccounts] = useState([]);
  const [selectedAccountIds, setSelectedAccountIds] = useState([]);
  const [selectedModelId, setSelectedModelId] = useState('');
  const [selectedExtensionVideoId, setSelectedExtensionVideoId] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [isStartingGeneration, setIsStartingGeneration] = useState(false);
  const [isSchedulingAll, setIsSchedulingAll] = useState(false);
  const [schedulingSlot, setSchedulingSlot] = useState(null);
  const [swappingSlot, setSwappingSlot] = useState(null);
  const [error, setError] = useState('');
  const timezone = useMemo(() => Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC', []);
  const { models, loading: loadingModels } = useModels();
  const { extensionVideos, loading: loadingExtensionVideos } = useExtensionVideos();

  const refreshPlan = useCallback(async () => {
    if (!plan?.id) return;
    try {
      const next = await getAccountPlan(plan.id);
      setPlan(next);
    } catch (err) {
      setError(err.message || 'Could not refresh plan.');
    }
  }, [plan?.id]);

  useEffect(() => {
    let cancelled = false;
    async function loadAccounts() {
      try {
        const result = await listLateAccounts({ sessionId: DEFAULT_SESSION_ID });
        if (cancelled) return;
        const normalized = (result.accounts || [])
          .map((account) => ({
            id: String(account?._id ?? account?.id ?? ''),
            platform: String(account?.platform ?? account?.provider ?? ''),
          }))
          .filter((account) => account.id && account.platform);
        setAccounts(normalized);
      } catch {
        setAccounts([]);
      }
    }
    loadAccounts();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!plan?.id || !['generating', 'generation_dry_run'].includes(plan.status)) return undefined;
    const id = window.setInterval(refreshPlan, 3000);
    return () => window.clearInterval(id);
  }, [plan?.id, plan?.status, refreshPlan]);

  useEffect(() => {
    if (models.length && !models.some((model) => model.modelId === selectedModelId)) {
      setSelectedModelId(models[0].modelId || '');
    } else if (!models.length && selectedModelId) {
      setSelectedModelId('');
    }
  }, [models, selectedModelId]);

  useEffect(() => {
    if (
      extensionVideos.length
      && !extensionVideos.some((video) => video.extensionVideoId === selectedExtensionVideoId)
    ) {
      setSelectedExtensionVideoId(extensionVideos[0].extensionVideoId || '');
    } else if (!extensionVideos.length && selectedExtensionVideoId) {
      setSelectedExtensionVideoId('');
    }
  }, [extensionVideos, selectedExtensionVideoId]);

  const selectedPlatforms = useMemo(() => (
    accounts
      .filter((account) => selectedAccountIds.includes(account.id))
      .map((account) => ({ platform: account.platform, accountId: account.id }))
  ), [accounts, selectedAccountIds]);

  const planStats = useMemo(() => {
    const posts = plan?.plannedPosts || [];
    return {
      total: posts.length,
      queued: posts.filter((post) => post.status === 'queued').length,
      generating: posts.filter((post) => post.status === 'generating').length,
      generated: posts.filter((post) => post.status === 'generated' || post.generatedMediaUrl).length,
      scheduled: posts.filter((post) => post.reviewStatus === 'scheduled').length,
      failed: posts.filter((post) => post.status === 'failed').length,
    };
  }, [plan]);
  const generatedUnscheduledPosts = useMemo(() => (
    (plan?.plannedPosts || []).filter((post) => (
      (post.status === 'generated' || post.generatedMediaUrl)
      && post.reviewStatus !== 'scheduled'
    ))
  ), [plan]);
  const planNeedsHookDemo = useMemo(
    () => (plan?.plannedPosts || []).some((post) => post.purpose === 'hook_demo'),
    [plan],
  );
  const selectedModel = useMemo(
    () => models.find((model) => model.modelId === selectedModelId) || null,
    [models, selectedModelId],
  );
  const selectedExtensionVideo = useMemo(
    () => extensionVideos.find((video) => video.extensionVideoId === selectedExtensionVideoId) || null,
    [extensionVideos, selectedExtensionVideoId],
  );
  const canStartGeneration = ['approved', 'generation_dry_run'].includes(plan?.status)
    && Boolean(selectedModelId)
    && (!planNeedsHookDemo || Boolean(selectedExtensionVideoId));

  const handleCreatePlan = async () => {
    setIsCreating(true);
    setError('');
    try {
      const result = await createStudyTokSimplePlan({
        postCount: Number(postCount) || 30,
        relatablePerDay: Number(relatablePerDay) || 3,
        hookDemoPerDay: Number(hookDemoPerDay) || 1,
        startDate,
        dailyTimes,
        timezone,
      });
      setPlan(result);
    } catch (err) {
      setError(err.message || 'Could not create StudyTok plan.');
    } finally {
      setIsCreating(false);
    }
  };

  const handleApprovePlan = async () => {
    if (!plan?.id) return;
    setIsApproving(true);
    setError('');
    try {
      const result = await updateAccountPlan(plan.id, { status: 'approved' });
      setPlan(result);
    } catch (err) {
      setError(err.message || 'Could not approve plan.');
    } finally {
      setIsApproving(false);
    }
  };

  const handleStartGeneration = async () => {
    if (!plan?.id) return;
    setIsStartingGeneration(true);
    setError('');
    try {
      const result = await generateAccountPlanPosts(plan.id, {
        modelId: selectedModelId,
        extensionVideoId: selectedExtensionVideoId,
      });
      setPlan(result);
      if (onGenerationStarted) onGenerationStarted();
    } catch (err) {
      setError(err.message || 'Could not start generation.');
    } finally {
      setIsStartingGeneration(false);
    }
  };

  const handlePatchPost = async (slot, updates) => {
    if (!plan?.id) return;
    const nextPosts = (plan.plannedPosts || []).map((post) => (
      post.slot === slot ? { ...post, ...updates } : post
    ));
    setPlan({ ...plan, plannedPosts: nextPosts });
    try {
      const result = await updateAccountPlanPost({ planId: plan.id, slot, updates });
      setPlan(result);
    } catch (err) {
      setError(err.message || 'Could not update planned post.');
    }
  };

  const handleSwapPost = async (slot) => {
    if (!plan?.id) return;
    setSwappingSlot(slot);
    setError('');
    try {
      const result = await swapAccountPlanPost({ planId: plan.id, slot });
      setPlan(result);
    } catch (err) {
      setError(err.message || 'Could not swap planned video.');
    } finally {
      setSwappingSlot(null);
    }
  };

  const handleSchedulePost = async (post) => {
    if (!plan?.id) return;
    setSchedulingSlot(post.slot);
    setError('');
    try {
      const scheduledIso = toIsoLocal(post.suggestedScheduledFor);
      const payload = {
        sessionId: DEFAULT_SESSION_ID,
        content: post.captionDraft || 'Generated with nflncr.ai',
        platforms: selectedPlatforms,
        publishNow: false,
        timezone,
        scheduledFor: scheduledIso,
        mediaUrls: [post.generatedMediaUrl].filter(Boolean),
        ...(post.jobId ? { jobId: post.jobId, includeResultVideo: true } : {}),
      };
      const result = await createLatePost(payload);
      const latePostId = result?.post?._id || result?._id || result?.id || 'created';
      await handlePatchPost(post.slot, { reviewStatus: 'scheduled', status: 'scheduled', latePostId });
    } catch (err) {
      setError(err.message || 'Could not schedule post.');
    } finally {
      setSchedulingSlot(null);
    }
  };

  const handleScheduleAll = async () => {
    if (!plan?.id) return;
    setIsSchedulingAll(true);
    setError('');
    try {
      const result = await scheduleAccountPlanPosts(plan.id, {
        sessionId: DEFAULT_SESSION_ID,
        platforms: selectedPlatforms,
        timezone,
      });
      setPlan(result.plan || result);
      if (onGenerationStarted) onGenerationStarted();
    } catch (err) {
      setError(err.message || 'Could not schedule generated posts.');
    } finally {
      setIsSchedulingAll(false);
    }
  };

  const updateTime = (idx, value) => {
    setDailyTimes((items) => items.map((item, itemIdx) => (itemIdx === idx ? value : item)));
  };

  return (
    <div className="mx-auto max-w-7xl">
      <section className="overflow-hidden rounded-[2rem] border border-white/10 bg-ink-950 text-white shadow-pill">
        <div className="border-b border-white/10 px-5 py-6 md:px-8">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-white/40">
                StudyTok Planner
              </p>
              <h1 className="mt-3 font-display text-3xl font-medium tracking-tight md:text-5xl">
                3 Relatable + 1 Hook Demo Per Day
              </h1>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-white/60 md:text-base">
                Choose the mix and frequency. The planner auto-selects tagged study videos, orders them, suggests schedule slots, then queues generation for review and publishing.
              </p>
            </div>
            <button
              type="button"
              onClick={refreshPlan}
              disabled={!plan?.id}
              className="inline-flex items-center gap-2 rounded-full bg-white/10 px-4 py-2 text-sm font-semibold text-white/70 transition hover:bg-white/18 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
            >
              <RefreshCw size={16} aria-hidden />
              Refresh
            </button>
          </div>
        </div>

        <div className="grid gap-5 px-5 py-5 md:px-8">
          {error && (
            <div className="flex items-start gap-3 rounded-2xl border border-red-400/25 bg-red-500/10 px-4 py-3 text-sm text-red-100">
              <AlertCircle size={18} className="mt-0.5 shrink-0" aria-hidden />
              <p>{error}</p>
            </div>
          )}

          <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-4">
            <div className="grid gap-3 md:grid-cols-5">
              <label className="grid gap-1 text-xs text-white/45">
                Relatable / day
                <input
                  type="number"
                  min="0"
                  max="12"
                  value={relatablePerDay}
                  onChange={(event) => setRelatablePerDay(event.target.value)}
                  className="rounded-2xl border border-white/10 bg-white/10 px-3 py-2 text-sm font-semibold text-white outline-none"
                />
              </label>
              <label className="grid gap-1 text-xs text-white/45">
                Hook + demo / day
                <input
                  type="number"
                  min="0"
                  max="12"
                  value={hookDemoPerDay}
                  onChange={(event) => setHookDemoPerDay(event.target.value)}
                  className="rounded-2xl border border-white/10 bg-white/10 px-3 py-2 text-sm font-semibold text-white outline-none"
                />
              </label>
              <label className="grid gap-1 text-xs text-white/45">
                Plan size
                <input
                  type="number"
                  min="1"
                  max="60"
                  value={postCount}
                  onChange={(event) => setPostCount(event.target.value)}
                  className="rounded-2xl border border-white/10 bg-white/10 px-3 py-2 text-sm font-semibold text-white outline-none"
                />
              </label>
              <label className="grid gap-1 text-xs text-white/45">
                Start date
                <input
                  type="date"
                  value={startDate}
                  onChange={(event) => setStartDate(event.target.value)}
                  className="rounded-2xl border border-white/10 bg-white/10 px-3 py-2 text-sm font-semibold text-white outline-none"
                />
              </label>
              <button
                type="button"
                onClick={handleCreatePlan}
                disabled={isCreating}
                className="inline-flex items-center justify-center gap-2 rounded-2xl bg-cyan-300 px-4 py-2 text-sm font-semibold text-ink-950 transition hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-50 md:self-end"
              >
                {isCreating ? <Loader2 size={16} className="animate-spin" aria-hidden /> : <Sparkles size={16} aria-hidden />}
                Create plan
              </button>
            </div>

            <div className="mt-4 grid gap-2 sm:grid-cols-4">
              {dailyTimes.map((item, idx) => (
                <label key={`time-${idx}`} className="grid gap-1 text-xs text-white/45">
                  Daily slot {idx + 1}
                  <input
                    type="time"
                    value={item}
                    onChange={(event) => updateTime(idx, event.target.value)}
                    className="rounded-2xl border border-white/10 bg-black/20 px-3 py-2 text-sm font-semibold text-white outline-none"
                  />
                </label>
              ))}
            </div>
          </div>

          {plan && (
            <>
              <div className="grid gap-3 md:grid-cols-3 lg:grid-cols-7">
                {[
                  ['Plan status', tagValue(plan.status)],
                  ['Posts', String(planStats.total)],
                  ['Queued', String(planStats.queued)],
                  ['Generating', String(planStats.generating)],
                  ['Generated', String(planStats.generated)],
                  ['Failed', String(planStats.failed)],
                  ['Scheduled', String(planStats.scheduled)],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-3xl border border-white/10 bg-white/[0.04] p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-white/35">{label}</p>
                    <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
                  </div>
                ))}
              </div>

              <div className="flex flex-wrap items-center justify-between gap-3 rounded-3xl border border-white/10 bg-white/[0.04] p-4">
                <div>
                  <p className="text-sm font-semibold text-white">Approve and generate</p>
                  <p className="mt-1 text-sm text-white/45">
                    Choose the identity model for every post and the demo extension used for hook + demo posts.
                  </p>
                  <p className="mt-1 text-xs text-white/35">
                    Selected: {assetLabel(selectedModel, 'modelId')}
                    {planNeedsHookDemo ? ` + ${assetLabel(selectedExtensionVideo, 'extensionVideoId')}` : ''}
                  </p>
                </div>
                <div className="grid w-full gap-3 lg:grid-cols-[minmax(360px,1fr)_minmax(220px,320px)]">
                  <div className="grid gap-1 text-xs text-white/45">
                    <p>Model</p>
                    <ModelImagePicker
                      models={models}
                      loading={loadingModels}
                      selectedModelId={selectedModelId}
                      onSelect={setSelectedModelId}
                    />
                  </div>
                  <div className="grid gap-1 text-xs text-white/45">
                    <p>Hook + demo extension</p>
                    <ExtensionVideoPicker
                      videos={extensionVideos}
                      loading={loadingExtensionVideos}
                      disabled={!planNeedsHookDemo}
                      selectedVideoId={selectedExtensionVideoId}
                      onSelect={setSelectedExtensionVideoId}
                    />
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={handleApprovePlan}
                    disabled={isApproving || plan.status !== 'draft'}
                    className="inline-flex items-center gap-2 rounded-2xl bg-white/10 px-4 py-2 text-sm font-semibold text-white/70 hover:bg-white/15 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {isApproving ? <Loader2 size={16} className="animate-spin" aria-hidden /> : <CheckCircle2 size={16} aria-hidden />}
                    Approve
                  </button>
                  <button
                    type="button"
                    onClick={handleStartGeneration}
                    disabled={isStartingGeneration || !canStartGeneration}
                    className="inline-flex items-center gap-2 rounded-2xl bg-emerald-300 px-4 py-2 text-sm font-semibold text-ink-950 disabled:cursor-not-allowed disabled:opacity-50"
                    title={!selectedModelId ? 'Select a model first' : planNeedsHookDemo && !selectedExtensionVideoId ? 'Select a hook + demo extension first' : undefined}
                  >
                    {isStartingGeneration ? <Loader2 size={16} className="animate-spin" aria-hidden /> : <PlayCircle size={16} aria-hidden />}
                    Start bulk generation
                  </button>
                </div>
              </div>

              <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-white">Schedule account</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {accounts.length ? accounts.map((account) => {
                        const selected = selectedAccountIds.includes(account.id);
                        return (
                          <button
                            key={account.id}
                            type="button"
                            onClick={() => setSelectedAccountIds((ids) => (
                              selected ? ids.filter((id) => id !== account.id) : [...ids, account.id]
                            ))}
                            className={`rounded-full px-3 py-1.5 text-xs font-semibold transition ${selected ? 'bg-white text-ink-950' : 'bg-white/10 text-white/60 hover:bg-white/15'}`}
                          >
                            {account.platform}
                          </button>
                        );
                      }) : (
                        <span className="text-sm text-white/45">No Late accounts connected yet.</span>
                      )}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={handleScheduleAll}
                    disabled={isSchedulingAll || !selectedPlatforms.length || generatedUnscheduledPosts.length === 0}
                    className="inline-flex items-center gap-2 rounded-2xl bg-emerald-300 px-4 py-2 text-sm font-semibold text-ink-950 disabled:cursor-not-allowed disabled:opacity-50"
                    title={!selectedPlatforms.length ? 'Select a connected account first' : generatedUnscheduledPosts.length === 0 ? 'No generated unscheduled posts ready' : undefined}
                  >
                    {isSchedulingAll ? <Loader2 size={16} className="animate-spin" aria-hidden /> : <CalendarClock size={16} aria-hidden />}
                    Schedule all generated
                  </button>
                </div>
              </div>

              <div className="grid gap-3">
                {(plan.plannedPosts || []).map((post) => (
                  <PostCard
                    key={post.slot}
                    post={post}
                    canSchedule={selectedPlatforms.length > 0 && post.reviewStatus !== 'scheduled'}
                    selectedPlatforms={selectedPlatforms}
                    onPatchPost={handlePatchPost}
                    onSchedulePost={handleSchedulePost}
                    onSwapPost={handleSwapPost}
                    isScheduling={schedulingSlot === post.slot}
                    isSwapping={swappingSlot === post.slot}
                  />
                ))}
              </div>
            </>
          )}
        </div>
      </section>
    </div>
  );
}

export default AccountPlanner;
