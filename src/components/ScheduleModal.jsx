import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  CalendarClock,
  ChevronLeft,
  ChevronRight,
  Link2,
  RefreshCw,
  Send,
  CheckCircle2,
  X,
  Image,
  Video,
  Play,
} from 'lucide-react';
import {
  createLatePost,
  createLateProfile,
  getLateConnectUrl,
  listLateAccounts,
  patchGeneration,
  DEFAULT_SESSION_ID,
} from '../lib/lateApi';

const SOCIAL_PLATFORMS = [
  'instagram',
  'tiktok',
  'youtube',
  'facebook',
  'linkedin',
  'threads',
  'twitter',
];

function toIsoLocal(datetimeLocal) {
  if (!datetimeLocal) return null;
  const d = new Date(datetimeLocal);
  if (Number.isNaN(d.getTime())) return null;
  return d.toISOString();
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

function CarouselPreview({ slides, mediaUrls }) {
  const scrollRef = useRef(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const checkScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 4);
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 4);
  };

  useEffect(() => {
    checkScroll();
    const el = scrollRef.current;
    if (el) el.addEventListener('scroll', checkScroll, { passive: true });
    return () => el?.removeEventListener('scroll', checkScroll);
  }, []);

  const scroll = (dir) => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollBy({ left: dir * 200, behavior: 'smooth' });
  };

  // Build items from slides metadata if available, otherwise fall back to raw URLs
  const items = slides.length > 0
    ? slides.map((s) => ({ url: s.url, label: s.kind || '', tipTitle: s.tipTitle || '' }))
    : mediaUrls.map((url, i) => ({ url, label: `Slide ${i + 1}`, tipTitle: '' }));

  return (
    <div className="mb-5">
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
        Preview &middot; {items.length} slide{items.length !== 1 ? 's' : ''}
      </p>

      <div className="relative group">
        {/* Left arrow */}
        {canScrollLeft && (
          <button
            onClick={() => scroll(-1)}
            className="absolute left-0 top-1/2 -translate-y-1/2 z-10 w-7 h-7 rounded-full bg-white/90 shadow border border-gray-200 flex items-center justify-center hover:bg-white transition-colors"
          >
            <ChevronLeft size={16} className="text-gray-600" />
          </button>
        )}

        {/* Scrollable track */}
        <div
          ref={scrollRef}
          className="flex gap-3 overflow-x-auto pb-2 scrollbar-hide px-1"
        >
          {items.map((item, i) => (
            <div key={i} className="flex-shrink-0 w-32">
              <div className="aspect-square rounded-xl overflow-hidden bg-gray-100 border border-gray-200 shadow-sm">
                <img
                  src={item.url}
                  alt={item.label}
                  className="w-full h-full object-cover"
                />
              </div>
              <p className="mt-1 text-[11px] text-gray-500 text-center truncate">
                {item.tipTitle || item.label}
              </p>
            </div>
          ))}
        </div>

        {/* Right arrow */}
        {canScrollRight && (
          <button
            onClick={() => scroll(1)}
            className="absolute right-0 top-1/2 -translate-y-1/2 z-10 w-7 h-7 rounded-full bg-white/90 shadow border border-gray-200 flex items-center justify-center hover:bg-white transition-colors"
          >
            <ChevronRight size={16} className="text-gray-600" />
          </button>
        )}
      </div>
    </div>
  );
}

export default function ScheduleModal({ generation, onClose, onScheduled }) {
  const [profileId, setProfileId] = useState('');
  const [profileName, setProfileName] = useState('Lumeet Profile');
  const [caption, setCaption] = useState('');
  const [platformToConnect, setPlatformToConnect] = useState('instagram');
  const [accounts, setAccounts] = useState([]);
  const [selectedAccountIds, setSelectedAccountIds] = useState([]);
  const [scheduledFor, setScheduledFor] = useState(nextSlotDatetimeLocal());
  const [timezone, setTimezone] = useState(
    Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
  );
  const [statusMessage, setStatusMessage] = useState('');
  const [error, setError] = useState('');
  const [isCreatingProfile, setIsCreatingProfile] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isLoadingAccounts, setIsLoadingAccounts] = useState(false);
  const [isScheduling, setIsScheduling] = useState(false);

  const output = generation?.output || {};
  const isVideo = generation?.type === 'video';
  const isCarousel = generation?.type === 'carousel';

  // Derive media URLs
  const mediaUrls = useMemo(() => {
    if (isVideo) {
      const url = output.videoGcs?.url || output.videoUrl || '';
      return url ? [url] : [];
    }
    if (isCarousel) {
      return output.mediaUrls || [];
    }
    return [];
  }, [isVideo, isCarousel, output]);

  // Carousel slides metadata (for labeled previews)
  const slides = useMemo(() => {
    if (isCarousel && output.slides) return output.slides;
    return [];
  }, [isCarousel, output]);

  // Pre-fill caption for carousel
  useEffect(() => {
    if (isCarousel) {
      const parts = [output.captionDraft, ...(output.hashtags || [])].filter(Boolean);
      setCaption(parts.join('\n\n').trim());
      if (output.suggestedScheduledFor) {
        const d = new Date(output.suggestedScheduledFor);
        if (!Number.isNaN(d.getTime()) && d > new Date()) {
          const tzOffsetMs = d.getTimezoneOffset() * 60000;
          const local = new Date(d.getTime() - tzOffsetMs);
          setScheduledFor(local.toISOString().slice(0, 16));
        }
      }
    } else {
      setCaption('Generated with Lumeet');
    }
  }, [isCarousel, output]);

  const selectedPlatforms = useMemo(
    () =>
      accounts
        .filter((acc) => selectedAccountIds.includes(acc._id))
        .map((acc) => ({ platform: acc.platform, accountId: acc._id })),
    [accounts, selectedAccountIds],
  );

  const loadAccounts = async () => {
    setIsLoadingAccounts(true);
    setError('');
    try {
      const data = await listLateAccounts({
        sessionId: DEFAULT_SESSION_ID,
        profileId: profileId || undefined,
      });
      const raw = data.accounts || [];
      const normalized = raw
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
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoadingAccounts(false);
    }
  };

  useEffect(() => {
    loadAccounts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleCreateProfile = async () => {
    setIsCreatingProfile(true);
    setError('');
    setStatusMessage('');
    try {
      const data = await createLateProfile({
        sessionId: DEFAULT_SESSION_ID,
        name: profileName,
        description: 'Created from Lumeet',
      });
      const id = data?.profile?._id || '';
      setProfileId(id);
      setStatusMessage(`Profile created: ${id}`);
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
    setIsScheduling(true);
    setError('');
    setStatusMessage('');
    try {
      const scheduledIso = toIsoLocal(scheduledFor);
      if (!scheduledIso) throw new Error('Pick a valid schedule date/time.');
      const payload = {
        sessionId: DEFAULT_SESSION_ID,
        profileId: profileId || undefined,
        content: caption,
        platforms: selectedPlatforms,
        publishNow: false,
        timezone,
        scheduledFor: scheduledIso,
        mediaUrls,
        ...(isVideo && output.jobId ? { jobId: output.jobId, includeResultVideo: true } : {}),
      };
      const data = await createLatePost(payload);
      const postId = data?.post?._id || data?._id || 'created';
      setStatusMessage(`Scheduled successfully (${postId}).`);

      // Mark generation as scheduled in backend
      if (generation?.generationId) {
        try {
          await patchGeneration(generation.generationId, { scheduled: true });
        } catch {
          // non-critical — the post was already scheduled
        }
      }
      // Notify parent so GenerationCenter can refresh
      if (onScheduled) onScheduled(generation);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsScheduling(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/30 backdrop-blur-sm">
      <div className="relative w-full max-w-xl mx-4 max-h-[85vh] overflow-y-auto glass-heavy border border-white/40 rounded-2xl shadow-2xl p-6">
        {/* Close */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
        >
          <X size={18} className="text-gray-500" />
        </button>

        {/* Header */}
        <div className="flex items-center gap-3 mb-5">
          <CalendarClock size={22} className="text-purple-600" />
          <div>
            <h3 className="text-lg font-bold text-gray-900">Schedule to Social</h3>
            <p className="text-xs text-gray-500 flex items-center gap-1.5 mt-0.5">
              {isVideo ? <Video size={12} /> : <Image size={12} />}
              {generation?.label || generation?.type}
            </p>
          </div>
        </div>

        {/* Content Preview */}
        {isVideo && mediaUrls.length > 0 && (
          <div className="mb-5">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Preview</p>
            <div className="flex justify-center">
              <div className="w-44 aspect-[9/16] rounded-2xl overflow-hidden bg-black shadow-lg border border-white/10">
                <video
                  src={mediaUrls[0]}
                  controls
                  className="w-full h-full object-contain"
                />
              </div>
            </div>
          </div>
        )}

        {isCarousel && mediaUrls.length > 0 && (
          <CarouselPreview slides={slides} mediaUrls={mediaUrls} />
        )}

        {/* Profile creation */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
          <input
            value={profileName}
            onChange={(e) => setProfileName(e.target.value)}
            className="px-3 py-2 rounded-xl border border-gray-200 focus:border-purple-400 outline-none text-sm"
            placeholder="Profile name"
          />
          <button
            onClick={handleCreateProfile}
            disabled={isCreatingProfile || !profileName.trim()}
            className="px-4 py-2 rounded-xl bg-purple-600 text-white text-sm hover:bg-purple-700 disabled:opacity-50"
          >
            {isCreatingProfile ? 'Creating...' : 'Create Profile'}
          </button>
        </div>
        <p className="text-[11px] text-gray-400 mb-3">
          Skip if your Late account already has connected accounts.
        </p>

        {/* Connect account */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
          <select
            value={platformToConnect}
            onChange={(e) => setPlatformToConnect(e.target.value)}
            className="px-3 py-2 rounded-xl border border-gray-200 focus:border-purple-400 outline-none text-sm"
          >
            {SOCIAL_PLATFORMS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
          <button
            onClick={handleConnect}
            disabled={isConnecting}
            className="px-4 py-2 rounded-xl bg-indigo-600 text-white text-sm hover:bg-indigo-700 disabled:opacity-50 flex items-center justify-center gap-2"
          >
            <Link2 size={14} />
            {isConnecting ? 'Opening...' : 'Connect'}
          </button>
          <button
            onClick={loadAccounts}
            disabled={isLoadingAccounts}
            className="px-4 py-2 rounded-xl bg-gray-100 text-gray-700 text-sm hover:bg-gray-200 disabled:opacity-50 flex items-center justify-center gap-2"
          >
            <RefreshCw size={14} className={isLoadingAccounts ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>

        {/* Account list */}
        {accounts.length > 0 && (
          <div className="mb-4 border border-gray-200 rounded-xl p-3 max-h-32 overflow-y-auto">
            {accounts.map((acc) => (
              <label
                key={acc._id}
                className="flex items-center gap-2 py-1 text-sm text-gray-800"
              >
                <input
                  type="checkbox"
                  checked={selectedAccountIds.includes(acc._id)}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setSelectedAccountIds((prev) => [...prev, acc._id]);
                    } else {
                      setSelectedAccountIds((prev) => prev.filter((id) => id !== acc._id));
                    }
                  }}
                />
                <span className="font-medium">{acc.platform}</span>
                <span className="text-gray-400 text-xs">{acc._id}</span>
              </label>
            ))}
          </div>
        )}

        {/* Caption */}
        <textarea
          value={caption}
          onChange={(e) => setCaption(e.target.value)}
          rows={3}
          className="w-full mb-3 px-3 py-2 rounded-xl border border-gray-200 focus:border-purple-400 outline-none text-sm"
          placeholder="Caption / content"
        />

        {/* Date & timezone */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
          <input
            type="datetime-local"
            value={scheduledFor}
            onChange={(e) => setScheduledFor(e.target.value)}
            className="px-3 py-2 rounded-xl border border-gray-200 focus:border-purple-400 outline-none text-sm"
          />
          <input
            value={timezone}
            onChange={(e) => setTimezone(e.target.value)}
            className="px-3 py-2 rounded-xl border border-gray-200 focus:border-purple-400 outline-none text-sm"
            placeholder="Timezone"
          />
        </div>

        {/* Schedule button */}
        <button
          onClick={handleSchedule}
          disabled={isScheduling || selectedPlatforms.length === 0 || !caption.trim() || !scheduledFor}
          className="w-full px-4 py-3 rounded-xl bg-gradient-to-r from-purple-600 to-purple-500 text-white font-semibold hover:from-purple-700 hover:to-purple-600 disabled:opacity-50 flex items-center justify-center gap-2 text-sm"
        >
          <Send size={16} />
          {isScheduling ? 'Scheduling...' : 'Schedule Post'}
        </button>

        {statusMessage && (
          <p className="mt-3 text-sm text-green-700 flex items-center gap-2">
            <CheckCircle2 size={16} />
            {statusMessage}
          </p>
        )}
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      </div>
    </div>
  );
}
