import React, { useEffect, useMemo, useState, useCallback } from 'react';
import { CalendarRange, CheckCircle2, Clock, Film, Image as ImageIcon, RefreshCw, Send, Trash2 } from 'lucide-react';
import AccountRow from './AccountRow';
import ScheduleModal from './ScheduleModal';
import { normalizeLateAccounts } from '../lib/lateAccounts';
import {
  createLatePost,
  DEFAULT_SESSION_ID,
  deleteVideo,
  listLateAccounts,
  listVideos,
} from '../lib/lateApi';
import { useLibraryVideos, useLibraryCarousels } from '../lib/mediaLibrary';

function toIsoLocal(datetimeLocal) {
  if (!datetimeLocal) return null;
  const localDate = new Date(datetimeLocal);
  if (Number.isNaN(localDate.getTime())) return null;
  return localDate.toISOString();
}

/**
 * Format a library item's `createdAt` (ISO string or Unix-seconds number) into
 * a friendly relative/short label. Returns empty string if unparsable.
 */
function formatCreatedAt(raw) {
  if (!raw && raw !== 0) return '';
  let d;
  if (typeof raw === 'number') {
    // Unix seconds (backend stores e.g. 1773612943.11244)
    d = new Date(raw * 1000);
  } else if (typeof raw === 'string') {
    d = new Date(raw);
  } else {
    return '';
  }
  if (Number.isNaN(d.getTime())) return '';

  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  const diffH = Math.floor(diffMs / 3600000);
  const diffD = Math.floor(diffMs / 86400000);

  if (diffMin < 1) return 'Just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffH < 24) return `${diffH}h ago`;
  if (diffD < 7) return `${diffD}d ago`;

  const sameYear = d.getFullYear() === now.getFullYear();
  return d.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    ...(sameYear ? {} : { year: 'numeric' }),
  });
}

/** Return tomorrow's date as YYYY-MM-DD. */
function tomorrowDateStr() {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return d.toISOString().slice(0, 10);
}

/** Random integer in [min, max). */
function randInt(min, max) {
  return Math.floor(Math.random() * (max - min)) + min;
}

/**
 * Given an ordered list of { item, type } objects, assign each a scheduledFor
 * datetime-local string spread across consecutive days.
 *
 * @param {Array<{item: object, type: 'video'|'carousel'}>} items
 * @param {{ postsPerDay: 1|2, startDate: string }} opts  startDate is YYYY-MM-DD
 * @returns {Array<{item: object, type: string, scheduledFor: string}>}
 */
function generateBulkSlots(items, { postsPerDay, startDate }) {
  if (!items.length) return [];
  const slots = [];
  let dayOffset = 0;
  let slotInDay = 0;

  for (const entry of items) {
    // Build the date for this slot
    const base = new Date(`${startDate}T00:00:00`);
    base.setDate(base.getDate() + dayOffset);

    let hour;
    let minute;
    if (postsPerDay === 1) {
      // Random between 4:00 PM and 6:59 PM
      const total = randInt(0, 180); // 3 hours = 180 minutes
      hour = 16 + Math.floor(total / 60);
      minute = total % 60;
    } else if (slotInDay === 0) {
      // First slot: 2:00 PM – 4:59 PM
      const total = randInt(0, 180);
      hour = 14 + Math.floor(total / 60);
      minute = total % 60;
    } else {
      // Second slot: 5:00 PM – 6:59 PM
      const total = randInt(0, 120);
      hour = 17 + Math.floor(total / 60);
      minute = total % 60;
    }

    const y = base.getFullYear();
    const m = String(base.getMonth() + 1).padStart(2, '0');
    const d = String(base.getDate()).padStart(2, '0');
    const hh = String(hour).padStart(2, '0');
    const mm = String(minute).padStart(2, '0');

    slots.push({
      ...entry,
      scheduledFor: `${y}-${m}-${d}T${hh}:${mm}`,
    });

    slotInDay += 1;
    if (slotInDay >= postsPerDay) {
      slotInDay = 0;
      dayOffset += 1;
    }
  }

  return slots;
}

const PAGE_SIZE = 5;

function VideoLibrary() {
  const [libraryTab, setLibraryTab] = useState('video'); // 'video' | 'carousel'
  const {
    videos,
    total: videosTotal,
    setVideos,
    setTotal: setVideosTotal,
    refresh: refreshVideos,
  } = useLibraryVideos();
  const {
    carousels,
    setCarousels,
    refresh: refreshCarousels,
  } = useLibraryCarousels();
  const [isLoadingVideos, setIsLoadingVideos] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [isLoadingCarousels, setIsLoadingCarousels] = useState(false);
  const [timezone] = useState(Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC');
  const [accounts, setAccounts] = useState([]);
  const [selectedAccountIds, setSelectedAccountIds] = useState([]);
  const [statusMessage, setStatusMessage] = useState('');
  const [error, setError] = useState('');
  const [isLoadingAccounts, setIsLoadingAccounts] = useState(false);
  const [isScheduling, setIsScheduling] = useState(false);
  const [deletingVideoId, setDeletingVideoId] = useState(null);
  // Target passed to the shared ScheduleModal when a library item is clicked.
  const [scheduleTarget, setScheduleTarget] = useState(null);

  // ---- Bulk scheduling state ----
  const [bulkMode, setBulkMode] = useState(false);
  const [bulkSelectedVideos, setBulkSelectedVideos] = useState([]);
  const [bulkSelectedCarousels, setBulkSelectedCarousels] = useState([]);
  const [bulkPostsPerDay, setBulkPostsPerDay] = useState(1);
  const [bulkStartDate, setBulkStartDate] = useState(tomorrowDateStr);
  const [bulkCaption, setBulkCaption] = useState('');
  // { current, total, results: [{ ok, id?, error? }] } | null
  const [bulkProgress, setBulkProgress] = useState(null);

  const selectedPlatforms = useMemo(
    () =>
      accounts
        .filter((acc) => selectedAccountIds.includes(acc._id))
        .map((acc) => ({ platform: acc.platform, accountId: acc._id }))
        .filter((t) => t.platform && t.accountId),
    [accounts, selectedAccountIds],
  );

  // ---- Data loading ----

  const handleLoadVideos = async (force = false) => {
    if (!force) return;
    setIsLoadingVideos(true);
    setError('');
    try {
      await refreshVideos();
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoadingVideos(false);
    }
  };

  const handleLoadMoreVideos = async () => {
    setIsLoadingMore(true);
    setError('');
    try {
      const data = await listVideos({ limit: PAGE_SIZE, offset: videos.length });
      const moreVideos = data.videos || [];
      const total = data.total ?? (videos.length + moreVideos.length);
      setVideos((prev) => [...prev, ...moreVideos]);
      setVideosTotal(total);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoadingMore(false);
    }
  };

  const hasMoreVideos = videos.length < videosTotal;

  // ---- Bulk selection helpers ----

  const toggleBulkVideo = useCallback((video) => {
    setBulkSelectedVideos((prev) => {
      const exists = prev.some((v) => v.videoId === video.videoId);
      return exists ? prev.filter((v) => v.videoId !== video.videoId) : [...prev, video];
    });
  }, []);

  const toggleBulkCarousel = useCallback((carousel) => {
    setBulkSelectedCarousels((prev) => {
      const exists = prev.some((c) => c.carouselId === carousel.carouselId);
      return exists ? prev.filter((c) => c.carouselId !== carousel.carouselId) : [...prev, carousel];
    });
  }, []);

  const bulkItems = useMemo(() => [
    ...bulkSelectedVideos.map((v) => ({ item: v, type: 'video' })),
    ...bulkSelectedCarousels.map((c) => ({ item: c, type: 'carousel' })),
  ], [bulkSelectedVideos, bulkSelectedCarousels]);

  const bulkSlots = useMemo(
    () => generateBulkSlots(bulkItems, { postsPerDay: bulkPostsPerDay, startDate: bulkStartDate }),
    [bulkItems, bulkPostsPerDay, bulkStartDate],
  );

  const exitBulkMode = useCallback(() => {
    setBulkMode(false);
    setBulkSelectedVideos([]);
    setBulkSelectedCarousels([]);
    setBulkProgress(null);
  }, []);

  const handleLoadCarousels = async (force = false) => {
    if (!force) return;
    setIsLoadingCarousels(true);
    setError('');
    try {
      await refreshCarousels();
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoadingCarousels(false);
    }
  };

  const handleLoadAccounts = async () => {
    setIsLoadingAccounts(true);
    setError('');
    setStatusMessage('');
    try {
      const data = await listLateAccounts({
        sessionId: DEFAULT_SESSION_ID,
      });
      const normalized = normalizeLateAccounts(data.accounts || []);
      setAccounts(normalized);
      if (normalized.length > 0) {
        setStatusMessage(`Loaded ${normalized.length} connected account(s).`);
      } else {
        setStatusMessage('No connected accounts found yet.');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoadingAccounts(false);
    }
  };

  useEffect(() => {
    handleLoadAccounts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---- Actions ----

  // Open the shared ScheduleModal by constructing a generation-shaped payload
  // from a library item. We intentionally omit `generationId` so the modal
  // doesn't try to patch a non-existent generation record after scheduling.
  const openVideoSchedule = (video) => {
    setStatusMessage('');
    setError('');
    setScheduleTarget({
      type: 'video',
      label: video.videoId,
      output: {
        videoUrl: video.url || '',
        videoGcs: video.url ? { url: video.url } : null,
      },
    });
  };

  const openCarouselSchedule = (carousel) => {
    setStatusMessage('');
    setError('');
    setScheduleTarget({
      type: 'carousel',
      label: carousel.prompt || carousel.carouselId,
      output: {
        mediaUrls: carousel.mediaUrls || [],
        slides: carousel.slides || [],
        captionDraft: carousel.captionDraft || carousel.prompt || '',
        hashtags: carousel.hashtags || [],
        suggestedScheduledFor: carousel.suggestedScheduledFor || '',
      },
    });
  };

  const handleDeleteVideo = async (videoId) => {
    setDeletingVideoId(videoId);
    setError('');
    setStatusMessage('');
    try {
      await deleteVideo(videoId);
      setVideos((prev) => prev.filter((video) => video.videoId !== videoId));
      setVideosTotal((prevTotal) => Math.max(0, prevTotal - 1));
      setBulkSelectedVideos((prev) => prev.filter((video) => video.videoId !== videoId));
      setStatusMessage('Generated video deleted.');
    } catch (err) {
      setError(err.message);
    } finally {
      setDeletingVideoId(null);
    }
  };

  const handleModalScheduled = () => {
    setScheduleTarget(null);
    setStatusMessage('Post scheduled successfully.');
  };

  // ---- Bulk schedule execution ----

  const handleBulkSchedule = async () => {
    if (!bulkSlots.length || selectedPlatforms.length === 0) return;
    setIsScheduling(true);
    setError('');
    setStatusMessage('');

    const selectedAccounts = accounts.filter((acc) => selectedAccountIds.includes(acc._id));
    const inferredProfileIds = Array.from(
      new Set(selectedAccounts.map((acc) => acc.profileId).filter(Boolean)),
    );
    const resolvedProfileId = inferredProfileIds[0] || undefined;

    const results = [];
    setBulkProgress({ current: 0, total: bulkSlots.length, results: [] });

    for (let i = 0; i < bulkSlots.length; i++) {
      const slot = bulkSlots[i];
      const mediaUrls =
        slot.type === 'video'
          ? (slot.item.url ? [slot.item.url] : [])
          : (slot.item.mediaUrls || []);

      try {
        const payload = {
          sessionId: DEFAULT_SESSION_ID,
          profileId: resolvedProfileId,
          content: slot.type === 'carousel'
            ? (slot.item.prompt || 'Generated with nflncr.ai')
            : (bulkCaption || 'Generated with nflncr.ai'),
          platforms: selectedPlatforms,
          publishNow: false,
          timezone,
          scheduledFor: toIsoLocal(slot.scheduledFor),
          mediaUrls,
        };
        const data = await createLatePost(payload);
        const postId = data?.post?._id || data?._id || 'ok';
        results.push({ ok: true, id: postId });
      } catch (err) {
        results.push({ ok: false, error: err.message });
      }
      setBulkProgress({ current: i + 1, total: bulkSlots.length, results: [...results] });
    }

    const succeeded = results.filter((r) => r.ok).length;
    const failed = results.filter((r) => !r.ok).length;
    setStatusMessage(
      `Bulk schedule complete: ${succeeded} scheduled` +
        (failed ? `, ${failed} failed` : '') +
        '.',
    );
    setIsScheduling(false);
  };

  // ---- Render ----

  const activeLibraryTabId = bulkMode ? 'bulk' : libraryTab;
  const libraryTabs = [
    { id: 'video', label: 'Videos', Icon: Film },
    { id: 'carousel', label: 'Carousels', Icon: ImageIcon },
    { id: 'bulk', label: 'Bulk Schedule', Icon: CalendarRange },
  ];
  const handleLibraryTabClick = (id) => {
    if (id === 'bulk') {
      if (!bulkMode) setBulkMode(true);
      else exitBulkMode();
      return;
    }
    if (bulkMode) exitBulkMode();
    setLibraryTab(id);
  };

  return (
    <div className="max-w-6xl mx-auto pt-2 pb-6 md:pt-4 md:pb-8">
      <div className="mb-4 md:mb-6 flex justify-center">
        <div className="inline-flex p-1 rounded-2xl bg-white/70 border border-white/40">
          {libraryTabs.map(({ id, label, Icon }) => {
            const isActive = activeLibraryTabId === id;
            return (
              <button
                key={id}
                type="button"
                onClick={() => handleLibraryTabClick(id)}
                aria-pressed={isActive}
                className={`inline-flex items-center px-3 py-2 md:px-5 md:py-2.5 rounded-xl text-sm font-semibold transition-all duration-300 ease-out ${
                  isActive
                    ? 'bg-gradient-to-r from-purple-600 to-purple-500 text-white shadow'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                <Icon size={16} className="flex-shrink-0" />
                <span
                  className={`overflow-hidden whitespace-nowrap transition-all duration-300 ease-out ${
                    isActive
                      ? 'max-w-[160px] opacity-100 ml-2'
                      : 'max-w-0 opacity-0 ml-0 sm:max-w-[160px] sm:opacity-100 sm:ml-2'
                  }`}
                >
                  {label}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {bulkMode ? (
        /* ===================== BULK SCHEDULE MODE ===================== */
        <>
          {/* Videos grid — multi-select */}
          <div className="glass-card rounded-2xl p-5 mb-6">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-lg font-bold text-gray-900">Videos</h3>
              <div className="flex items-center gap-2">
                {bulkSelectedVideos.length > 0 && (
                  <span className="text-xs font-medium text-purple-600 bg-purple-50 px-2 py-1 rounded-lg">
                    {bulkSelectedVideos.length} selected
                  </span>
                )}
                <button
                  onClick={() => handleLoadVideos(true)}
                  disabled={isLoadingVideos}
                  className="px-3 py-2 rounded-xl bg-gray-100 text-gray-700 hover:bg-gray-200 disabled:opacity-50 flex items-center gap-2"
                >
                  <RefreshCw size={14} className={isLoadingVideos ? 'animate-spin' : ''} />
                  Refresh
                </button>
              </div>
            </div>
            {videos.length === 0 ? (
              <p className="text-sm text-gray-600">No videos yet.</p>
            ) : (
              <>
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
                  {videos.map((video) => {
                    const checked = bulkSelectedVideos.some((v) => v.videoId === video.videoId);
                    return (
                      <button
                        key={video.videoId}
                        onClick={() => toggleBulkVideo(video)}
                        className={`text-left rounded-2xl border-2 transition-all overflow-hidden ${
                          checked
                            ? 'border-purple-500 ring-2 ring-purple-200'
                            : 'border-gray-200 hover:border-purple-300'
                        }`}
                      >
                        <div className="relative aspect-[9/16] bg-black">
                          <video src={video.url} className="w-full h-full object-contain" muted preload="metadata" />
                          {checked && (
                            <div className="absolute top-2 right-2">
                              <CheckCircle2 size={20} className="text-purple-500 drop-shadow" />
                            </div>
                          )}
                        </div>
                        <div className="p-2">
                          <p className="text-xs text-gray-500 truncate">{video.videoId}</p>
                        </div>
                      </button>
                    );
                  })}
                </div>
                {hasMoreVideos && (
                  <div className="flex justify-center mt-3">
                    <button
                      onClick={handleLoadMoreVideos}
                      disabled={isLoadingMore}
                      className="px-4 py-2 rounded-xl bg-purple-50 text-purple-700 font-semibold hover:bg-purple-100 disabled:opacity-50 flex items-center gap-2 text-sm"
                    >
                      {isLoadingMore ? (
                        <><RefreshCw size={14} className="animate-spin" /> Loading…</>
                      ) : (
                        `Load More (${videos.length} of ${videosTotal})`
                      )}
                    </button>
                  </div>
                )}
              </>
            )}
          </div>

          {/* Carousels grid — multi-select */}
          <div className="glass-card rounded-2xl p-5 mb-6">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-lg font-bold text-gray-900">Carousels</h3>
              <div className="flex items-center gap-2">
                {bulkSelectedCarousels.length > 0 && (
                  <span className="text-xs font-medium text-purple-600 bg-purple-50 px-2 py-1 rounded-lg">
                    {bulkSelectedCarousels.length} selected
                  </span>
                )}
                <button
                  onClick={() => handleLoadCarousels(true)}
                  disabled={isLoadingCarousels}
                  className="px-3 py-2 rounded-xl bg-gray-100 text-gray-700 hover:bg-gray-200 disabled:opacity-50 flex items-center gap-2"
                >
                  <RefreshCw size={14} className={isLoadingCarousels ? 'animate-spin' : ''} />
                  Refresh
                </button>
              </div>
            </div>
            {carousels.length === 0 ? (
              <p className="text-sm text-gray-600">No carousels yet.</p>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
                {carousels.map((carousel) => {
                  const checked = bulkSelectedCarousels.some((c) => c.carouselId === carousel.carouselId);
                  const coverUrl = carousel.mediaUrls?.[0] || '';
                  return (
                    <button
                      key={carousel.carouselId}
                      onClick={() => toggleBulkCarousel(carousel)}
                      className={`text-left rounded-2xl border-2 transition-all overflow-hidden ${
                        checked
                          ? 'border-purple-500 ring-2 ring-purple-200'
                          : 'border-gray-200 hover:border-purple-300'
                      }`}
                    >
                      <div className="relative aspect-square bg-gray-100">
                        {coverUrl ? (
                          <img src={coverUrl} alt="" className="w-full h-full object-cover" loading="lazy" />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-gray-400">
                            <ImageIcon size={22} />
                          </div>
                        )}
                        {checked && (
                          <div className="absolute top-2 right-2">
                            <CheckCircle2 size={20} className="text-purple-500 drop-shadow" />
                          </div>
                        )}
                      </div>
                      <div className="p-2">
                        <p className="text-xs text-gray-500 truncate">{carousel.prompt || carousel.carouselId}</p>
                        <p className="text-xs text-gray-400">{carousel.mediaUrls?.length || 0} slides</p>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Bulk config + preview — shown when items are selected */}
          {bulkItems.length > 0 && (
            <div className="glass-card rounded-2xl p-5 mb-6">
              <h3 className="text-lg font-bold text-gray-900 mb-4">
                Schedule {bulkItems.length} Post{bulkItems.length > 1 ? 's' : ''}
              </h3>

              {/* Account selection */}
              <div className="mb-4">
                <label className="block text-sm font-semibold text-gray-700 mb-2">Accounts</label>
                {accounts.length > 0 ? (
                  <div className="border border-gray-200 rounded-xl p-3 max-h-36 overflow-y-auto">
                    {accounts.map((acc) => (
                      <AccountRow
                        key={acc._id}
                        account={acc}
                        checked={selectedAccountIds.includes(acc._id)}
                        onToggle={(checked) => {
                          if (checked) {
                            setSelectedAccountIds((prev) => [...prev, acc._id]);
                          } else {
                            setSelectedAccountIds((prev) => prev.filter((id) => id !== acc._id));
                          }
                        }}
                      />
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">No connected accounts. Connect one in the single-schedule view first.</p>
                )}
              </div>

              {/* Posts per day + Start date */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-1">Posts per day</label>
                  <div className="inline-flex p-1 rounded-xl bg-gray-100 border border-gray-200">
                    {[1, 2].map((n) => (
                      <button
                        key={n}
                        type="button"
                        onClick={() => setBulkPostsPerDay(n)}
                        className={`px-4 py-1.5 rounded-lg text-sm font-semibold transition-all ${
                          bulkPostsPerDay === n
                            ? 'bg-white text-purple-700 shadow'
                            : 'text-gray-500 hover:text-gray-700'
                        }`}
                      >
                        {n}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-1">Start date</label>
                  <input
                    type="date"
                    value={bulkStartDate}
                    onChange={(e) => setBulkStartDate(e.target.value)}
                    className="px-3 py-2 rounded-xl border border-gray-200 focus:border-purple-400 outline-none w-full"
                  />
                </div>
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-1">Timezone</label>
                  <div className="px-3 py-2 rounded-xl border border-gray-200 bg-gray-50 text-sm text-gray-600 w-full truncate">
                    {timezone}
                  </div>
                </div>
              </div>

              {/* Caption — only for videos; carousels use their own prompt */}
              {bulkSelectedVideos.length > 0 && (
                <div className="mb-4">
                  <label className="block text-sm font-semibold text-gray-700 mb-1">
                    Caption{bulkSelectedCarousels.length > 0 ? ' (videos only — carousels use their own)' : ''}
                  </label>
                  <textarea
                    value={bulkCaption}
                    onChange={(e) => setBulkCaption(e.target.value)}
                    rows={3}
                    className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:border-purple-400 outline-none"
                    placeholder="Caption with hashtags"
                  />
                </div>
              )}

              {/* Schedule preview */}
              <div className="mb-4">
                <label className="block text-sm font-semibold text-gray-700 mb-2">Schedule Preview</label>
                <div className="border border-gray-200 rounded-xl divide-y divide-gray-100 max-h-64 overflow-y-auto">
                  {bulkSlots.map((slot, idx) => {
                    const d = new Date(slot.scheduledFor);
                    const dateStr = d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
                    const timeStr = d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
                    const label =
                      slot.type === 'video'
                        ? slot.item.videoId
                        : (slot.item.prompt || slot.item.carouselId);
                    return (
                      <div key={idx} className="flex items-center gap-3 px-3 py-2 text-sm">
                        <span className={`inline-block w-16 text-center text-xs font-semibold rounded-full px-2 py-0.5 ${
                          slot.type === 'video'
                            ? 'bg-blue-50 text-blue-700'
                            : 'bg-amber-50 text-amber-700'
                        }`}>
                          {slot.type === 'video' ? 'Video' : 'Carousel'}
                        </span>
                        <span className="text-gray-500 w-32 shrink-0">{dateStr} {timeStr}</span>
                        <span className="text-gray-800 truncate">{label}</span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Progress indicator */}
              {bulkProgress && (
                <div className="mb-4">
                  <div className="flex items-center gap-3 mb-2">
                    <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-purple-500 transition-all duration-300 rounded-full"
                        style={{ width: `${(bulkProgress.current / bulkProgress.total) * 100}%` }}
                      />
                    </div>
                    <span className="text-sm font-semibold text-gray-600">
                      {bulkProgress.current} / {bulkProgress.total}
                    </span>
                  </div>
                  {bulkProgress.results.some((r) => !r.ok) && (
                    <div className="text-xs text-red-600 space-y-0.5">
                      {bulkProgress.results
                        .map((r, i) => (!r.ok ? <p key={i}>Post {i + 1}: {r.error}</p> : null))
                        .filter(Boolean)}
                    </div>
                  )}
                </div>
              )}

              {/* Schedule All button */}
              <button
                onClick={handleBulkSchedule}
                disabled={isScheduling || selectedPlatforms.length === 0 || !bulkSlots.length || (bulkSelectedVideos.length > 0 && !bulkCaption.trim())}
                className="w-full px-4 py-3 rounded-xl bg-gradient-to-r from-purple-600 to-purple-500 text-white font-semibold hover:from-purple-700 hover:to-purple-600 disabled:opacity-50 flex items-center justify-center gap-2"
              >
                <Send size={16} />
                {isScheduling
                  ? `Scheduling${bulkProgress ? ` (${bulkProgress.current}/${bulkProgress.total})` : ''}…`
                  : `Schedule All ${bulkSlots.length} Post${bulkSlots.length !== 1 ? 's' : ''}`}
              </button>
            </div>
          )}
        </>
      ) : libraryTab === 'video' ? (
        <>
          {/* Video Gallery */}
          <div className="glass-card rounded-2xl p-5 mb-6">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-lg font-bold text-gray-900">Generated Videos</h3>
              <button
                onClick={() => handleLoadVideos(true)}
                disabled={isLoadingVideos}
                className="px-3 py-2 rounded-xl bg-gray-100 text-gray-700 hover:bg-gray-200 disabled:opacity-50 flex items-center gap-2"
              >
                <RefreshCw size={14} className={isLoadingVideos ? 'animate-spin' : ''} />
                Refresh
              </button>
            </div>
            {videos.length === 0 ? (
              <p className="text-sm text-gray-600">
                No generated videos yet. Create one in the <strong>Create</strong> tab and it will appear here.
              </p>
            ) : (
              <>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3 sm:gap-4">
                  {videos.map((video) => (
                    <div key={video.videoId} className="relative group">
                      <button
                        type="button"
                        onClick={() => openVideoSchedule(video)}
                        className="w-full text-left rounded-2xl border-2 border-gray-200 hover:border-purple-400 transition-all overflow-hidden hover:shadow-md"
                      >
                        <div className="relative aspect-[9/16] bg-black">
                          <video
                            src={video.url}
                            className="w-full h-full object-contain"
                            muted
                            preload="metadata"
                          />
                          {video.extended && (
                            <span className="absolute top-2 right-2 px-2 py-0.5 rounded-full bg-purple-600/90 text-white text-[10px] font-semibold shadow backdrop-blur-sm">
                              Extended
                            </span>
                          )}
                          <div className="absolute inset-0 flex items-center justify-center bg-black/30 opacity-0 group-hover:opacity-100 transition-opacity">
                            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white/90 text-purple-700 text-xs font-semibold shadow">
                              <Send size={12} />
                              Schedule
                            </div>
                          </div>
                        </div>
                        {(() => {
                          const label = formatCreatedAt(video.createdAt);
                          return label ? (
                            <div className="px-3 py-2 flex items-center gap-1.5">
                              <Clock size={11} className="text-gray-400 flex-shrink-0" />
                              <p className="text-[11px] font-medium text-gray-600 truncate">
                                {label}
                              </p>
                            </div>
                          ) : null;
                        })()}
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDeleteVideo(video.videoId)}
                        disabled={deletingVideoId === video.videoId}
                        className="absolute top-2 left-2 rounded-full bg-red-500 p-1.5 text-white shadow transition-colors hover:bg-red-600 disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-white/80"
                        title="Delete generated video"
                        aria-label={`Delete generated video ${video.videoId}`}
                      >
                        {deletingVideoId === video.videoId ? (
                          <RefreshCw size={13} className="animate-spin" />
                        ) : (
                          <Trash2 size={13} />
                        )}
                      </button>
                    </div>
                  ))}
                </div>
                {hasMoreVideos && (
                  <div className="flex justify-center mt-4">
                    <button
                      onClick={handleLoadMoreVideos}
                      disabled={isLoadingMore}
                      className="px-5 py-2.5 rounded-xl bg-purple-50 text-purple-700 font-semibold hover:bg-purple-100 disabled:opacity-50 flex items-center gap-2 transition-colors"
                    >
                      {isLoadingMore ? (
                        <>
                          <RefreshCw size={14} className="animate-spin" />
                          Loading…
                        </>
                      ) : (
                        `Load More (${videos.length} of ${videosTotal})`
                      )}
                    </button>
                  </div>
                )}
              </>
            )}
          </div>

        </>
      ) : (
        <>
          {/* Carousel Gallery */}
          <div className="glass-card rounded-2xl p-5 mb-6">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-lg font-bold text-gray-900">Generated Carousels</h3>
              <button
                onClick={() => handleLoadCarousels(true)}
                disabled={isLoadingCarousels}
                className="px-3 py-2 rounded-xl bg-gray-100 text-gray-700 hover:bg-gray-200 disabled:opacity-50 flex items-center gap-2"
              >
                <RefreshCw size={14} className={isLoadingCarousels ? 'animate-spin' : ''} />
                Refresh
              </button>
            </div>
            {carousels.length === 0 ? (
              <p className="text-sm text-gray-600">
                No generated carousels yet. Create one in the <strong>Create</strong> tab and it will appear here.
              </p>
            ) : (
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3 sm:gap-4">
                {carousels.map((carousel) => {
                  const coverUrl = carousel.mediaUrls?.[0] || '';
                  const slideCount = carousel.mediaUrls?.length || 0;
                  return (
                    <button
                      key={carousel.carouselId}
                      onClick={() => openCarouselSchedule(carousel)}
                      className="group text-left rounded-2xl border-2 border-gray-200 hover:border-purple-400 transition-all overflow-hidden hover:shadow-md"
                    >
                      <div className="relative aspect-square bg-gray-100">
                        {coverUrl ? (
                          <img
                            src={coverUrl}
                            alt=""
                            className="w-full h-full object-cover"
                            loading="lazy"
                          />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-gray-400">
                            <ImageIcon size={26} />
                          </div>
                        )}
                        {slideCount > 0 && (
                          <span className="absolute top-2 left-2 px-2 py-0.5 rounded-full bg-black/55 text-white text-[10px] font-semibold">
                            {slideCount} slides
                          </span>
                        )}
                        <div className="absolute inset-0 flex items-center justify-center bg-black/30 opacity-0 group-hover:opacity-100 transition-opacity">
                          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white/90 text-purple-700 text-xs font-semibold shadow">
                            <Send size={12} />
                            Schedule
                          </div>
                        </div>
                      </div>
                      <div className="p-3">
                        <p className="text-sm font-semibold text-gray-900 truncate">
                          {carousel.prompt || carousel.carouselId}
                        </p>
                        {(() => {
                          const label = formatCreatedAt(carousel.createdAt);
                          return label ? (
                            <div className="mt-1 flex items-center gap-1.5">
                              <Clock size={11} className="text-gray-400 flex-shrink-0" />
                              <p className="text-[11px] font-medium text-gray-600 truncate">
                                {label}
                              </p>
                            </div>
                          ) : null;
                        })()}
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </>
      )}

      {statusMessage && (
        <p className="mt-4 text-sm text-green-700 flex items-center gap-2">
          <CheckCircle2 size={16} />
          {statusMessage}
        </p>
      )}
      {error && <p className="mt-4 text-sm text-red-600">{error}</p>}

      {scheduleTarget && (
        <ScheduleModal
          generation={scheduleTarget}
          onClose={() => setScheduleTarget(null)}
          onScheduled={handleModalScheduled}
        />
      )}
    </div>
  );
}

export default VideoLibrary;
