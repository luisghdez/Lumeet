import React, { useEffect, useMemo, useState, useCallback } from 'react';
import { CalendarRange, CheckCircle2, Film, Image as ImageIcon, Link2, Play, RefreshCw, Send } from 'lucide-react';
import AccountRow from './AccountRow';
import {
  createLatePost,
  createLateProfile,
  DEFAULT_SESSION_ID,
  getLateConnectUrl,
  listCarousels,
  listLateAccounts,
  listVideos,
} from '../lib/lateApi';

function toIsoLocal(datetimeLocal) {
  if (!datetimeLocal) return null;
  const localDate = new Date(datetimeLocal);
  if (Number.isNaN(localDate.getTime())) return null;
  return localDate.toISOString();
}

function nextSlotDatetimeLocal(stepMinutes = 30) {
  const now = new Date();
  const candidate = new Date(now.getTime() + stepMinutes * 60 * 1000);
  const minutes = candidate.getMinutes();
  const floored = Math.floor(minutes / stepMinutes) * stepMinutes;
  candidate.setMinutes(floored, 0, 0);
  const tzOffsetMs = candidate.getTimezoneOffset() * 60000;
  const local = new Date(candidate.getTime() - tzOffsetMs);
  return local.toISOString().slice(0, 16);
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

const SOCIAL_PLATFORMS = [
  'instagram',
  'tiktok',
  'youtube',
  'facebook',
  'linkedin',
  'threads',
  'twitter',
];

const LIBRARY_CACHE_TTL_MS = 2 * 60 * 1000;
const PAGE_SIZE = 5;

const libraryCache = {
  videos: null,
  videosTotal: 0,
  videosFetchedAt: 0,
  carousels: null,
  carouselsFetchedAt: 0,
};

function VideoLibrary() {
  const [libraryTab, setLibraryTab] = useState('video'); // 'video' | 'carousel'
  const [videos, setVideos] = useState([]);
  const [videosTotal, setVideosTotal] = useState(0);
  const [carousels, setCarousels] = useState([]);
  const [isLoadingVideos, setIsLoadingVideos] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [isLoadingCarousels, setIsLoadingCarousels] = useState(false);
  const [selectedVideo, setSelectedVideo] = useState(null);
  const [selectedCarousel, setSelectedCarousel] = useState(null);
  const [caption, setCaption] = useState('');
  const [timezone, setTimezone] = useState(Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC');
  const [scheduledFor, setScheduledFor] = useState('');
  const [publishNow, setPublishNow] = useState(false);
  const [profileName, setProfileName] = useState('Lumeet Profile');
  const [profileId, setProfileId] = useState('');
  const [platformToConnect, setPlatformToConnect] = useState('instagram');
  const [accounts, setAccounts] = useState([]);
  const [selectedAccountIds, setSelectedAccountIds] = useState([]);
  const [statusMessage, setStatusMessage] = useState('');
  const [error, setError] = useState('');
  const [isCreatingProfile, setIsCreatingProfile] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isLoadingAccounts, setIsLoadingAccounts] = useState(false);
  const [isScheduling, setIsScheduling] = useState(false);

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
    const now = Date.now();
    const videosCacheIsFresh = (
      !force
      && Array.isArray(libraryCache.videos)
      && now - libraryCache.videosFetchedAt < LIBRARY_CACHE_TTL_MS
    );
    if (videosCacheIsFresh) {
      setVideos(libraryCache.videos);
      setVideosTotal(libraryCache.videosTotal);
      return;
    }

    setIsLoadingVideos(true);
    setError('');
    try {
      const data = await listVideos({ limit: PAGE_SIZE, offset: 0 });
      const nextVideos = data.videos || [];
      const total = data.total ?? nextVideos.length;
      setVideos(nextVideos);
      setVideosTotal(total);
      libraryCache.videos = nextVideos;
      libraryCache.videosTotal = total;
      libraryCache.videosFetchedAt = Date.now();
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
      const merged = [...videos, ...moreVideos];
      setVideos(merged);
      setVideosTotal(total);
      libraryCache.videos = merged;
      libraryCache.videosTotal = total;
      libraryCache.videosFetchedAt = Date.now();
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
    const now = Date.now();
    const carouselsCacheIsFresh = (
      !force
      && Array.isArray(libraryCache.carousels)
      && now - libraryCache.carouselsFetchedAt < LIBRARY_CACHE_TTL_MS
    );
    if (carouselsCacheIsFresh) {
      setCarousels(libraryCache.carousels);
      return;
    }

    setIsLoadingCarousels(true);
    setError('');
    try {
      const data = await listCarousels();
      const nextCarousels = data.carousels || [];
      setCarousels(nextCarousels);
      libraryCache.carousels = nextCarousels;
      libraryCache.carouselsFetchedAt = Date.now();
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
        profileId: profileId || undefined,
      });
      const normalized = (data.accounts || [])
        .map((acc) => ({
          _id: String(acc?._id ?? acc?.id ?? '').trim(),
          platform: String(acc?.platform ?? acc?.provider ?? '').trim(),
          profileId: (
            typeof acc?.profileId === 'string'
              ? acc.profileId
              : typeof acc?.profile?._id === 'string'
                ? acc.profile._id
                : ''
          ).trim(),
        }))
        .filter((acc) => acc._id && acc.platform);
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
    handleLoadVideos();
    handleLoadCarousels();
    handleLoadAccounts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---- Actions ----

  const selectVideo = (video) => {
    setSelectedVideo(video);
    setCaption('Generated with Lumeet');
    setScheduledFor(nextSlotDatetimeLocal());
    setPublishNow(false);
    setStatusMessage(`Selected video ${video.videoId}.`);
  };

  const selectCarousel = (carousel) => {
    setSelectedCarousel(carousel);
    setStatusMessage(`Selected carousel ${carousel.carouselId}.`);
  };

  const handleCreateProfile = async () => {
    setIsCreatingProfile(true);
    setError('');
    setStatusMessage('');
    try {
      const data = await createLateProfile({
        sessionId: DEFAULT_SESSION_ID,
        name: profileName,
        description: 'Created from Video Library',
      });
      const createdProfileId = data?.profile?._id || '';
      setProfileId(createdProfileId);
      setStatusMessage(`Profile created: ${createdProfileId}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsCreatingProfile(false);
    }
  };

  const handleConnect = async () => {
    setIsConnecting(true);
    setError('');
    setStatusMessage('');
    try {
      const redirectUrl = `${window.location.origin}${window.location.pathname}?late_connected=1`;
      const data = await getLateConnectUrl({
        platform: platformToConnect,
        profileId: profileId || undefined,
        sessionId: DEFAULT_SESSION_ID,
        redirectUrl,
      });
      if (!data.authUrl) throw new Error('Late did not return an authUrl.');
      window.location.href = data.authUrl;
    } catch (err) {
      setError(err.message);
      setIsConnecting(false);
    }
  };

  const handleSchedule = async () => {
    if (!selectedVideo) return;
    setIsScheduling(true);
    setError('');
    setStatusMessage('');
    try {
      const selectedAccounts = accounts.filter((acc) => selectedAccountIds.includes(acc._id));
      const inferredProfileIds = Array.from(
        new Set(selectedAccounts.map((acc) => acc.profileId).filter(Boolean)),
      );
      if (!profileId && inferredProfileIds.length > 1) {
        throw new Error('Selected accounts belong to multiple profiles. Select accounts from one profile or create/use a profile.');
      }
      const resolvedProfileId = profileId || inferredProfileIds[0] || undefined;

      if (!publishNow) {
        const scheduledIso = toIsoLocal(scheduledFor);
        if (!scheduledIso) {
          throw new Error('Pick a valid schedule date/time, or toggle "Publish now".');
        }
      }

      const payload = {
        sessionId: DEFAULT_SESSION_ID,
        profileId: resolvedProfileId,
        content: caption,
        platforms: selectedPlatforms,
        publishNow,
        timezone: publishNow ? undefined : timezone,
        scheduledFor: publishNow ? undefined : toIsoLocal(scheduledFor),
        mediaUrls: selectedVideo.url ? [selectedVideo.url] : [],
      };
      const data = await createLatePost(payload);
      const postId = data?.post?._id || data?._id || 'created';
      setStatusMessage(`Post ${publishNow ? 'published' : 'scheduled'} successfully (${postId}).`);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsScheduling(false);
    }
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
    const resolvedProfileId = profileId || inferredProfileIds[0] || undefined;

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
            ? (slot.item.prompt || 'Generated with Lumeet')
            : (bulkCaption || 'Generated with Lumeet'),
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

  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-8 text-center">
        <div className="flex items-center justify-center gap-3">
          {bulkMode ? (
            <CalendarRange size={24} className="text-purple-600" />
          ) : libraryTab === 'video' ? (
            <Film size={24} className="text-purple-600" />
          ) : (
            <ImageIcon size={24} className="text-purple-600" />
          )}
          <h2 className="text-3xl font-bold text-gray-900">
            {bulkMode
              ? 'Bulk Schedule'
              : libraryTab === 'video'
                ? 'Video Library'
                : 'Carousel Library'}
          </h2>
        </div>
        <p className="text-gray-600 mt-2">
          {bulkMode
            ? 'Select videos and carousels, then schedule them across multiple days.'
            : libraryTab === 'video'
              ? 'Browse past generated videos and schedule or publish them.'
              : 'Browse generated carousels and review their slides.'}
        </p>
      </div>

      <div className="mb-6 flex justify-center gap-3">
        <div className="inline-flex p-1 rounded-2xl bg-white/70 border border-white/40">
          <button
            type="button"
            onClick={() => { if (bulkMode) exitBulkMode(); setLibraryTab('video'); }}
            className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200 ${
              !bulkMode && libraryTab === 'video'
                ? 'bg-gradient-to-r from-purple-600 to-purple-500 text-white shadow'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            <Film size={16} />
            Videos
          </button>
          <button
            type="button"
            onClick={() => { if (bulkMode) exitBulkMode(); setLibraryTab('carousel'); }}
            className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200 ${
              !bulkMode && libraryTab === 'carousel'
                ? 'bg-gradient-to-r from-purple-600 to-purple-500 text-white shadow'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            <ImageIcon size={16} />
            Carousels
          </button>
          <button
            type="button"
            onClick={() => { if (!bulkMode) { setBulkMode(true); } else { exitBulkMode(); } }}
            className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200 ${
              bulkMode
                ? 'bg-gradient-to-r from-purple-600 to-purple-500 text-white shadow'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            <CalendarRange size={16} />
            Bulk Schedule
          </button>
        </div>
      </div>

      {bulkMode ? (
        /* ===================== BULK SCHEDULE MODE ===================== */
        <>
          {/* Videos grid — multi-select */}
          <div className="glass-card border border-white/40 rounded-2xl p-5 mb-6">
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
          <div className="glass-card border border-white/40 rounded-2xl p-5 mb-6">
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
            <div className="glass-card border border-white/40 rounded-2xl p-5 mb-6">
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
                  <input
                    value={timezone}
                    onChange={(e) => setTimezone(e.target.value)}
                    className="px-3 py-2 rounded-xl border border-gray-200 focus:border-purple-400 outline-none w-full"
                    placeholder="Timezone"
                  />
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
          <div className="glass-card border border-white/40 rounded-2xl p-5 mb-6">
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
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
                  {videos.map((video) => {
                    const isSelected = selectedVideo?.videoId === video.videoId;
                    return (
                      <button
                        key={video.videoId}
                        onClick={() => selectVideo(video)}
                        className={`text-left rounded-2xl border-2 transition-all overflow-hidden
                          ${isSelected
                            ? 'border-purple-500 ring-2 ring-purple-200'
                            : 'border-gray-200 hover:border-purple-300'
                          }`}
                      >
                        <div className="relative aspect-[9/16] bg-black">
                          <video
                            src={video.url}
                            className="w-full h-full object-contain"
                            muted
                            preload="metadata"
                          />
                          <div className="absolute inset-0 flex items-center justify-center bg-black/20 opacity-0 hover:opacity-100 transition-opacity">
                            <Play size={36} className="text-white drop-shadow-lg" />
                          </div>
                          {isSelected && (
                            <div className="absolute top-2 right-2">
                              <CheckCircle2 size={22} className="text-purple-500 drop-shadow" />
                            </div>
                          )}
                        </div>
                        <div className="p-3">
                          <p className="text-xs text-gray-500">{video.createdAt || ''}</p>
                          <p className="text-sm font-semibold text-gray-900 truncate">
                            {video.videoId}
                          </p>
                          {video.extended && (
                            <span className="inline-block mt-1 text-xs px-2 py-0.5 rounded-full bg-purple-100 text-purple-700 font-medium">
                              Extended
                            </span>
                          )}
                        </div>
                      </button>
                    );
                  })}
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

          {/* Schedule / Publish Section — shown when a video is selected */}
          {selectedVideo && (
            <>
              {/* Preview */}
              <div className="glass-card border border-white/40 rounded-2xl p-5 mb-6">
                <h3 className="text-lg font-bold text-gray-900 mb-3">Preview</h3>
                <div className="flex justify-center">
                  <div className="w-full max-w-xs aspect-[9/16] rounded-2xl overflow-hidden bg-black shadow-xl">
                    <video
                      src={selectedVideo.url}
                      controls
                      className="w-full h-full object-contain"
                    />
                  </div>
                </div>
              </div>

              {/* Schedule Controls */}
              <div className="glass-card border border-white/40 rounded-2xl p-5">
                <h3 className="text-lg font-bold text-gray-900 mb-3">Schedule or Publish</h3>

                {/* Profile */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
                  <input
                    value={profileName}
                    onChange={(e) => setProfileName(e.target.value)}
                    className="px-3 py-2 rounded-xl border border-gray-200 focus:border-purple-400 outline-none"
                    placeholder="Profile name"
                  />
                  <button
                    onClick={handleCreateProfile}
                    disabled={isCreatingProfile || !profileName.trim()}
                    className="px-4 py-2 rounded-xl bg-purple-600 text-white hover:bg-purple-700 disabled:opacity-50"
                  >
                    {isCreatingProfile ? 'Creating...' : 'Create Profile'}
                  </button>
                </div>
                <p className="text-xs text-gray-500 mb-3">
                  Skip if your Late account already has connected accounts.
                </p>

                {/* Connect */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
                  <select
                    value={platformToConnect}
                    onChange={(e) => setPlatformToConnect(e.target.value)}
                    className="px-3 py-2 rounded-xl border border-gray-200 focus:border-purple-400 outline-none"
                  >
                    {SOCIAL_PLATFORMS.map((p) => (
                      <option key={p} value={p}>{p}</option>
                    ))}
                  </select>
                  <button
                    onClick={handleConnect}
                    disabled={isConnecting}
                    className="px-4 py-2 rounded-xl bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    <Link2 size={16} />
                    {isConnecting ? 'Opening...' : 'Connect Account'}
                  </button>
                  <button
                    onClick={handleLoadAccounts}
                    disabled={isLoadingAccounts}
                    className="px-4 py-2 rounded-xl bg-gray-100 text-gray-700 hover:bg-gray-200 disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    <RefreshCw size={16} className={isLoadingAccounts ? 'animate-spin' : ''} />
                    Refresh Accounts
                  </button>
                </div>

                {/* Account checkboxes */}
                {accounts.length > 0 && (
                  <div className="mb-4 border border-gray-200 rounded-xl p-3 max-h-36 overflow-y-auto">
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
                )}

                {/* Caption */}
                <textarea
                  value={caption}
                  onChange={(e) => setCaption(e.target.value)}
                  rows={4}
                  className="w-full mb-3 px-3 py-2 rounded-xl border border-gray-200 focus:border-purple-400 outline-none"
                  placeholder="Caption with hashtags"
                />

                {/* Schedule / Publish now */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
                  <label className="flex items-center gap-2 text-sm text-gray-700 font-medium">
                    <input
                      type="checkbox"
                      checked={publishNow}
                      onChange={(e) => setPublishNow(e.target.checked)}
                    />
                    Publish now
                  </label>
                  <input
                    type="datetime-local"
                    value={scheduledFor}
                    onChange={(e) => setScheduledFor(e.target.value)}
                    disabled={publishNow}
                    className="px-3 py-2 rounded-xl border border-gray-200 focus:border-purple-400 outline-none disabled:bg-gray-100"
                  />
                  <input
                    value={timezone}
                    onChange={(e) => setTimezone(e.target.value)}
                    disabled={publishNow}
                    className="px-3 py-2 rounded-xl border border-gray-200 focus:border-purple-400 outline-none disabled:bg-gray-100"
                    placeholder="Timezone"
                  />
                </div>

                <button
                  onClick={handleSchedule}
                  disabled={isScheduling || selectedPlatforms.length === 0 || !caption.trim() || (!publishNow && !scheduledFor)}
                  className="w-full px-4 py-3 rounded-xl bg-gradient-to-r from-purple-600 to-purple-500 text-white font-semibold hover:from-purple-700 hover:to-purple-600 disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  <Send size={16} />
                  {isScheduling ? 'Sending...' : publishNow ? 'Publish Now' : 'Schedule Post'}
                </button>
              </div>
            </>
          )}
        </>
      ) : (
        <>
          {/* Carousel Gallery */}
          <div className="glass-card border border-white/40 rounded-2xl p-5 mb-6">
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
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
                {carousels.map((carousel) => {
                  const isSelected = selectedCarousel?.carouselId === carousel.carouselId;
                  const coverUrl = carousel.mediaUrls?.[0] || '';
                  return (
                    <button
                      key={carousel.carouselId}
                      onClick={() => selectCarousel(carousel)}
                      className={`text-left rounded-2xl border-2 transition-all overflow-hidden
                        ${isSelected
                          ? 'border-purple-500 ring-2 ring-purple-200'
                          : 'border-gray-200 hover:border-purple-300'
                        }`}
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
                        {isSelected && (
                          <div className="absolute top-2 right-2">
                            <CheckCircle2 size={22} className="text-purple-500 drop-shadow" />
                          </div>
                        )}
                      </div>
                      <div className="p-3">
                        <p className="text-xs text-gray-500">{carousel.createdAt || ''}</p>
                        <p className="text-sm font-semibold text-gray-900 truncate">
                          {carousel.prompt || carousel.carouselId}
                        </p>
                        <p className="text-xs text-gray-500 mt-1">
                          {carousel.mediaUrls?.length || 0} slides
                        </p>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Carousel Preview */}
          {selectedCarousel && (
            <div className="glass-card border border-white/40 rounded-2xl p-5">
              <h3 className="text-lg font-bold text-gray-900 mb-2">Carousel Preview</h3>
              <p className="text-sm text-gray-600 mb-4">{selectedCarousel.prompt}</p>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {(selectedCarousel.mediaUrls || []).map((url) => (
                  <div key={url} className="aspect-square rounded-xl overflow-hidden bg-gray-100">
                    <img src={url} alt="" className="w-full h-full object-cover" loading="lazy" />
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {statusMessage && (
        <p className="mt-4 text-sm text-green-700 flex items-center gap-2">
          <CheckCircle2 size={16} />
          {statusMessage}
        </p>
      )}
      {error && <p className="mt-4 text-sm text-red-600">{error}</p>}
    </div>
  );
}

export default VideoLibrary;
