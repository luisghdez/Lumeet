import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertCircle, ArrowUpRight, Loader2, RefreshCw, Sparkles, Target, Video } from 'lucide-react';
import {
  createAccountPlan,
  listAccountPlannerArchetypes,
  listOrganizerBatches,
} from '../lib/organizerApi';

function tagValue(value) {
  return value ? String(value).replaceAll('_', ' ') : 'n/a';
}

function formatDuration(seconds) {
  const value = Number(seconds);
  if (!Number.isFinite(value) || value < 0) return 'n/a';
  const mins = Math.floor(value / 60);
  const secs = Math.round(value % 60);
  return mins ? `${mins}:${String(secs).padStart(2, '0')}` : `${secs}s`;
}

function InspoVideoCard({ video }) {
  const tags = video.keyTags || {};
  return (
    <div className="rounded-2xl border border-white/10 bg-black/20 p-3">
      <div className="flex gap-3">
        <a
          href={video.url}
          target="_blank"
          rel="noreferrer"
          className="relative h-24 w-16 shrink-0 overflow-hidden rounded-xl bg-white/10"
        >
          {video.thumbnailUrl ? (
            <img src={video.thumbnailUrl} alt="" className="h-full w-full object-cover" loading="lazy" />
          ) : (
            <div className="flex h-full w-full items-center justify-center text-white/40">
              <Video size={16} aria-hidden />
            </div>
          )}
          <span className="absolute bottom-1 right-1 rounded-full bg-black/70 px-1.5 py-0.5 text-[10px] font-semibold text-white">
            {formatDuration(video.durationSec)}
          </span>
        </a>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <p className="truncate text-xs font-semibold text-white/75">
              @{video.creatorHandle || 'unknown'}
            </p>
            <a href={video.url} target="_blank" rel="noreferrer" className="text-white/45 hover:text-white">
              <ArrowUpRight size={13} aria-hidden />
            </a>
          </div>
          <p className="mt-1 line-clamp-2 text-[11px] leading-4 text-white/45">
            {video.caption || 'No caption returned.'}
          </p>
          <div className="mt-2 flex flex-wrap gap-1">
            {tags.study_content_type && (
              <span className="rounded-full bg-sky-400/15 px-2 py-0.5 text-[10px] font-semibold text-sky-100">
                {tagValue(tags.study_content_type)}
              </span>
            )}
            {tags.primary_product_name && (
              <span className="rounded-full bg-lime-400/15 px-2 py-0.5 text-[10px] font-semibold text-lime-100">
                {tags.primary_product_name}
              </span>
            )}
            {tags.funnel_stage && (
              <span className="rounded-full bg-white/10 px-2 py-0.5 text-[10px] text-white/55">
                {tagValue(tags.funnel_stage)}
              </span>
            )}
          </div>
        </div>
      </div>
      <div className="mt-2 flex flex-wrap gap-1">
        {(video.selectionReasons || []).slice(0, 3).map((reason) => (
          <span key={reason} className="rounded-full bg-white/10 px-2 py-0.5 text-[10px] text-white/45">
            {reason}
          </span>
        ))}
      </div>
    </div>
  );
}

function PlannedPostCard({ post }) {
  const targetTags = post.targetTags || {};
  const targetDuration = post.durationTargetSec || {};
  return (
    <article className="rounded-3xl border border-white/10 bg-white/[0.04] p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-white/35">
            Post {post.slot}
          </p>
          <h3 className="mt-1 font-display text-xl font-medium tracking-tight text-white">
            {post.label || tagValue(post.purpose)}
          </h3>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-white/55">
            {post.creativeNotes}
          </p>
        </div>
        <span className="rounded-full bg-cyan-400/15 px-3 py-1.5 text-xs font-semibold text-cyan-100">
          {formatDuration(targetDuration.min)}-{formatDuration(targetDuration.max)}
        </span>
      </div>

      <div className="mt-4 flex flex-wrap gap-1.5">
        {Object.entries(targetTags).flatMap(([key, values]) => (
          (values || []).map((value) => (
            <span key={`${key}-${value}`} className="rounded-full bg-white/10 px-2 py-1 text-[11px] text-white/55">
              {tagValue(key)}: {tagValue(value)}
            </span>
          ))
        ))}
      </div>

      {post.needsMoreInspo && (
        <div className="mt-4 rounded-2xl border border-amber-300/20 bg-amber-400/10 px-3 py-2 text-xs leading-5 text-amber-100">
          {post.fallbackNote}
        </div>
      )}

      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        {(post.inspoVideos || []).map((video) => (
          <InspoVideoCard key={video.videoReferenceId} video={video} />
        ))}
      </div>
    </article>
  );
}

function AccountPlanner() {
  const [archetypes, setArchetypes] = useState([]);
  const [batches, setBatches] = useState([]);
  const [archetype, setArchetype] = useState('studytok');
  const [batchId, setBatchId] = useState('');
  const [postCount, setPostCount] = useState(10);
  const [plan, setPlan] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState('');

  const loadPlannerData = useCallback(async () => {
    setIsLoading(true);
    setError('');
    try {
      const [archetypeResult, batchResult] = await Promise.all([
        listAccountPlannerArchetypes(),
        listOrganizerBatches({ limit: 100 }),
      ]);
      setArchetypes(archetypeResult.archetypes || []);
      setBatches(batchResult.batches || []);
    } catch (err) {
      setError(err.message || 'Could not load planner data.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPlannerData();
  }, [loadPlannerData]);

  const selectedArchetype = useMemo(() => (
    archetypes.find((item) => item.id === archetype) || archetypes[0]
  ), [archetypes, archetype]);

  const handleGeneratePlan = async () => {
    setIsGenerating(true);
    setError('');
    try {
      const result = await createAccountPlan({ archetype, postCount: Number(postCount) || 10, batchId });
      setPlan(result);
    } catch (err) {
      setError(err.message || 'Could not generate account plan.');
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="mx-auto max-w-7xl">
      <section className="overflow-hidden rounded-[2rem] border border-white/10 bg-ink-950 text-white shadow-pill">
        <div className="border-b border-white/10 px-5 py-6 md:px-8">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-white/40">
                Account Planner
              </p>
              <h1 className="mt-3 font-display text-3xl font-medium tracking-tight md:text-5xl">
                StudyTok First Posts
              </h1>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-white/60 md:text-base">
                Design the first posts of a study influencer account from tagged inspo videos, with every recommendation tied back to references.
              </p>
            </div>
            <button
              type="button"
              onClick={loadPlannerData}
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

          <div className="mb-5 rounded-3xl border border-white/10 bg-white/[0.04] p-4">
            <div className="grid gap-3 md:grid-cols-[1fr_1fr_120px_auto]">
              <label className="grid gap-1 text-xs text-white/45">
                Account type
                <select
                  value={archetype}
                  onChange={(event) => setArchetype(event.target.value)}
                  className="rounded-2xl border border-white/10 bg-white/10 px-3 py-2 text-sm font-semibold text-white outline-none"
                >
                  {(archetypes.length ? archetypes : [{ id: 'studytok', label: 'StudyTok' }]).map((item) => (
                    <option key={item.id} value={item.id}>{item.label}</option>
                  ))}
                </select>
              </label>
              <label className="grid gap-1 text-xs text-white/45">
                Source batch
                <select
                  value={batchId}
                  onChange={(event) => setBatchId(event.target.value)}
                  className="rounded-2xl border border-white/10 bg-white/10 px-3 py-2 text-sm font-semibold text-white outline-none"
                >
                  <option value="">All tagged videos</option>
                  {batches.map((batch) => (
                    <option key={batch.id} value={batch.id}>
                      @{batch.creatorHandle || 'unknown'} · {batch.counts?.aiTagged || 0} tagged
                    </option>
                  ))}
                </select>
              </label>
              <label className="grid gap-1 text-xs text-white/45">
                Posts
                <input
                  type="number"
                  min="1"
                  max="20"
                  value={postCount}
                  onChange={(event) => setPostCount(event.target.value)}
                  className="rounded-2xl border border-white/10 bg-white/10 px-3 py-2 text-sm font-semibold text-white outline-none"
                />
              </label>
              <button
                type="button"
                onClick={handleGeneratePlan}
                disabled={isGenerating}
                className="inline-flex items-center justify-center gap-2 rounded-2xl bg-cyan-300 px-4 py-2 text-sm font-semibold text-ink-950 transition hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-50 md:self-end"
              >
                {isGenerating ? <Loader2 size={16} className="animate-spin" aria-hidden /> : <Sparkles size={16} aria-hidden />}
                Generate plan
              </button>
            </div>
            {selectedArchetype?.description && (
              <p className="mt-3 text-sm leading-6 text-white/45">{selectedArchetype.description}</p>
            )}
          </div>

          {plan && (
            <div className="grid gap-5">
              <div className="grid gap-3 lg:grid-cols-[1.2fr_2fr]">
                <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-4">
                  <div className="flex items-center gap-2 text-white">
                    <Target size={18} aria-hidden />
                    <h2 className="font-display text-xl font-medium tracking-tight">Content Mix</h2>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {(plan.contentMix || []).map((item) => (
                      <span key={item.purpose} className="rounded-full bg-white/10 px-3 py-1.5 text-xs font-semibold text-white/70">
                        {tagValue(item.purpose)} {item.percentage}%
                      </span>
                    ))}
                  </div>
                  <p className="mt-4 text-sm text-white/45">
                    Built from {plan.source?.taggedVideoCount || 0} tagged study videos
                    {plan.source?.batchId ? ` in ${plan.source.batchId}` : ' across all batches'}.
                  </p>
                </div>
                <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-white/35">MVP Logic</p>
                  <p className="mt-2 text-sm leading-6 text-white/55">
                    The planner uses deterministic slot rules over existing tags. It picks references by study type, funnel role, app/product mentions, hook-demo structure, and duration fit.
                  </p>
                </div>
              </div>

              {(plan.plannedPosts || []).map((post) => (
                <PlannedPostCard key={post.slot} post={post} />
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

export default AccountPlanner;
