import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  ArrowLeft,
  ArrowUpRight,
  BarChart3,
  CheckCircle2,
  Clock,
  Loader2,
  PlayCircle,
  RefreshCw,
  ThumbsDown,
  ThumbsUp,
  Video,
} from 'lucide-react';
import {
  analyzeOrganizerBatch,
  analyzeVideoReference,
  getOrganizerBatch,
  listOrganizerBatches,
  updateVideoReviewStatus,
} from '../lib/organizerApi';

const REVIEW_ACTIONS = [
  { id: 'approved', label: 'Approve', icon: ThumbsUp },
  { id: 'rejected', label: 'Reject', icon: ThumbsDown },
  { id: 'saved_hook_only', label: 'Hook only', icon: CheckCircle2 },
  { id: 'saved_format_only', label: 'Format only', icon: CheckCircle2 },
  { id: 'needs_deep_analysis', label: 'Deep analysis', icon: Clock },
];

function formatDate(raw) {
  if (!raw && raw !== 0) return 'n/a';
  const date = typeof raw === 'number' ? new Date(raw * 1000) : new Date(raw);
  if (Number.isNaN(date.getTime())) return String(raw);
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

function formatNumber(value) {
  if (value === null || value === undefined || value === '') return '0';
  const num = Number(value);
  if (Number.isNaN(num)) return '0';
  return Intl.NumberFormat(undefined, { notation: num >= 10000 ? 'compact' : 'standard' }).format(num);
}

function formatDuration(seconds) {
  const value = Number(seconds);
  if (!Number.isFinite(value) || value <= 0) return 'n/a';
  const mins = Math.floor(value / 60);
  const secs = Math.round(value % 60);
  return mins ? `${mins}:${String(secs).padStart(2, '0')}` : `${secs}s`;
}

function statusLabel(value) {
  return String(value || 'pending').replaceAll('_', ' ');
}

function tagValue(value) {
  return value ? statusLabel(value) : 'n/a';
}

function metricValue(value) {
  if (value === null || value === undefined || value === '') return 'n/a';
  const num = Number(value);
  if (Number.isNaN(num)) return String(value);
  return num % 1 === 0 ? String(num) : num.toFixed(2);
}

function getVideoTags(video) {
  return video?.aiTag?.normalizedTags || {};
}

function summarizeByTag(videos, tagKey) {
  const total = videos.length || 1;
  const counts = {};
  for (const video of videos) {
    const value = getVideoTags(video)[tagKey] || 'untagged';
    counts[value] = (counts[value] || 0) + 1;
  }
  return Object.entries(counts)
    .map(([id, count]) => ({ id, count, percentage: Math.round((count / total) * 100) }))
    .sort((a, b) => b.count - a.count);
}

function BatchCard({ batch, onOpen }) {
  const counts = batch.counts || {};
  return (
    <button
      type="button"
      onClick={() => onOpen(batch.id)}
      className="w-full rounded-3xl border border-white/10 bg-white/[0.04] p-5 text-left text-white transition hover:-translate-y-0.5 hover:bg-white/[0.07]"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-white/40">
            Source batch
          </p>
          <h3 className="mt-2 truncate font-display text-xl font-medium tracking-tight">
            @{batch.creatorHandle || 'unknown'}
          </h3>
          <p className="mt-1 text-sm text-white/45">{formatDate(batch.createdAt)}</p>
        </div>
        <span className="rounded-full bg-emerald-400/15 px-3 py-1.5 text-xs font-semibold text-emerald-200">
          {batch.status || 'imported'}
        </span>
      </div>
      <div className="mt-5 grid grid-cols-3 gap-2">
        <div className="rounded-2xl bg-black/20 p-3">
          <p className="text-[11px] uppercase tracking-[0.14em] text-white/35">Videos</p>
          <p className="mt-1 text-lg font-semibold">{formatNumber(counts.total)}</p>
        </div>
        <div className="rounded-2xl bg-black/20 p-3">
          <p className="text-[11px] uppercase tracking-[0.14em] text-white/35">Tagged</p>
          <p className="mt-1 text-lg font-semibold">{formatNumber(counts.aiTagged)}</p>
        </div>
        <div className="rounded-2xl bg-black/20 p-3">
          <p className="text-[11px] uppercase tracking-[0.14em] text-white/35">Failed</p>
          <p className="mt-1 text-lg font-semibold">{formatNumber(counts.failed)}</p>
        </div>
      </div>
      {batch.nicheHint && (
        <p className="mt-4 rounded-full bg-white/10 px-3 py-1.5 text-xs text-white/60">
          Niche: {batch.nicheHint}
        </p>
      )}
    </button>
  );
}

function BatchVideoRow({ video, onReview, onAnalyze, isUpdating, isAnalyzing }) {
  const metrics = video.metrics || {};
  const aiTag = video.aiTag || {};
  const tags = aiTag.normalizedTags || {};
  const motion = aiTag.motionMetrics || {};
  const analysisStatus = aiTag.status || video.aiTagStatus || 'not_tagged';
  const isTagged = analysisStatus === 'tagged';
  const isFailed = analysisStatus === 'tag_failed';
  return (
    <div className="grid gap-4 border-t border-white/10 px-4 py-4 first:border-t-0 xl:grid-cols-[84px_minmax(0,1fr)_300px]">
      <a
        href={video.url}
        target="_blank"
        rel="noreferrer"
        className="relative h-28 overflow-hidden rounded-2xl bg-white/10"
      >
        {video.thumbnailUrl ? (
          <img src={video.thumbnailUrl} alt="" className="h-full w-full object-cover" loading="lazy" />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-white/40">
            <Video size={20} aria-hidden />
          </div>
        )}
        <span className="absolute bottom-2 right-2 rounded-full bg-black/70 px-2 py-1 text-[11px] font-semibold text-white">
          {formatDuration(video.durationSec)}
        </span>
      </a>
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-white/10 px-2.5 py-1 text-[11px] font-semibold text-white/55">
            {statusLabel(video.approvalStatus)}
          </span>
          <span className="rounded-full bg-purple-400/15 px-2.5 py-1 text-[11px] font-semibold text-purple-100">
            AI: {statusLabel(analysisStatus)}
          </span>
          <span className="text-xs text-white/40">{formatDate(video.postedAt)}</span>
        </div>
        <p className="mt-2 line-clamp-2 text-sm leading-6 text-white/70">
          {video.caption || 'No caption returned.'}
        </p>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {(video.hashtags || []).slice(0, 7).map((tag) => (
            <span key={tag} className="rounded-full bg-white/10 px-2 py-1 text-xs text-white/55">
              #{tag}
            </span>
          ))}
        </div>
        <div className="mt-3 flex items-center gap-2 text-xs text-white/45">
          <span>{formatNumber(metrics.views)} views</span>
          <span>{formatNumber(metrics.likes)} likes</span>
          <a href={video.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-white/70 hover:text-white">
            Open <ArrowUpRight size={13} aria-hidden />
          </a>
        </div>
        {(isTagged || isFailed) && (
          <div className="mt-3 rounded-2xl border border-white/10 bg-white/[0.04] p-3">
            {isFailed ? (
              <p className="text-xs leading-5 text-red-100/80">
                Analysis failed: {aiTag.error || 'Unknown error'}
              </p>
            ) : (
              <>
                <div className="flex flex-wrap gap-1.5">
                  <span className="rounded-full bg-cyan-400/15 px-2 py-1 text-[11px] font-semibold text-cyan-100">
                    {tagValue(tags.niche)} / {tagValue(tags.sub_niche)}
                  </span>
                  <span className="rounded-full bg-white/10 px-2 py-1 text-[11px] text-white/65">
                    Format: {tagValue(tags.format)}
                  </span>
                  <span className="rounded-full bg-white/10 px-2 py-1 text-[11px] text-white/65">
                    Hook: {tagValue(tags.hook_type)}
                  </span>
                  <span className="rounded-full bg-white/10 px-2 py-1 text-[11px] text-white/65">
                    Camera: {tagValue(tags.camera_movement)}
                  </span>
                  <span className="rounded-full bg-white/10 px-2 py-1 text-[11px] text-white/65">
                    Motion: {tagValue(tags.motion_difficulty)}
                  </span>
                  <span className="rounded-full bg-amber-400/15 px-2 py-1 text-[11px] font-semibold text-amber-100">
                    Pillar: {tagValue(tags.content_pillar)}
                  </span>
                  <span className="rounded-full bg-white/10 px-2 py-1 text-[11px] text-white/65">
                    Funnel: {tagValue(tags.funnel_stage)}
                  </span>
                  <span className="rounded-full bg-white/10 px-2 py-1 text-[11px] text-white/65">
                    Use: {tagValue(tags.campaign_use)}
                  </span>
                  <span className="rounded-full bg-white/10 px-2 py-1 text-[11px] text-white/65">
                    Product: {tagValue(tags.product_integration_type)}
                  </span>
                  <span className="rounded-full bg-white/10 px-2 py-1 text-[11px] text-white/65">
                    Template: {tagValue(tags.creative_template)}
                  </span>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4">
                  <div className="rounded-xl bg-black/20 p-2">
                    <p className="text-[10px] uppercase tracking-[0.12em] text-white/35">Frames</p>
                    <p className="mt-0.5 text-xs font-semibold text-white">{metricValue(motion.estimated_total_frame_count)}</p>
                  </div>
                  <div className="rounded-xl bg-black/20 p-2">
                    <p className="text-[10px] uppercase tracking-[0.12em] text-white/35">Scenes</p>
                    <p className="mt-0.5 text-xs font-semibold text-white">{metricValue(motion.scene_count)}</p>
                  </div>
                  <div className="rounded-xl bg-black/20 p-2">
                    <p className="text-[10px] uppercase tracking-[0.12em] text-white/35">Movement</p>
                    <p className="mt-0.5 text-xs font-semibold text-white">{metricValue(motion.total_frame_movement)}</p>
                  </div>
                  <div className="rounded-xl bg-black/20 p-2">
                    <p className="text-[10px] uppercase tracking-[0.12em] text-white/35">Character</p>
                    <p className="mt-0.5 text-xs font-semibold text-white">{metricValue(motion.character_movement_score)}</p>
                  </div>
                </div>
                {motion.first_two_scene_similarity_score !== undefined && motion.first_two_scene_similarity_score !== null && (
                  <div className="mt-2 rounded-xl bg-black/20 p-2">
                    <p className="text-[10px] uppercase tracking-[0.12em] text-white/35">Scene similarity</p>
                    <p className="mt-0.5 text-xs font-semibold text-white">
                      Avg {metricValue(motion.average_adjacent_scene_similarity_score)}
                      {motion.lowest_adjacent_scene_similarity_score !== undefined && motion.lowest_adjacent_scene_similarity_score !== null
                        ? ` · Low ${metricValue(motion.lowest_adjacent_scene_similarity_score)}`
                        : ''}
                    </p>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {(motion.scene_similarity_pairs || []).slice(0, 6).map((pair) => (
                        <span
                          key={`${pair.from_scene}-${pair.to_scene}`}
                          className="rounded-full bg-white/10 px-2 py-0.5 text-[11px] text-white/50"
                        >
                          {`${pair.from_scene}->${pair.to_scene}: ${metricValue(pair.similarity_score)}`}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>
      <div className="grid grid-cols-2 gap-2 self-start">
        <button
          type="button"
          onClick={() => onAnalyze(video.id)}
          disabled={isAnalyzing}
          className="col-span-2 inline-flex items-center justify-center gap-2 rounded-full bg-cyan-300 px-3 py-2 text-xs font-semibold text-ink-950 transition hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-45"
        >
          {isAnalyzing ? <Loader2 size={13} className="animate-spin" aria-hidden /> : <BarChart3 size={13} aria-hidden />}
          {isAnalyzing ? 'Analyzing...' : isFailed ? 'Retry analysis' : 'Analyze'}
        </button>
        {REVIEW_ACTIONS.map((action) => {
          const Icon = action.icon;
          const selected = video.approvalStatus === action.id;
          return (
            <button
              key={action.id}
              type="button"
              onClick={() => onReview(video.id, action.id)}
              disabled={isUpdating}
              className={`inline-flex items-center justify-center gap-2 rounded-full px-3 py-2 text-xs font-semibold transition ${
                selected
                  ? 'bg-white text-ink-950'
                  : 'bg-white/10 text-white/65 hover:bg-white/18 hover:text-white'
              } disabled:cursor-not-allowed disabled:opacity-45`}
            >
              <Icon size={13} aria-hidden />
              {action.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function OrganizerBatches({ initialBatchId = '', onClearInitialBatch }) {
  const [batches, setBatches] = useState([]);
  const [selectedBatchId, setSelectedBatchId] = useState(initialBatchId || '');
  const [selectedBatch, setSelectedBatch] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingBatch, setIsLoadingBatch] = useState(false);
  const [updatingVideoId, setUpdatingVideoId] = useState('');
  const [analyzingVideoId, setAnalyzingVideoId] = useState('');
  const [isAnalyzingBatch, setIsAnalyzingBatch] = useState(false);
  const [batchAnalyzeLimit, setBatchAnalyzeLimit] = useState(5);
  const [pillarFilter, setPillarFilter] = useState('all');
  const [funnelFilter, setFunnelFilter] = useState('all');
  const [error, setError] = useState('');

  const loadBatches = useCallback(async () => {
    setIsLoading(true);
    setError('');
    try {
      const result = await listOrganizerBatches({ limit: 50 });
      setBatches(result.batches || []);
    } catch (err) {
      setError(err.message || 'Could not load batches.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const loadBatch = useCallback(async (batchId) => {
    if (!batchId) return;
    setIsLoadingBatch(true);
    setError('');
    try {
      const result = await getOrganizerBatch(batchId);
      setSelectedBatch(result);
      setSelectedBatchId(batchId);
    } catch (err) {
      setError(err.message || 'Could not load batch.');
    } finally {
      setIsLoadingBatch(false);
    }
  }, []);

  useEffect(() => {
    loadBatches();
  }, [loadBatches]);

  useEffect(() => {
    if (initialBatchId) {
      loadBatch(initialBatchId);
      if (onClearInitialBatch) onClearInitialBatch();
    }
  }, [initialBatchId, loadBatch, onClearInitialBatch]);

  const counts = selectedBatch?.counts || {};
  const approvalCounts = useMemo(() => {
    const tally = {};
    for (const video of selectedBatch?.videos || []) {
      const status = video.approvalStatus || 'pending';
      tally[status] = (tally[status] || 0) + 1;
    }
    return tally;
  }, [selectedBatch]);

  const selectedVideos = selectedBatch?.videos || [];
  const availablePillars = useMemo(() => (
    [...new Set(selectedVideos.map((video) => getVideoTags(video).content_pillar).filter(Boolean))].sort()
  ), [selectedVideos]);
  const availableFunnels = useMemo(() => (
    [...new Set(selectedVideos.map((video) => getVideoTags(video).funnel_stage).filter(Boolean))].sort()
  ), [selectedVideos]);
  const filteredVideos = useMemo(() => (
    selectedVideos.filter((video) => {
      const tags = getVideoTags(video);
      const pillarOk = pillarFilter === 'all' || tags.content_pillar === pillarFilter;
      const funnelOk = funnelFilter === 'all' || tags.funnel_stage === funnelFilter;
      return pillarOk && funnelOk;
    })
  ), [selectedVideos, pillarFilter, funnelFilter]);
  const contentPillarMix = useMemo(() => summarizeByTag(selectedVideos, 'content_pillar'), [selectedVideos]);
  const funnelMix = useMemo(() => summarizeByTag(selectedVideos, 'funnel_stage'), [selectedVideos]);

  const handleReview = async (videoReferenceId, approvalStatus) => {
    setUpdatingVideoId(videoReferenceId);
    setError('');
    try {
      const updated = await updateVideoReviewStatus({ videoReferenceId, approvalStatus });
      setSelectedBatch((current) => {
        if (!current) return current;
        return {
          ...current,
          videos: (current.videos || []).map((video) => (
            video.id === updated.id ? { ...video, ...updated } : video
          )),
        };
      });
    } catch (err) {
      setError(err.message || 'Could not update review status.');
    } finally {
      setUpdatingVideoId('');
    }
  };

  const replaceVideoAnalysis = (videoReferenceId, analysis) => {
    setSelectedBatch((current) => {
      if (!current) return current;
      return {
        ...current,
        videos: (current.videos || []).map((video) => (
          video.id === videoReferenceId
            ? { ...video, aiTagStatus: analysis.status, aiTag: analysis }
            : video
        )),
      };
    });
  };

  const handleAnalyzeVideo = async (videoReferenceId) => {
    setAnalyzingVideoId(videoReferenceId);
    setError('');
    try {
      const analysis = await analyzeVideoReference(videoReferenceId);
      replaceVideoAnalysis(videoReferenceId, analysis);
      if (selectedBatchId) loadBatch(selectedBatchId);
    } catch (err) {
      setError(err.message || 'Could not analyze video.');
      if (selectedBatchId) loadBatch(selectedBatchId);
    } finally {
      setAnalyzingVideoId('');
    }
  };

  const handleAnalyzeBatch = async () => {
    if (!selectedBatch?.id) return;
    setIsAnalyzingBatch(true);
    setError('');
    try {
      const result = await analyzeOrganizerBatch({
        batchId: selectedBatch.id,
        limit: Number(batchAnalyzeLimit) || 5,
        retryFailed: true,
      });
      setSelectedBatch(result.batch);
      loadBatches();
    } catch (err) {
      setError(err.message || 'Could not analyze batch.');
      loadBatch(selectedBatch.id);
    } finally {
      setIsAnalyzingBatch(false);
    }
  };

  return (
    <div className="mx-auto max-w-7xl">
      <section className="overflow-hidden rounded-[2rem] border border-white/10 bg-ink-950 text-white shadow-pill">
        <div className="border-b border-white/10 px-5 py-6 md:px-8">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-white/40">
                Bulk Video Organizer
              </p>
              <h1 className="mt-3 font-display text-3xl font-medium tracking-tight md:text-5xl">
                Source Batches
              </h1>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-white/60 md:text-base">
                Review imported TikTok URLs, track processing progress, and mark which creative references are worth keeping.
              </p>
            </div>
            <button
              type="button"
              onClick={loadBatches}
              className="inline-flex items-center gap-2 rounded-full bg-white/10 px-4 py-2 text-sm font-semibold text-white/70 transition hover:bg-white/18 hover:text-white"
            >
              {isLoading ? <Loader2 size={16} className="animate-spin" aria-hidden /> : <RefreshCw size={16} aria-hidden />}
              Refresh
            </button>
          </div>
        </div>

        <div className="px-5 py-5 md:px-8">
          {error && (
            <div className="mb-5 flex items-start gap-3 rounded-2xl border border-red-400/25 bg-red-500/10 px-4 py-3 text-sm text-red-100">
              <AlertCircle size={18} className="mt-0.5 shrink-0" aria-hidden />
              <p>{error}</p>
            </div>
          )}

          {selectedBatch ? (
            <div>
              <button
                type="button"
                onClick={() => {
                  setSelectedBatch(null);
                  setSelectedBatchId('');
                }}
                className="mb-5 inline-flex items-center gap-2 rounded-full bg-white/10 px-4 py-2 text-sm font-semibold text-white/70 transition hover:bg-white/18 hover:text-white"
              >
                <ArrowLeft size={16} aria-hidden />
                All batches
              </button>

              <div className="mb-5 grid gap-3 md:grid-cols-4">
                <div className="rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3">
                  <p className="text-xs uppercase tracking-[0.16em] text-white/35">Total</p>
                  <p className="mt-1 text-2xl font-semibold">{formatNumber(counts.total)}</p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3">
                  <p className="text-xs uppercase tracking-[0.16em] text-white/35">Imported</p>
                  <p className="mt-1 text-2xl font-semibold">{formatNumber(counts.imported)}</p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3">
                  <p className="text-xs uppercase tracking-[0.16em] text-white/35">Approved</p>
                  <p className="mt-1 text-2xl font-semibold">{formatNumber(approvalCounts.approved)}</p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3">
                  <p className="text-xs uppercase tracking-[0.16em] text-white/35">Needs deep analysis</p>
                  <p className="mt-1 text-2xl font-semibold">{formatNumber(approvalCounts.needs_deep_analysis)}</p>
                </div>
              </div>

              <div className="mb-5 grid gap-3 lg:grid-cols-2">
                <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-white/35">
                    Content Pillar Mix
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {contentPillarMix.slice(0, 6).map((item) => (
                      <span key={item.id} className="rounded-full bg-amber-400/15 px-3 py-1.5 text-xs font-semibold text-amber-100">
                        {tagValue(item.id)} {item.percentage}%
                      </span>
                    ))}
                  </div>
                </div>
                <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-white/35">
                    Funnel Mix
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {funnelMix.slice(0, 6).map((item) => (
                      <span key={item.id} className="rounded-full bg-cyan-400/15 px-3 py-1.5 text-xs font-semibold text-cyan-100">
                        {tagValue(item.id)} {item.percentage}%
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              <div className="overflow-hidden rounded-3xl border border-white/10 bg-black/20">
                <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-4">
                  <div>
                    <h2 className="font-display text-xl font-medium tracking-tight">
                      @{selectedBatch.creatorHandle || 'unknown'}
                    </h2>
                    <p className="mt-1 text-sm text-white/45">
                      {selectedBatch.id} · {selectedBatch.nicheHint || 'No niche hint'}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <select
                      value={pillarFilter}
                      onChange={(event) => setPillarFilter(event.target.value)}
                      className="rounded-full border border-white/10 bg-white/10 px-3 py-2 text-xs font-semibold text-white/70 outline-none"
                    >
                      <option value="all">All pillars</option>
                      {availablePillars.map((pillar) => (
                        <option key={pillar} value={pillar}>{tagValue(pillar)}</option>
                      ))}
                    </select>
                    <select
                      value={funnelFilter}
                      onChange={(event) => setFunnelFilter(event.target.value)}
                      className="rounded-full border border-white/10 bg-white/10 px-3 py-2 text-xs font-semibold text-white/70 outline-none"
                    >
                      <option value="all">All funnel</option>
                      {availableFunnels.map((funnel) => (
                        <option key={funnel} value={funnel}>{tagValue(funnel)}</option>
                      ))}
                    </select>
                    <label className="flex items-center gap-2 rounded-full bg-white/10 px-3 py-2 text-xs text-white/55">
                      Limit
                      <input
                        type="number"
                        min="1"
                        max="25"
                        value={batchAnalyzeLimit}
                        onChange={(event) => setBatchAnalyzeLimit(event.target.value)}
                        className="w-12 bg-transparent text-white outline-none"
                      />
                    </label>
                    <button
                      type="button"
                      onClick={handleAnalyzeBatch}
                      disabled={isAnalyzingBatch}
                      className="inline-flex items-center gap-2 rounded-full bg-cyan-300 px-4 py-2 text-xs font-semibold text-ink-950 transition hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-45"
                    >
                      {isAnalyzingBatch ? <Loader2 size={14} className="animate-spin" aria-hidden /> : <PlayCircle size={14} aria-hidden />}
                      {isAnalyzingBatch ? 'Analyzing batch...' : 'Analyze batch'}
                    </button>
                    {isLoadingBatch && <Loader2 size={18} className="animate-spin text-white/50" aria-hidden />}
                  </div>
                </div>
                {filteredVideos.map((video) => (
                  <BatchVideoRow
                    key={video.id}
                    video={video}
                    onReview={handleReview}
                    onAnalyze={handleAnalyzeVideo}
                    isUpdating={updatingVideoId === video.id}
                    isAnalyzing={analyzingVideoId === video.id}
                  />
                ))}
              </div>
            </div>
          ) : (
            <div>
              {isLoading && batches.length === 0 ? (
                <div className="flex items-center justify-center rounded-3xl border border-white/10 bg-white/[0.04] py-16 text-white/50">
                  <Loader2 size={22} className="mr-2 animate-spin" aria-hidden />
                  Loading batches...
                </div>
              ) : batches.length > 0 ? (
                <div className="grid gap-4 lg:grid-cols-2">
                  {batches.map((batch) => (
                    <BatchCard key={batch.id} batch={batch} onOpen={loadBatch} />
                  ))}
                </div>
              ) : (
                <div className="rounded-3xl border border-white/10 bg-white/[0.04] px-6 py-12 text-center">
                  <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-white/10 text-white">
                    <Video size={24} aria-hidden />
                  </div>
                  <h3 className="mt-5 font-display text-xl font-medium tracking-tight">
                    No source batches yet
                  </h3>
                  <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-white/60">
                    Import a TikTok account, then create a source batch from the extracted videos.
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

export default OrganizerBatches;
