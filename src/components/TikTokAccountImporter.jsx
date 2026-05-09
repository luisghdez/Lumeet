import React, { useMemo, useState } from 'react';
import {
  AlertCircle,
  ArrowUpRight,
  CheckCircle2,
  Clipboard,
  Loader2,
  PackagePlus,
  Search,
  Sparkles,
  Video,
} from 'lucide-react';
import { createBatchFromTikTokScan, scanTikTokAccount } from '../lib/organizerApi';

function formatNumber(value) {
  if (value === null || value === undefined || value === '') return 'n/a';
  const num = Number(value);
  if (Number.isNaN(num)) return 'n/a';
  return Intl.NumberFormat(undefined, { notation: num >= 10000 ? 'compact' : 'standard' }).format(num);
}

function formatDuration(seconds) {
  const value = Number(seconds);
  if (!Number.isFinite(value) || value <= 0) return 'n/a';
  const mins = Math.floor(value / 60);
  const secs = Math.round(value % 60);
  return mins ? `${mins}:${String(secs).padStart(2, '0')}` : `${secs}s`;
}

function formatDate(raw) {
  if (!raw && raw !== 0) return 'n/a';
  const date = typeof raw === 'number' ? new Date(raw * 1000) : new Date(raw);
  if (Number.isNaN(date.getTime())) return String(raw);
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

function normalizeAccountInput(value) {
  return value.trim();
}

function EmptyState() {
  return (
    <div className="rounded-3xl border border-white/10 bg-white/[0.04] px-6 py-12 text-center">
      <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-white/10 text-white">
        <Video size={24} aria-hidden />
      </div>
      <h3 className="mt-5 font-display text-xl font-medium tracking-tight text-white">
        Drop in a TikTok account to extract videos
      </h3>
      <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-white/60">
        Phase 1 stores public metadata only: URLs, creator, captions, hashtags, duration, thumbnails, and basic metrics.
      </p>
    </div>
  );
}

function VideoRow({ video, onCopy }) {
  const metrics = video.metrics || {};
  return (
    <div className="grid gap-4 border-t border-white/10 px-4 py-4 first:border-t-0 lg:grid-cols-[88px_minmax(0,1fr)_220px]">
      <a
        href={video.url}
        target="_blank"
        rel="noreferrer"
        className="group relative h-32 overflow-hidden rounded-2xl bg-white/10 lg:h-28"
      >
        {video.thumbnailUrl ? (
          <img
            src={video.thumbnailUrl}
            alt=""
            className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
            loading="lazy"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-white/40">
            <Video size={22} aria-hidden />
          </div>
        )}
        <span className="absolute bottom-2 right-2 rounded-full bg-black/70 px-2 py-1 text-[11px] font-semibold text-white">
          {formatDuration(video.durationSec)}
        </span>
      </a>

      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-emerald-400/15 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-emerald-200">
            TikTok
          </span>
          <span className="truncate text-sm font-semibold text-white">
            @{video.creatorHandle || 'unknown'}
          </span>
          <span className="text-xs text-white/45">{formatDate(video.postedAt)}</span>
        </div>
        <p className="mt-2 line-clamp-2 text-sm leading-6 text-white/70">
          {video.caption || 'No caption returned by provider.'}
        </p>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {(video.hashtags || []).slice(0, 8).map((tag) => (
            <span key={tag} className="rounded-full bg-white/10 px-2.5 py-1 text-xs text-white/65">
              #{tag}
            </span>
          ))}
          {(video.hashtags || []).length === 0 && (
            <span className="text-xs text-white/35">No hashtags</span>
          )}
        </div>
        <div className="mt-3 flex min-w-0 items-center gap-2">
          <code className="truncate rounded-full bg-black/30 px-3 py-1.5 text-xs text-white/55">
            {video.url}
          </code>
          <button
            type="button"
            onClick={() => onCopy(video.url)}
            className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/10 text-white/65 transition-colors hover:bg-white/20 hover:text-white"
            aria-label="Copy video URL"
            title="Copy URL"
          >
            <Clipboard size={14} aria-hidden />
          </button>
          <a
            href={video.url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/10 text-white/65 transition-colors hover:bg-white/20 hover:text-white"
            aria-label="Open video"
            title="Open video"
          >
            <ArrowUpRight size={14} aria-hidden />
          </a>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-2 rounded-2xl bg-white/[0.04] p-3 text-center lg:grid-cols-2">
        <div>
          <p className="text-[11px] uppercase tracking-[0.14em] text-white/35">Views</p>
          <p className="mt-1 text-sm font-semibold text-white">{formatNumber(metrics.views)}</p>
        </div>
        <div>
          <p className="text-[11px] uppercase tracking-[0.14em] text-white/35">Likes</p>
          <p className="mt-1 text-sm font-semibold text-white">{formatNumber(metrics.likes)}</p>
        </div>
        <div>
          <p className="text-[11px] uppercase tracking-[0.14em] text-white/35">Comments</p>
          <p className="mt-1 text-sm font-semibold text-white">{formatNumber(metrics.comments)}</p>
        </div>
        <div>
          <p className="text-[11px] uppercase tracking-[0.14em] text-white/35">Shares</p>
          <p className="mt-1 text-sm font-semibold text-white">{formatNumber(metrics.shares)}</p>
        </div>
      </div>
    </div>
  );
}

function TikTokAccountImporter({ onBatchCreated }) {
  const [account, setAccount] = useState('');
  const [maxItems, setMaxItems] = useState(30);
  const [nicheHint, setNicheHint] = useState('');
  const [scan, setScan] = useState(null);
  const [error, setError] = useState('');
  const [statusMessage, setStatusMessage] = useState('');
  const [isScanning, setIsScanning] = useState(false);
  const [isCreatingBatch, setIsCreatingBatch] = useState(false);

  const videos = scan?.videos || [];
  const canSubmit = normalizeAccountInput(account).length > 0 && !isScanning;
  const summary = useMemo(() => {
    if (!scan) return null;
    const counts = scan.counts || {};
    return [
      { label: 'Videos', value: counts.videos ?? videos.length },
      { label: 'Provider rows', value: counts.providerItems ?? videos.length },
      { label: 'Duplicates removed', value: counts.duplicatesRemoved ?? 0 },
    ];
  }, [scan, videos.length]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    const input = normalizeAccountInput(account);
    if (!input) return;

    setIsScanning(true);
    setError('');
    setStatusMessage('');
    try {
      const result = await scanTikTokAccount({ account: input, maxItems: Number(maxItems) || 30 });
      setScan(result);
      setStatusMessage(`Extracted ${result.videos?.length || 0} videos from @${result.creatorHandle}.`);
    } catch (err) {
      setError(err.message || 'TikTok scan failed.');
    } finally {
      setIsScanning(false);
    }
  };

  const handleCopy = async (url) => {
    try {
      await navigator.clipboard.writeText(url);
      setStatusMessage('Video URL copied.');
    } catch {
      setStatusMessage('Could not copy automatically. Open the video and copy from the browser.');
    }
  };

  const handleCreateBatch = async () => {
    if (!scan?.scanId || videos.length === 0) return;
    setIsCreatingBatch(true);
    setError('');
    setStatusMessage('');
    try {
      const batch = await createBatchFromTikTokScan({ scanId: scan.scanId, nicheHint });
      setStatusMessage(`Created source batch with ${batch.videos?.length || batch.counts?.total || 0} videos.`);
      if (onBatchCreated) onBatchCreated(batch);
    } catch (err) {
      setError(err.message || 'Could not create source batch.');
    } finally {
      setIsCreatingBatch(false);
    }
  };

  return (
    <div className="mx-auto max-w-7xl">
      <section className="overflow-hidden rounded-[2rem] border border-white/10 bg-ink-950 text-white shadow-pill">
        <div className="relative overflow-hidden border-b border-white/10 px-5 py-6 md:px-8 md:py-8">
          <div className="absolute -right-24 -top-24 h-72 w-72 rounded-full bg-purple-500/20 blur-3xl" />
          <div className="absolute -bottom-32 left-24 h-72 w-72 rounded-full bg-cyan-400/10 blur-3xl" />
          <div className="relative grid gap-6 lg:grid-cols-[minmax(0,1fr)_420px] lg:items-end">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/10 px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.18em] text-white/70">
                <Sparkles size={14} aria-hidden />
                Bulk Video Organizer
              </div>
              <h1 className="mt-5 font-display text-3xl font-medium tracking-tight text-white md:text-5xl">
                TikTok Account Import
              </h1>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-white/60 md:text-base">
                Extract public video references from one TikTok account. This cheap-first pass saves metadata and URLs only, ready for later batching and AI tagging.
              </p>
            </div>

            <form onSubmit={handleSubmit} className="rounded-3xl border border-white/10 bg-white/[0.06] p-4 backdrop-blur">
              <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-white/45">
                TikTok account
              </label>
              <div className="mt-2 flex gap-2">
                <input
                  value={account}
                  onChange={(event) => setAccount(event.target.value)}
                  placeholder="@creator or https://www.tiktok.com/@creator"
                  className="min-w-0 flex-1 rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-sm text-white placeholder-white/30 outline-none transition focus:border-white/25 focus:ring-2 focus:ring-white/10"
                />
              </div>
              <div className="mt-4 grid grid-cols-[120px_minmax(0,1fr)] gap-3">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-white/45">
                    Max videos
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="100"
                    value={maxItems}
                    onChange={(event) => setMaxItems(event.target.value)}
                    className="mt-2 w-full rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-sm text-white outline-none transition focus:border-white/25 focus:ring-2 focus:ring-white/10"
                  />
                </div>
                <button
                  type="submit"
                  disabled={!canSubmit}
                  className="mt-6 inline-flex items-center justify-center gap-2 rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-ink-950 transition-transform hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-45 disabled:hover:translate-y-0"
                >
                  {isScanning ? <Loader2 size={17} className="animate-spin" aria-hidden /> : <Search size={17} aria-hidden />}
                  {isScanning ? 'Scanning...' : 'Extract videos'}
                </button>
              </div>
              <label className="mt-4 block text-xs font-semibold uppercase tracking-[0.16em] text-white/45">
                Niche hint
              </label>
              <input
                value={nicheHint}
                onChange={(event) => setNicheHint(event.target.value)}
                placeholder="e.g. beauty, health, creator tools"
                className="mt-2 w-full rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-sm text-white placeholder-white/30 outline-none transition focus:border-white/25 focus:ring-2 focus:ring-white/10"
              />
              <p className="mt-3 text-xs leading-5 text-white/40">
                Requires `APIFY_TOKEN` in `backend/.env`. No full video files are downloaded.
              </p>
            </form>
          </div>
        </div>

        <div className="px-5 py-5 md:px-8">
          {error && (
            <div className="mb-5 flex items-start gap-3 rounded-2xl border border-red-400/25 bg-red-500/10 px-4 py-3 text-sm text-red-100">
              <AlertCircle size={18} className="mt-0.5 shrink-0" aria-hidden />
              <div>
                <p className="font-semibold">Scan failed</p>
                <p className="mt-1 text-red-100/80">{error}</p>
              </div>
            </div>
          )}

          {statusMessage && !error && (
            <div className="mb-5 flex items-center gap-3 rounded-2xl border border-emerald-400/20 bg-emerald-400/10 px-4 py-3 text-sm text-emerald-100">
              <CheckCircle2 size={18} aria-hidden />
              {statusMessage}
            </div>
          )}

          {summary && (
            <div className="mb-5 grid gap-3 md:grid-cols-3">
              {summary.map((item) => (
                <div key={item.label} className="rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3">
                  <p className="text-xs uppercase tracking-[0.16em] text-white/35">{item.label}</p>
                  <p className="mt-1 text-2xl font-semibold tracking-tight text-white">{formatNumber(item.value)}</p>
                </div>
              ))}
            </div>
          )}

          {videos.length > 0 ? (
            <div className="overflow-hidden rounded-3xl border border-white/10 bg-black/20">
              <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-4">
                <div>
                  <h2 className="font-display text-xl font-medium tracking-tight text-white">
                    Extracted videos
                  </h2>
                  <p className="mt-1 text-sm text-white/45">
                    Scan {scan.scanId} from @{scan.creatorHandle}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full bg-white/10 px-3 py-1.5 text-xs font-semibold text-white/60">
                    {videos.length} URLs ready
                  </span>
                  <button
                    type="button"
                    onClick={handleCreateBatch}
                    disabled={isCreatingBatch}
                    className="inline-flex items-center gap-2 rounded-full bg-white px-4 py-2 text-xs font-semibold text-ink-950 transition-transform hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-45 disabled:hover:translate-y-0"
                  >
                    {isCreatingBatch ? <Loader2 size={14} className="animate-spin" aria-hidden /> : <PackagePlus size={14} aria-hidden />}
                    {isCreatingBatch ? 'Creating...' : 'Create Source Batch'}
                  </button>
                </div>
              </div>
              <div>
                {videos.map((video) => (
                  <VideoRow key={video.id || video.url} video={video} onCopy={handleCopy} />
                ))}
              </div>
            </div>
          ) : (
            <EmptyState />
          )}
        </div>
      </section>
    </div>
  );
}

export default TikTokAccountImporter;
