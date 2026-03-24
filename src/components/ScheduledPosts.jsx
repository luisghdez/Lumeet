import React, { useEffect, useMemo, useState } from 'react';
import {
  CalendarDays,
  List,
  RefreshCw,
  Play,
  Filter,
  Clock,
  Image as ImageIcon,
} from 'lucide-react';
import {
  DEFAULT_SESSION_ID,
  listLateAccounts,
  listLatePosts,
} from '../lib/lateApi';
import { accountLabel } from '../lib/accountNicknames';
import MiniCalendar, { isoToDateKey, toDateKey } from './MiniCalendar';

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function formatScheduledDate(iso) {
  if (!iso) return 'No date';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

function formatScheduledTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
}

function normalizePosts(rawPosts) {
  return rawPosts
    .map((post) => {
      const platforms = (post.platforms || []).map((p) => {
        if (typeof p === 'string') return { platform: p, accountId: '' };
        return {
          platform: String(p?.platform || p?.provider || ''),
          accountId: String(p?.accountId || p?.account_id || ''),
        };
      }).filter((p) => p.platform);

      const mediaUrls = post.mediaUrls
        || (post.media || []).map((m) => (typeof m === 'string' ? m : m?.url)).filter(Boolean)
        || (post.mediaItems || []).map((m) => m?.url).filter(Boolean)
        || [];

      return {
        id: String(post?._id ?? post?.id ?? ''),
        status: String(post?.status ?? post?.state ?? post?.publishStatus ?? ''),
        scheduledFor: post?.scheduledFor || post?.scheduled_at || post?.scheduledTime || '',
        content: String(post?.content ?? post?.caption ?? post?.text ?? ''),
        platforms,
        mediaUrls,
        accountIds: platforms.map((p) => p.accountId).filter(Boolean),
      };
    })
    .filter((p) => p.id);
}

const PLATFORM_COLORS = {
  instagram: 'bg-pink-100 text-pink-700',
  tiktok: 'bg-gray-900 text-white',
  youtube: 'bg-red-100 text-red-700',
  facebook: 'bg-blue-100 text-blue-700',
  linkedin: 'bg-sky-100 text-sky-700',
  threads: 'bg-gray-100 text-gray-700',
  twitter: 'bg-cyan-100 text-cyan-700',
};

/* ------------------------------------------------------------------ */
/*  Post Card                                                          */
/* ------------------------------------------------------------------ */

function PostCard({ post }) {
  const hasMedia = post.mediaUrls.length > 0;
  const isVideo = hasMedia && post.mediaUrls.some((u) =>
    /\.(mp4|mov|webm)(\?|$)/i.test(u),
  );

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 hover:shadow-sm transition-shadow">
      <div className="flex gap-4">
        {/* Media thumbnail */}
        {hasMedia && (
          <div className="flex-shrink-0 w-16 h-16 rounded-lg overflow-hidden bg-gray-100 border border-gray-200 relative">
            {isVideo ? (
              <>
                <video
                  src={post.mediaUrls[0]}
                  className="w-full h-full object-cover"
                  muted
                  preload="metadata"
                />
                <div className="absolute inset-0 flex items-center justify-center bg-black/20">
                  <Play size={16} className="text-white drop-shadow" />
                </div>
              </>
            ) : (
              <img
                src={post.mediaUrls[0]}
                alt=""
                className="w-full h-full object-cover"
              />
            )}
            {post.mediaUrls.length > 1 && (
              <span className="absolute bottom-0.5 right-0.5 bg-black/60 text-white text-[9px] px-1 rounded">
                +{post.mediaUrls.length - 1}
              </span>
            )}
          </div>
        )}

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-2">
              <Clock size={12} className="text-gray-400" />
              <span className="text-xs font-medium text-gray-600">
                {formatScheduledTime(post.scheduledFor)}
              </span>
            </div>
            <span className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full ${
              post.status === 'published'
                ? 'bg-green-100 text-green-700'
                : post.status === 'failed'
                  ? 'bg-red-100 text-red-700'
                  : 'bg-purple-100 text-purple-700'
            }`}>
              {post.status || 'scheduled'}
            </span>
          </div>

          <p className="text-sm text-gray-900 line-clamp-2 mb-2">{post.content || 'No content'}</p>

          <div className="flex flex-wrap gap-1.5">
            {post.platforms.map((p, i) => (
              <span
                key={i}
                className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${
                  PLATFORM_COLORS[p.platform] || 'bg-gray-100 text-gray-600'
                }`}
              >
                {p.platform}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main Component                                                     */
/* ------------------------------------------------------------------ */

export default function ScheduledPosts() {
  const [posts, setPosts] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [isLoadingPosts, setIsLoadingPosts] = useState(false);
  const [isLoadingAccounts, setIsLoadingAccounts] = useState(false);
  const [error, setError] = useState('');
  const [viewMode, setViewMode] = useState('calendar'); // 'calendar' | 'list'
  const [selectedAccount, setSelectedAccount] = useState(''); // '' = all
  const [selectedDay, setSelectedDay] = useState(''); // YYYY-MM-DD

  /* ---------- Data loading ---------- */

  const loadPosts = async () => {
    setIsLoadingPosts(true);
    setError('');
    try {
      const data = await listLatePosts({
        sessionId: DEFAULT_SESSION_ID,
        status: 'scheduled',
        limit: 100,
      });
      const rawPosts = data.posts || data.results || data.data || [];
      setPosts(normalizePosts(rawPosts));
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoadingPosts(false);
    }
  };

  const loadAccounts = async () => {
    setIsLoadingAccounts(true);
    try {
      const data = await listLateAccounts({ sessionId: DEFAULT_SESSION_ID });
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
    } catch {
      // non-critical
    } finally {
      setIsLoadingAccounts(false);
    }
  };

  useEffect(() => {
    loadPosts();
    loadAccounts();
  }, []);

  /* ---------- Filtering ---------- */

  const filteredPosts = useMemo(() => {
    if (!selectedAccount) return posts;
    return posts.filter((p) =>
      p.accountIds.includes(selectedAccount) ||
      p.platforms.some((pl) => pl.accountId === selectedAccount),
    );
  }, [posts, selectedAccount]);

  // Posts grouped by day for calendar
  const postsByDay = useMemo(() => {
    const map = {};
    filteredPosts.forEach((p) => {
      const key = isoToDateKey(p.scheduledFor);
      if (!key) return;
      if (!map[key]) map[key] = [];
      map[key].push(p);
    });
    return map;
  }, [filteredPosts]);

  const scheduledDateIsos = useMemo(
    () => filteredPosts.map((p) => p.scheduledFor).filter(Boolean),
    [filteredPosts],
  );

  // Posts for the selected day
  const dayPosts = useMemo(() => {
    if (!selectedDay) return [];
    return (postsByDay[selectedDay] || []).sort((a, b) => {
      const da = new Date(a.scheduledFor || 0);
      const db = new Date(b.scheduledFor || 0);
      return da - db;
    });
  }, [selectedDay, postsByDay]);

  // Sorted posts for list view
  const sortedPosts = useMemo(
    () => [...filteredPosts].sort((a, b) => {
      const da = new Date(a.scheduledFor || 0);
      const db = new Date(b.scheduledFor || 0);
      return da - db;
    }),
    [filteredPosts],
  );

  /* ---------- Render ---------- */

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-8 text-center">
        <div className="flex items-center justify-center gap-3">
          <CalendarDays size={24} className="text-purple-600" />
          <h2 className="text-3xl font-bold text-gray-900">Scheduled Posts</h2>
        </div>
        <p className="text-gray-600 mt-2">
          View and manage your upcoming scheduled posts across all accounts.
        </p>
      </div>

      {/* Controls bar */}
      <div className="glass-card border border-white/40 rounded-2xl p-4 mb-6">
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
          {/* Account filter */}
          <div className="flex items-center gap-2 flex-1 min-w-0">
            <Filter size={16} className="text-gray-400 flex-shrink-0" />
            <select
              value={selectedAccount}
              onChange={(e) => setSelectedAccount(e.target.value)}
              className="flex-1 min-w-0 px-3 py-2 rounded-xl border border-gray-200 focus:border-purple-400 outline-none text-sm bg-white"
            >
              <option value="">All Accounts</option>
              {accounts.map((acc) => (
                <option key={acc._id} value={acc._id}>
                  {accountLabel(acc)}
                </option>
              ))}
            </select>
          </div>

          {/* View toggle */}
          <div className="flex items-center gap-1 bg-gray-100 rounded-xl p-1">
            <button
              onClick={() => setViewMode('calendar')}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-1.5 ${
                viewMode === 'calendar'
                  ? 'bg-white text-purple-700 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              <CalendarDays size={14} />
              Calendar
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-1.5 ${
                viewMode === 'list'
                  ? 'bg-white text-purple-700 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              <List size={14} />
              List
            </button>
          </div>

          {/* Refresh */}
          <button
            onClick={loadPosts}
            disabled={isLoadingPosts}
            className="px-3 py-2 rounded-xl bg-gray-100 text-gray-700 hover:bg-gray-200 disabled:opacity-50 flex items-center gap-2 text-sm"
          >
            <RefreshCw size={14} className={isLoadingPosts ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <p className="mb-4 text-sm text-red-600 bg-red-50 rounded-xl px-4 py-2">{error}</p>
      )}

      {/* Calendar View */}
      {viewMode === 'calendar' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Calendar */}
          <div className="lg:col-span-2 glass-card border border-white/40 rounded-2xl p-5">
            <MiniCalendar
              scheduledDates={scheduledDateIsos}
              selectedDate={selectedDay}
              onSelectDate={setSelectedDay}
            />

            {/* Day summary below calendar on mobile */}
            <div className="mt-4 lg:hidden">
              <DayPanel
                selectedDay={selectedDay}
                dayPosts={dayPosts}
              />
            </div>
          </div>

          {/* Day detail panel – desktop sidebar */}
          <div className="hidden lg:block glass-card border border-white/40 rounded-2xl p-5">
            <DayPanel
              selectedDay={selectedDay}
              dayPosts={dayPosts}
            />
          </div>
        </div>
      )}

      {/* List View */}
      {viewMode === 'list' && (
        <div className="glass-card border border-white/40 rounded-2xl p-5">
          {sortedPosts.length === 0 ? (
            <EmptyState />
          ) : (
            <div className="space-y-3">
              {sortedPosts.map((post) => (
                <div key={post.id}>
                  <p className="text-xs font-medium text-gray-400 mb-1">
                    {formatScheduledDate(post.scheduledFor)}
                  </p>
                  <PostCard post={post} />
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Sub-components                                                     */
/* ------------------------------------------------------------------ */

function DayPanel({ selectedDay, dayPosts }) {
  if (!selectedDay) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <CalendarDays size={32} className="text-gray-300 mb-3" />
        <p className="text-sm text-gray-500">Select a day on the calendar to see scheduled posts.</p>
      </div>
    );
  }

  const dateLabel = new Date(selectedDay + 'T00:00:00').toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  });

  return (
    <div>
      <h3 className="text-sm font-bold text-gray-900 mb-1">{dateLabel}</h3>
      <p className="text-xs text-gray-500 mb-4">
        {dayPosts.length} post{dayPosts.length !== 1 ? 's' : ''} scheduled
      </p>

      {dayPosts.length === 0 ? (
        <p className="text-sm text-gray-400 text-center py-6">No posts on this day.</p>
      ) : (
        <div className="space-y-3">
          {dayPosts.map((post) => (
            <PostCard key={post.id} post={post} />
          ))}
        </div>
      )}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center text-center py-16">
      <CalendarDays size={40} className="text-gray-300 mb-4" />
      <h3 className="text-lg font-semibold text-gray-700 mb-1">No scheduled posts</h3>
      <p className="text-sm text-gray-500 max-w-sm">
        Schedule posts from the Carousel Studio, Video Library, or Generation Center to see them here.
      </p>
    </div>
  );
}
