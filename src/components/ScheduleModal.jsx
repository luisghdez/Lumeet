import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  CalendarClock,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  RefreshCw,
  Send,
  CheckCircle2,
  X,
  Image as ImageIcon,
  Video,
  Instagram,
  Youtube,
  Facebook,
  Linkedin,
  Twitter,
  AtSign,
  Users,
  Sparkles,
  Loader2,
  Plus,
  Clock,
  Pencil,
  Check,
  Eye,
  Maximize2,
} from 'lucide-react';
import {
  createLatePost,
  getLateConnectUrl,
  listLateAccounts,
  listLatePosts,
  patchGeneration,
  DEFAULT_SESSION_ID,
} from '../lib/lateApi';
import { getNickname, setNickname as saveNickname } from '../lib/accountNicknames';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function toIsoLocal(datetimeLocal) {
  if (!datetimeLocal) return null;
  const d = new Date(datetimeLocal);
  if (Number.isNaN(d.getTime())) return null;
  return d.toISOString();
}

function formatRelativeSchedule(date) {
  if (!date || Number.isNaN(date.getTime())) return null;
  const now = new Date();
  const diffMs = date.getTime() - now.getTime();
  if (diffMs <= 0) return null;

  const diffMin = Math.round(diffMs / 60000);
  const diffH = Math.round(diffMs / 3600000);
  const diffD = Math.round(diffMs / 86400000);

  let relative;
  if (diffMin < 60) relative = `in ${diffMin}m`;
  else if (diffH < 24) relative = `in ${diffH}h`;
  else relative = `in ${diffD}d`;

  const todayKey = now.toDateString();
  const tomorrow = new Date(now);
  tomorrow.setDate(tomorrow.getDate() + 1);
  const tomorrowKey = tomorrow.toDateString();
  const targetKey = date.toDateString();

  let day;
  if (targetKey === todayKey) day = 'Today';
  else if (targetKey === tomorrowKey) day = 'Tomorrow';
  else
    day = date.toLocaleDateString([], {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
    });

  const time = date.toLocaleTimeString([], {
    hour: 'numeric',
    minute: '2-digit',
  });

  return { day, time, relative, date };
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

const PLATFORM_META = {
  instagram: { label: 'Instagram', Icon: Instagram, tone: 'from-pink-500 to-orange-400' },
  tiktok: { label: 'TikTok', Icon: null, initials: 'TT', tone: 'from-gray-900 to-gray-700' },
  youtube: { label: 'YouTube', Icon: Youtube, tone: 'from-red-600 to-red-500' },
  facebook: { label: 'Facebook', Icon: Facebook, tone: 'from-blue-600 to-blue-500' },
  linkedin: { label: 'LinkedIn', Icon: Linkedin, tone: 'from-sky-700 to-sky-500' },
  threads: { label: 'Threads', Icon: AtSign, tone: 'from-gray-900 to-gray-700' },
  twitter: { label: 'X / Twitter', Icon: Twitter, tone: 'from-gray-900 to-gray-700' },
};

const CONNECTABLE_PLATFORMS = [
  'instagram',
  'tiktok',
  'youtube',
  'facebook',
  'linkedin',
  'threads',
  'twitter',
];

function getPlatformMeta(platform) {
  return PLATFORM_META[platform?.toLowerCase()] || {
    label: platform || 'Account',
    Icon: null,
    initials: (platform || '?').slice(0, 2).toUpperCase(),
    tone: 'from-purple-500 to-purple-400',
  };
}

function PlatformBadge({ platform, size = 36 }) {
  const meta = getPlatformMeta(platform);
  const { Icon } = meta;
  return (
    <div
      className={`rounded-xl bg-gradient-to-br ${meta.tone} text-white flex items-center justify-center flex-shrink-0 shadow-sm`}
      style={{ width: size, height: size }}
    >
      {Icon ? (
        <Icon size={Math.round(size * 0.5)} />
      ) : (
        <span className="font-bold text-[11px] tracking-wide">{meta.initials}</span>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Preview helpers
// ---------------------------------------------------------------------------

function buildSlideItems(slides, mediaUrls) {
  return slides.length > 0
    ? slides.map((s, i) => ({
        url: s.url,
        label: s.kind || '',
        tipTitle: s.tipTitle || `Slide ${i + 1}`,
      }))
    : mediaUrls.map((url, i) => ({
        url,
        label: `Slide ${i + 1}`,
        tipTitle: `Slide ${i + 1}`,
      }));
}

// Compact carousel preview: main slide + thumbnail strip with arrows.
function InlineCarouselPreview({
  items,
  activeIndex,
  onActiveChange,
  onExpand,
}) {
  const active = items[activeIndex] || items[0];

  const goPrev = (e) => {
    e.stopPropagation();
    onActiveChange((activeIndex - 1 + items.length) % items.length);
  };
  const goNext = (e) => {
    e.stopPropagation();
    onActiveChange((activeIndex + 1) % items.length);
  };

  return (
    <div className="flex flex-col items-center">
      <div className="relative w-44 sm:w-52">
        <div className="aspect-square rounded-2xl overflow-hidden bg-gray-100 border border-gray-200 shadow-sm">
          <img
            src={active.url}
            alt={active.tipTitle}
            className="w-full h-full object-cover"
            onClick={onExpand}
          />
        </div>
        {items.length > 1 && (
          <>
            <button
              type="button"
              onClick={goPrev}
              className="absolute left-1 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-white/95 shadow-md border border-gray-200 flex items-center justify-center hover:bg-white transition-colors"
              aria-label="Previous slide"
            >
              <ChevronLeft size={16} className="text-gray-700" />
            </button>
            <button
              type="button"
              onClick={goNext}
              className="absolute right-1 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-white/95 shadow-md border border-gray-200 flex items-center justify-center hover:bg-white transition-colors"
              aria-label="Next slide"
            >
              <ChevronRight size={16} className="text-gray-700" />
            </button>
            <div className="absolute bottom-2 left-1/2 -translate-x-1/2 px-2 py-0.5 rounded-full bg-black/55 text-white text-[10px] font-semibold">
              {activeIndex + 1} / {items.length}
            </div>
          </>
        )}
      </div>
      {active.tipTitle && (
        <p className="mt-2 text-[11px] text-gray-500 text-center max-w-[14rem] truncate">
          {active.tipTitle}
        </p>
      )}
      {items.length > 1 && (
        <div className="mt-3 flex gap-1.5 overflow-x-auto max-w-full px-1 pb-1 scrollbar-hide">
          {items.map((item, i) => (
            <button
              key={i}
              type="button"
              onClick={() => onActiveChange(i)}
              aria-label={`Go to slide ${i + 1}`}
              className={`flex-shrink-0 w-10 h-10 rounded-lg overflow-hidden border-2 transition-all ${
                i === activeIndex
                  ? 'border-purple-500 ring-2 ring-purple-200 scale-105'
                  : 'border-gray-200 opacity-75 hover:opacity-100'
              }`}
            >
              <img src={item.url} alt="" className="w-full h-full object-cover" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function InlineVideoPreview({ src, onExpand }) {
  return (
    <div className="flex justify-center">
      <div className="relative group">
        <div className="w-44 sm:w-52 aspect-[9/16] rounded-2xl overflow-hidden bg-black shadow-md">
          <video
            src={src}
            controls
            playsInline
            preload="metadata"
            className="w-full h-full object-contain"
          />
        </div>
        <button
          type="button"
          onClick={onExpand}
          className="absolute top-2 right-2 w-8 h-8 rounded-full bg-black/60 text-white flex items-center justify-center opacity-80 hover:opacity-100 hover:bg-black/80 transition-all backdrop-blur-sm"
          title="View fullscreen"
          aria-label="View fullscreen"
        >
          <Maximize2 size={14} />
        </button>
      </div>
    </div>
  );
}

// Fullscreen lightbox that overlays the modal panel. Handles both video
// playback and carousel slide navigation (keyboard + buttons).
function PreviewLightbox({
  isVideo,
  isCarousel,
  mediaUrls,
  items,
  activeIndex,
  onActiveChange,
  onClose,
}) {
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') onClose();
      if (!isCarousel || items.length < 2) return;
      if (e.key === 'ArrowLeft') {
        onActiveChange((activeIndex - 1 + items.length) % items.length);
      }
      if (e.key === 'ArrowRight') {
        onActiveChange((activeIndex + 1) % items.length);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isCarousel, items.length, activeIndex, onActiveChange, onClose]);

  const active = items[activeIndex];

  return (
    <div
      className="lightbox-enter absolute inset-0 z-30 bg-black/95 flex flex-col"
      onClick={onClose}
    >
      <div className="flex items-center justify-between px-4 py-3 text-white flex-shrink-0">
        <div className="flex items-center gap-2">
          <Eye size={16} />
          <span className="text-sm font-semibold">
            {isVideo ? 'Video preview' : `Slide ${activeIndex + 1} of ${items.length}`}
          </span>
        </div>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onClose();
          }}
          className="p-2 rounded-full bg-white/10 hover:bg-white/20 transition-colors"
          aria-label="Close preview"
        >
          <X size={18} />
        </button>
      </div>
      <div
        className="flex-1 flex items-center justify-center relative min-h-0 px-4 pb-4"
        onClick={(e) => e.stopPropagation()}
      >
        {isVideo && mediaUrls.length > 0 ? (
          <video
            src={mediaUrls[0]}
            controls
            autoPlay
            playsInline
            className="max-w-full max-h-full rounded-xl shadow-xl"
          />
        ) : isCarousel && active ? (
          <>
            <img
              src={active.url}
              alt={active.tipTitle}
              className="max-w-full max-h-full rounded-xl shadow-xl object-contain"
            />
            {items.length > 1 && (
              <>
                <button
                  type="button"
                  onClick={() =>
                    onActiveChange((activeIndex - 1 + items.length) % items.length)
                  }
                  className="absolute left-2 sm:left-4 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full bg-white/15 hover:bg-white/25 text-white flex items-center justify-center transition-colors"
                  aria-label="Previous slide"
                >
                  <ChevronLeft size={20} />
                </button>
                <button
                  type="button"
                  onClick={() =>
                    onActiveChange((activeIndex + 1) % items.length)
                  }
                  className="absolute right-2 sm:right-4 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full bg-white/15 hover:bg-white/25 text-white flex items-center justify-center transition-colors"
                  aria-label="Next slide"
                >
                  <ChevronRight size={20} />
                </button>
              </>
            )}
          </>
        ) : null}
      </div>
      {isCarousel && items.length > 1 && (
        <div
          className="flex-shrink-0 flex justify-center gap-1.5 pb-4 px-4 overflow-x-auto scrollbar-hide"
          onClick={(e) => e.stopPropagation()}
        >
          {items.map((item, i) => (
            <button
              key={i}
              type="button"
              onClick={() => onActiveChange(i)}
              className={`flex-shrink-0 w-12 h-12 rounded-lg overflow-hidden border-2 transition-all ${
                i === activeIndex
                  ? 'border-white scale-110'
                  : 'border-white/30 opacity-60 hover:opacity-100'
              }`}
            >
              <img src={item.url} alt="" className="w-full h-full object-cover" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Account card
// ---------------------------------------------------------------------------

function AccountCard({ account, selected, onToggle, onNicknameSaved }) {
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState('');

  const meta = getPlatformMeta(account.platform);
  const nick = getNickname(account._id);
  const shortId = account._id.length > 10
    ? `${account._id.slice(0, 4)}…${account._id.slice(-4)}`
    : account._id;

  const startEdit = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDraft(nick);
    setIsEditing(true);
  };

  const commitEdit = (e) => {
    e?.preventDefault?.();
    e?.stopPropagation?.();
    saveNickname(account._id, draft);
    setIsEditing(false);
    onNicknameSaved?.();
  };

  const cancelEdit = (e) => {
    e?.preventDefault?.();
    e?.stopPropagation?.();
    setIsEditing(false);
  };

  const handleKey = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      commitEdit(e);
    }
    if (e.key === 'Escape') {
      e.preventDefault();
      cancelEdit(e);
    }
  };

  const containerClass = `relative w-full flex items-center gap-3 px-3 py-2.5 rounded-xl border text-left transition-all duration-150 group ${
    selected
      ? 'border-purple-500 bg-purple-50 ring-2 ring-purple-200'
      : 'border-gray-200 bg-white hover:border-purple-300 hover:bg-gray-50'
  }`;

  if (isEditing) {
    return (
      <div className={containerClass}>
        <PlatformBadge platform={account.platform} size={36} />
        <div className="flex-1 min-w-0">
          <input
            autoFocus
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={handleKey}
            onClick={(e) => e.stopPropagation()}
            placeholder={meta.label}
            className="w-full px-2 py-1 rounded-md border border-purple-300 focus:border-purple-500 focus:ring-2 focus:ring-purple-100 outline-none text-sm bg-white"
          />
          <p className="text-[10px] text-gray-400 mt-0.5 truncate">{meta.label} · {shortId}</p>
        </div>
        <button
          type="button"
          onClick={commitEdit}
          className="p-1.5 rounded-lg bg-green-50 hover:bg-green-100 text-green-600 flex-shrink-0 transition-colors"
          title="Save nickname"
        >
          <Check size={14} />
        </button>
        <button
          type="button"
          onClick={cancelEdit}
          className="p-1.5 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-500 flex-shrink-0 transition-colors"
          title="Cancel"
        >
          <X size={14} />
        </button>
      </div>
    );
  }

  return (
    <div
      role="button"
      tabIndex={0}
      aria-pressed={selected}
      onClick={() => onToggle(!selected)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onToggle(!selected);
        }
      }}
      className={`${containerClass} cursor-pointer`}
    >
      <PlatformBadge platform={account.platform} size={36} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <p className="text-sm font-semibold text-gray-900 truncate">
            {nick || meta.label}
          </p>
          <button
            type="button"
            onClick={startEdit}
            className="p-0.5 rounded-md text-gray-400 hover:text-purple-600 hover:bg-purple-50 opacity-70 sm:opacity-0 sm:group-hover:opacity-100 transition-all"
            title={nick ? 'Edit nickname' : 'Add nickname'}
          >
            <Pencil size={11} />
          </button>
        </div>
        <p className="text-[11px] text-gray-500 truncate">
          {nick ? meta.label : shortId}
        </p>
      </div>
      <div
        className={`w-5 h-5 rounded-full border-2 flex items-center justify-center flex-shrink-0 transition-colors ${
          selected ? 'border-nimbus-700 bg-nimbus-700' : 'border-nimbus-400/45 bg-white shadow-[inset_0_1px_0_0_rgba(255,255,255,0.5)]'
        }`}
      >
        {selected && <CheckCircle2 size={14} className="text-white" />}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Modal
// ---------------------------------------------------------------------------

export default function ScheduleModal({ generation, onClose, onScheduled }) {
  const [profileId] = useState('');
  const [caption, setCaption] = useState('');
  const [accounts, setAccounts] = useState([]);
  const [selectedAccountIds, setSelectedAccountIds] = useState([]);
  const [scheduledFor, setScheduledFor] = useState(nextSlotDatetimeLocal());
  const [timezone] = useState(
    Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
  );
  const [statusMessage, setStatusMessage] = useState('');
  const [error, setError] = useState('');
  const [isLoadingAccounts, setIsLoadingAccounts] = useState(false);
  const [isScheduling, setIsScheduling] = useState(false);
  const [scheduledPosts, setScheduledPosts] = useState([]);
  const [isAddingAccount, setIsAddingAccount] = useState(false);
  const [connectingPlatform, setConnectingPlatform] = useState(null);
  const [isPreviewOpen, setIsPreviewOpen] = useState(true);
  const [activeSlide, setActiveSlide] = useState(0);
  const [isLightboxOpen, setIsLightboxOpen] = useState(false);
  // Bumped when any nickname changes, forces re-render of getNickname consumers
  const [, setNicknameVersion] = useState(0);
  const bumpNicknames = () => setNicknameVersion((v) => v + 1);

  const output = generation?.output || {};
  // Remix generations produce a video output, so treat them as videos for
  // preview + payload purposes.
  const isVideo =
    generation?.type === 'video' || generation?.type === 'remix';
  const isCarousel = generation?.type === 'carousel';

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

  const slides = useMemo(() => {
    if (isCarousel && output.slides) return output.slides;
    return [];
  }, [isCarousel, output]);

  const previewItems = useMemo(
    () => (isCarousel ? buildSlideItems(slides, mediaUrls) : []),
    [isCarousel, slides, mediaUrls],
  );

  const hasPreview =
    (isVideo && mediaUrls.length > 0) ||
    (isCarousel && previewItems.length > 0);

  const previewSummary = isVideo
    ? '1 video'
    : previewItems.length === 1
      ? '1 slide'
      : `${previewItems.length} slides`;

  useEffect(() => {
    setActiveSlide(0);
  }, [isCarousel, previewItems.length]);

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
      setCaption('Generated with nflncr.ai');
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

  const loadScheduledPosts = async () => {
    try {
      const data = await listLatePosts({
        sessionId: DEFAULT_SESSION_ID,
        status: 'scheduled',
        limit: 100,
      });
      const rawPosts = data.posts || data.results || data.data || [];
      setScheduledPosts(rawPosts.map((p) => ({
        scheduledFor: p?.scheduledFor || p?.scheduled_at || p?.scheduledTime || '',
        accountIds: (p?.platforms || []).map((pl) =>
          String(typeof pl === 'string' ? '' : pl?.accountId || pl?.account_id || ''),
        ).filter(Boolean),
      })));
    } catch {
      // non-critical
    }
  };

  // For each selected account, find the earliest upcoming scheduled post
  const nextByAccount = useMemo(() => {
    const now = Date.now();
    const map = {};
    for (const id of selectedAccountIds) {
      let earliest = null;
      for (const post of scheduledPosts) {
        if (!post.scheduledFor) continue;
        const applies =
          post.accountIds.length === 0 || post.accountIds.includes(id);
        if (!applies) continue;
        const d = new Date(post.scheduledFor);
        if (Number.isNaN(d.getTime()) || d.getTime() <= now) continue;
        if (!earliest || d < earliest) earliest = d;
      }
      if (earliest) map[id] = earliest;
    }
    return map;
  }, [selectedAccountIds, scheduledPosts]);

  useEffect(() => {
    loadAccounts();
    loadScheduledPosts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Split scheduledFor into date + time pieces for a cleaner picker
  const [datePart, timePart] = useMemo(() => {
    if (!scheduledFor || scheduledFor.length < 16) return ['', ''];
    return [scheduledFor.slice(0, 10), scheduledFor.slice(11, 16)];
  }, [scheduledFor]);

  const updateDatePart = (d) => {
    setScheduledFor(`${d}T${timePart || nextSlotDatetimeLocal().slice(11, 16)}`);
  };
  const updateTimePart = (t) => {
    const d = datePart || nextSlotDatetimeLocal().slice(0, 10);
    setScheduledFor(`${d}T${t}`);
  };

  const handleConnect = async (platform) => {
    setConnectingPlatform(platform);
    setError('');
    try {
      const redirectUrl = `${window.location.origin}${window.location.pathname}?late_connected=1`;
      const data = await getLateConnectUrl({
        platform,
        profileId: profileId || undefined,
        sessionId: DEFAULT_SESSION_ID,
        redirectUrl,
      });
      if (!data.authUrl) throw new Error('Late did not return an authUrl.');
      window.location.href = data.authUrl;
    } catch (err) {
      setError(err.message);
      setConnectingPlatform(null);
    }
  };

  const handleSchedule = async () => {
    setIsScheduling(true);
    setError('');
    setStatusMessage('');
    try {
      const scheduledIso = toIsoLocal(scheduledFor);
      if (!scheduledIso) throw new Error('Pick a valid schedule date & time.');
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

      if (generation?.generationId) {
        try {
          await patchGeneration(generation.generationId, { scheduled: true });
        } catch {
          // non-critical
        }
      }
      if (onScheduled) onScheduled(generation);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsScheduling(false);
    }
  };

  const captionLength = caption.length;
  const canSubmit =
    !isScheduling &&
    selectedPlatforms.length > 0 &&
    caption.trim().length > 0 &&
    Boolean(scheduledFor);

  return (
    <div
      className="modal-backdrop-enter fixed inset-0 z-[100] flex items-end sm:items-center justify-center bg-ink-950/55 backdrop-blur-md p-0 sm:p-4"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="modal-panel-enter relative w-full sm:max-w-xl max-h-[95vh] sm:max-h-[90vh] bg-white rounded-t-3xl sm:rounded-3xl shadow-2xl flex flex-col overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-nimbus-100 flex-shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-10 h-10 rounded-2xl bg-ink-950 flex items-center justify-center flex-shrink-0 shadow-pill">
              <CalendarClock size={18} className="text-white" />
            </div>
            <div className="min-w-0">
              <h3 className="text-lg font-display font-medium text-ink-950 leading-tight tracking-tight">
                Schedule post
              </h3>
              <p className="text-[11px] text-nimbus-600 flex items-center gap-1 mt-0.5 truncate">
                {isVideo ? <Video size={11} /> : <ImageIcon size={11} />}
                <span className="truncate">{generation?.label || generation?.type}</span>
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-full hover:bg-nimbus-100 transition-colors flex-shrink-0"
          >
            <X size={18} className="text-nimbus-600" />
          </button>
        </div>

        {/* Body (scrollable) */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
          {/* Preview — collapsible card */}
          {hasPreview && (
            <section className="rounded-2xl border border-gray-200 overflow-hidden bg-white">
              <div className="flex items-stretch bg-gray-50 border-b border-gray-100">
                <button
                  type="button"
                  onClick={() => setIsPreviewOpen((v) => !v)}
                  aria-expanded={isPreviewOpen}
                  className="flex-1 flex items-center justify-between px-4 py-2.5 hover:bg-gray-100 transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <Eye size={14} className="text-purple-600" />
                    <h4 className="text-xs font-bold text-gray-700 uppercase tracking-wide">
                      Preview
                    </h4>
                    <span className="text-[11px] font-medium text-gray-500">
                      {previewSummary}
                    </span>
                  </div>
                  <ChevronDown
                    size={16}
                    className={`text-gray-500 transition-transform duration-300 ${
                      isPreviewOpen ? 'rotate-180' : ''
                    }`}
                  />
                </button>
                <button
                  type="button"
                  onClick={() => setIsLightboxOpen(true)}
                  className="px-3 flex items-center gap-1.5 text-[11px] font-semibold text-purple-600 hover:bg-purple-50 border-l border-gray-100 transition-colors"
                  title="View fullscreen"
                >
                  <Maximize2 size={13} />
                  <span className="hidden sm:inline">Fullscreen</span>
                </button>
              </div>
              <div
                className={`grid transition-all duration-300 ease-out ${
                  isPreviewOpen ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'
                }`}
              >
                <div className="overflow-hidden">
                  <div className="p-4">
                    {isVideo ? (
                      <InlineVideoPreview
                        src={mediaUrls[0]}
                        onExpand={() => setIsLightboxOpen(true)}
                      />
                    ) : (
                      <InlineCarouselPreview
                        items={previewItems}
                        activeIndex={activeSlide}
                        onActiveChange={setActiveSlide}
                        onExpand={() => setIsLightboxOpen(true)}
                      />
                    )}
                  </div>
                </div>
              </div>
            </section>
          )}

          {/* Accounts */}
          <section>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Users size={14} className="text-gray-400" />
                <h4 className="text-xs font-bold text-gray-700 uppercase tracking-wide">
                  Post to
                </h4>
                {selectedAccountIds.length > 0 && (
                  <span className="text-[10px] font-bold text-purple-600 bg-purple-100 px-1.5 py-0.5 rounded-full">
                    {selectedAccountIds.length}
                  </span>
                )}
              </div>
              <button
                onClick={loadAccounts}
                disabled={isLoadingAccounts}
                className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500 transition-colors disabled:opacity-50"
                title="Refresh accounts"
              >
                <RefreshCw size={14} className={isLoadingAccounts ? 'animate-spin' : ''} />
              </button>
            </div>

            {isLoadingAccounts && accounts.length === 0 ? (
              <div className="flex items-center justify-center py-8 text-gray-400 text-sm">
                <Loader2 size={16} className="animate-spin mr-2" />
                Loading accounts…
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {accounts.map((acc) => (
                  <AccountCard
                    key={acc._id}
                    account={acc}
                    selected={selectedAccountIds.includes(acc._id)}
                    onToggle={(next) => {
                      setSelectedAccountIds((prev) =>
                        next ? [...prev, acc._id] : prev.filter((id) => id !== acc._id),
                      );
                    }}
                    onNicknameSaved={bumpNicknames}
                  />
                ))}

                {/* + Add account card */}
                <button
                  type="button"
                  onClick={() => setIsAddingAccount((v) => !v)}
                  aria-expanded={isAddingAccount}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl border-2 border-dashed text-left transition-all duration-200 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.35)] ${
                    isAddingAccount
                      ? 'border-nimbus-500/42 bg-white/45'
                      : 'border-nimbus-400/42 bg-white/80 hover:border-nimbus-500/48 hover:bg-white'
                  }`}
                >
                  <div
                    className={`w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 transition-all duration-300 ${
                      isAddingAccount
                        ? 'bg-gradient-to-br from-purple-500 to-purple-400 rotate-45'
                        : 'bg-gradient-to-br from-gray-100 to-gray-200'
                    }`}
                  >
                    <Plus
                      size={18}
                      className={`transition-colors duration-200 ${
                        isAddingAccount ? 'text-white' : 'text-gray-500'
                      }`}
                    />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-gray-700">
                      {isAddingAccount ? 'Close picker' : 'Add account'}
                    </p>
                    <p className="text-[11px] text-gray-500">
                      {isAddingAccount ? 'Choose a platform below' : 'Connect a new social'}
                    </p>
                  </div>
                </button>
              </div>
            )}

            {accounts.length === 0 && !isLoadingAccounts && !isAddingAccount && (
              <p className="mt-2 text-[11px] text-gray-400 text-center">
                No accounts yet. Tap <span className="font-semibold text-gray-600">Add account</span> above to connect one.
              </p>
            )}

            {/* Add-account picker — always mounted, animates open/close */}
            <div
              className={`grid transition-all duration-300 ease-out ${
                isAddingAccount
                  ? 'grid-rows-[1fr] opacity-100 mt-3'
                  : 'grid-rows-[0fr] opacity-0 mt-0'
              }`}
            >
              <div className="overflow-hidden">
                <div
                  className={`rounded-xl border border-purple-200 bg-gradient-to-br from-purple-50/80 to-white p-3 transform transition-transform duration-300 ease-out ${
                    isAddingAccount ? 'translate-y-0 scale-100' : '-translate-y-1 scale-[0.98]'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2.5">
                    <p className="text-xs font-bold text-gray-700">Pick a platform to connect</p>
                    <button
                      type="button"
                      onClick={() => {
                        setIsAddingAccount(false);
                        setConnectingPlatform(null);
                      }}
                      className="p-1 rounded-md hover:bg-white/80 text-gray-500 transition-colors"
                    >
                      <X size={14} />
                    </button>
                  </div>
                  <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
                    {CONNECTABLE_PLATFORMS.map((platform, i) => {
                      const meta = getPlatformMeta(platform);
                      const isConnecting = connectingPlatform === platform;
                      return (
                        <button
                          key={platform}
                          type="button"
                          onClick={() => handleConnect(platform)}
                          disabled={Boolean(connectingPlatform)}
                          style={
                            isAddingAccount
                              ? {
                                  animation: 'popIn 0.35s ease-out both',
                                  animationDelay: `${i * 40}ms`,
                                }
                              : undefined
                          }
                          className="flex flex-col items-center gap-1.5 px-2 py-3 rounded-xl bg-white border border-gray-200 hover:border-purple-400 hover:shadow-md hover:-translate-y-0.5 active:translate-y-0 disabled:opacity-60 disabled:cursor-not-allowed disabled:hover:translate-y-0 transition-all duration-200"
                        >
                          {isConnecting ? (
                            <div className="w-9 h-9 rounded-xl bg-gray-100 flex items-center justify-center">
                              <Loader2 size={16} className="animate-spin text-purple-600" />
                            </div>
                          ) : (
                            <PlatformBadge platform={platform} size={36} />
                          )}
                          <span className="text-[11px] font-semibold text-gray-700 truncate w-full text-center">
                            {meta.label}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                  <p className="mt-2.5 text-[10px] text-gray-500 text-center">
                    You'll be redirected to authorize the account, then brought back here.
                  </p>
                </div>
              </div>
            </div>

            {/* Upcoming posts on selected accounts */}
            <div
              className={`grid transition-all duration-300 ease-out ${
                selectedAccountIds.length > 0
                  ? 'grid-rows-[1fr] opacity-100 mt-3'
                  : 'grid-rows-[0fr] opacity-0 mt-0'
              }`}
            >
              <div className="overflow-hidden">
                <div
                  className={`rounded-xl border border-gray-200 bg-gray-50/70 p-3 transform transition-transform duration-300 ease-out ${
                    selectedAccountIds.length > 0
                      ? 'translate-y-0'
                      : '-translate-y-1'
                  }`}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <Clock size={13} className="text-gray-500" />
                    <p className="text-[11px] font-bold text-gray-600 uppercase tracking-wide">
                      Next scheduled post
                    </p>
                  </div>
                  <ul className="divide-y divide-gray-200/70">
                    {accounts
                      .filter((acc) => selectedAccountIds.includes(acc._id))
                      .map((acc, i) => {
                        const nick = getNickname(acc._id);
                        const meta = getPlatformMeta(acc.platform);
                        const next = nextByAccount[acc._id];
                        const formatted = next ? formatRelativeSchedule(next) : null;
                        return (
                          <li
                            key={acc._id}
                            style={{
                              animation: 'popIn 0.3s ease-out both',
                              animationDelay: `${i * 40}ms`,
                            }}
                            className="flex items-center gap-3 py-2 first:pt-1 last:pb-1"
                          >
                            <PlatformBadge platform={acc.platform} size={28} />
                            <div className="min-w-0 flex-1">
                              <p className="text-xs font-semibold text-gray-800 truncate">
                                {nick || meta.label}
                              </p>
                              {formatted ? (
                                <p className="text-[11px] text-gray-500 truncate">
                                  {formatted.day} · {formatted.time}
                                </p>
                              ) : (
                                <p className="text-[11px] text-gray-400 italic">
                                  Nothing scheduled
                                </p>
                              )}
                            </div>
                            {formatted ? (
                              <button
                                type="button"
                                onClick={() => {
                                  const d = formatted.date;
                                  const tzOffsetMs = d.getTimezoneOffset() * 60000;
                                  const local = new Date(d.getTime() - tzOffsetMs);
                                  setScheduledFor(local.toISOString().slice(0, 16));
                                }}
                                className="flex-shrink-0 text-[10px] font-bold px-2 py-1 rounded-md bg-white border border-gray-200 text-purple-600 hover:bg-purple-50 hover:border-purple-300 transition-colors"
                                title="Jump to this time"
                              >
                                {formatted.relative}
                              </button>
                            ) : (
                              <span className="flex-shrink-0 text-[10px] font-bold text-green-600 bg-green-50 border border-green-200 px-2 py-1 rounded-md">
                                free
                              </span>
                            )}
                          </li>
                        );
                      })}
                  </ul>
                </div>
              </div>
            </div>
          </section>

          {/* Caption */}
          <section>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Sparkles size={14} className="text-gray-400" />
                <h4 className="text-xs font-bold text-gray-700 uppercase tracking-wide">
                  Caption
                </h4>
              </div>
              <span className="text-[11px] text-gray-400 tabular-nums">
                {captionLength}
              </span>
            </div>
            <textarea
              value={caption}
              onChange={(e) => setCaption(e.target.value)}
              rows={4}
              placeholder="Write something your audience will love…"
              className="w-full px-3.5 py-3 rounded-xl border border-gray-200 focus:border-purple-400 focus:ring-2 focus:ring-purple-100 outline-none text-sm bg-white resize-none"
            />
          </section>

          {/* Schedule time */}
          <section>
            <div className="flex items-center gap-2 mb-2">
              <CalendarClock size={14} className="text-gray-400" />
              <h4 className="text-xs font-bold text-gray-700 uppercase tracking-wide">
                When
              </h4>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <input
                type="date"
                value={datePart}
                onChange={(e) => updateDatePart(e.target.value)}
                className="px-3.5 py-2.5 rounded-xl border border-gray-200 focus:border-purple-400 focus:ring-2 focus:ring-purple-100 outline-none text-sm bg-white"
              />
              <input
                type="time"
                value={timePart}
                onChange={(e) => updateTimePart(e.target.value)}
                className="px-3.5 py-2.5 rounded-xl border border-gray-200 focus:border-purple-400 focus:ring-2 focus:ring-purple-100 outline-none text-sm bg-white"
              />
            </div>
            <p className="text-[11px] text-gray-400 mt-1.5">
              Timezone: {timezone}
            </p>
          </section>

          {/* Status / error */}
          {statusMessage && (
            <div className="rounded-xl bg-green-50 border border-green-200 px-3.5 py-2.5 flex items-start gap-2">
              <CheckCircle2 size={16} className="text-green-600 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-green-800">{statusMessage}</p>
            </div>
          )}
          {error && (
            <div className="rounded-xl bg-red-50 border border-red-200 px-3.5 py-2.5">
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}
        </div>

        {/* Sticky footer */}
        <div className="px-5 py-3 border-t border-gray-100 bg-white flex-shrink-0">
          <button
            onClick={handleSchedule}
            disabled={!canSubmit}
            className="w-full px-4 py-3 rounded-xl bg-gradient-to-r from-purple-600 to-purple-500 text-white font-semibold hover:from-purple-700 hover:to-purple-600 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 text-sm transition-all duration-200 shadow-md shadow-purple-500/20"
          >
            {isScheduling ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
            {isScheduling ? 'Scheduling…' : 'Schedule Post'}
          </button>
        </div>

        {/* Fullscreen preview lightbox (overlays the whole modal panel) */}
        {isLightboxOpen && hasPreview && (
          <PreviewLightbox
            isVideo={isVideo}
            isCarousel={isCarousel}
            mediaUrls={mediaUrls}
            items={previewItems}
            activeIndex={activeSlide}
            onActiveChange={setActiveSlide}
            onClose={() => setIsLightboxOpen(false)}
          />
        )}
      </div>
    </div>
  );
}
