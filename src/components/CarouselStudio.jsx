import React, { useEffect, useMemo, useState } from 'react';
import { CheckCircle2, Image, Link2, Loader2, RefreshCw, Send } from 'lucide-react';
import {
  createCarousel,
  listCarousels,
  createLatePost,
  createLateProfile,
  DEFAULT_SESSION_ID,
  getLateConnectUrl,
  listLateAccounts,
  listLatePosts,
  startCarouselGeneration,
  getGeneration,
} from '../lib/lateApi';

function toDatetimeLocal(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const tzOffsetMs = d.getTimezoneOffset() * 60000;
  const local = new Date(d.getTime() - tzOffsetMs);
  return local.toISOString().slice(0, 16);
}

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

const SOCIAL_PLATFORMS = [
  'instagram',
  'tiktok',
  'youtube',
  'facebook',
  'linkedin',
  'threads',
  'twitter',
];

function CarouselStudio() {
  const [prompt, setPrompt] = useState('');
  const [timezone, setTimezone] = useState(Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC');
  const [carousel, setCarousel] = useState(null);
  const [savedCarousels, setSavedCarousels] = useState([]);
  const [isLoadingSaved, setIsLoadingSaved] = useState(false);
  const [caption, setCaption] = useState('');
  const [scheduledFor, setScheduledFor] = useState('');
  const [profileName, setProfileName] = useState('Lumeet Profile');
  const [profileId, setProfileId] = useState('');
  const [platformToConnect, setPlatformToConnect] = useState('instagram');
  const [accounts, setAccounts] = useState([]);
  const [selectedAccountIds, setSelectedAccountIds] = useState([]);
  const [statusMessage, setStatusMessage] = useState('');
  const [error, setError] = useState('');
  const [scheduledPosts, setScheduledPosts] = useState([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isCreatingProfile, setIsCreatingProfile] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isLoadingAccounts, setIsLoadingAccounts] = useState(false);
  const [isLoadingPosts, setIsLoadingPosts] = useState(false);
  const [isScheduling, setIsScheduling] = useState(false);

  const selectedPlatforms = useMemo(
    () => accounts
      .filter((acc) => selectedAccountIds.includes(acc._id))
      .map((acc) => ({ platform: acc.platform, accountId: acc._id }))
      .filter((t) => t.platform && t.accountId),
    [accounts, selectedAccountIds],
  );

  const handleGenerate = async () => {
    setIsGenerating(true);
    setError('');
    setStatusMessage('Generating carousel in background...');
    try {
      // Start async generation via Generation Center endpoint
      const { generationId } = await startCarouselGeneration({ prompt, timezone });

      // Poll until done
      const poll = async () => {
        const gen = await getGeneration(generationId);
        if (gen.status === 'completed') {
          const output = gen.output || {};
          const carouselData = output.carousel || output;
          setCarousel(carouselData);
          setCaption(
            [carouselData.captionDraft, ...(carouselData.hashtags || [])]
              .filter(Boolean)
              .join('\n\n')
              .trim(),
          );
          setScheduledFor(toDatetimeLocal(carouselData.suggestedScheduledFor));
          setStatusMessage('Carousel generated. Review slides and schedule when ready.');
          setIsGenerating(false);
          await handleLoadSavedCarousels();
          return;
        }
        if (gen.status === 'failed') {
          setError(gen.error || 'Carousel generation failed.');
          setIsGenerating(false);
          return;
        }
        // Still processing — poll again
        setTimeout(poll, 2500);
      };
      setTimeout(poll, 2000);
    } catch (err) {
      setError(err.message);
      setIsGenerating(false);
    }
  };

  const handleCreateProfile = async () => {
    setIsCreatingProfile(true);
    setError('');
    setStatusMessage('');
    try {
      const data = await createLateProfile({
        sessionId: DEFAULT_SESSION_ID,
        name: profileName,
        description: 'Created from Carousel Studio',
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
        setStatusMessage('No connected accounts found in Late yet.');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoadingAccounts(false);
    }
  };

  const handleLoadSavedCarousels = async () => {
    setIsLoadingSaved(true);
    setError('');
    try {
      const data = await listCarousels();
      setSavedCarousels(data.carousels || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoadingSaved(false);
    }
  };

  const handleLoadScheduledPosts = async () => {
    setIsLoadingPosts(true);
    setError('');
    try {
      const data = await listLatePosts({
        sessionId: DEFAULT_SESSION_ID,
        profileId: profileId || undefined,
        status: 'scheduled',
        limit: 25,
      });
      const rawPosts = data.posts || data.results || data.data || [];
      const normalized = rawPosts
        .map((post) => {
          const platforms = (post.platforms || [])
            .map((p) => (typeof p === 'string' ? p : p?.platform || p?.provider || ''))
            .filter(Boolean);
          return {
            id: String(post?._id ?? post?.id ?? ''),
            status: String(post?.status ?? post?.state ?? post?.publishStatus ?? ''),
            scheduledFor: post?.scheduledFor || post?.scheduled_at || post?.scheduledTime || '',
            content: String(post?.content ?? post?.caption ?? post?.text ?? ''),
            platforms,
          };
        })
        .filter((p) => p.id);
      setScheduledPosts(normalized);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoadingPosts(false);
    }
  };

  const selectSavedCarousel = (item) => {
    setCarousel(item);
    setCaption(
      [item.captionDraft, ...(item.hashtags || [])]
        .filter(Boolean)
        .join('\n\n')
        .trim(),
    );
    const suggested = toDatetimeLocal(item.suggestedScheduledFor);
    const suggestedDate = suggested ? new Date(suggested) : null;
    if (!suggestedDate || Number.isNaN(suggestedDate.getTime()) || suggestedDate <= new Date()) {
      setScheduledFor(nextSlotDatetimeLocal());
    } else {
      setScheduledFor(suggested);
    }
    setTimezone(item.timezone || timezone);
    setStatusMessage(`Loaded saved carousel ${item.carouselId}.`);
  };

  useEffect(() => {
    // Auto-load existing Late-connected accounts so users can schedule quickly.
    handleLoadAccounts();
    handleLoadSavedCarousels();
    handleLoadScheduledPosts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSchedule = async () => {
    if (!carousel) return;
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
      const scheduledIso = toIsoLocal(scheduledFor);
      if (!scheduledIso) {
        throw new Error('Pick a valid schedule date/time.');
      }
      const payload = {
        sessionId: DEFAULT_SESSION_ID,
        profileId: resolvedProfileId,
        content: caption,
        platforms: selectedPlatforms,
        publishNow: false,
        timezone,
        scheduledFor: scheduledIso,
        mediaUrls: carousel.mediaUrls || [],
      };
      const data = await createLatePost(payload);
      const postId = data?.post?._id || data?._id || 'created';
      setStatusMessage(`Carousel scheduled successfully (${postId}).`);
      await handleLoadScheduledPosts();
    } catch (err) {
      setError(err.message);
    } finally {
      setIsScheduling(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-8 text-center">
        <div className="flex items-center justify-center gap-3">
          <Image size={24} className="text-purple-600" />
          <h2 className="text-3xl font-bold text-gray-900">Carousel Studio</h2>
        </div>
        <p className="text-gray-600 mt-2">Generate a carousel from a prompt, review it, then schedule in one flow.</p>
      </div>

      <div className="glass-card border border-white/40 rounded-2xl p-5 mb-6">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-lg font-bold text-gray-900">Scheduled Posts</h3>
          <button
            onClick={handleLoadScheduledPosts}
            disabled={isLoadingPosts}
            className="px-3 py-2 rounded-xl bg-gray-100 text-gray-700 hover:bg-gray-200 disabled:opacity-50 flex items-center gap-2"
          >
            <RefreshCw size={14} className={isLoadingPosts ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
        {scheduledPosts.length === 0 ? (
          <p className="text-sm text-gray-600">No scheduled posts found yet.</p>
        ) : (
          <div className="space-y-2">
            {scheduledPosts.map((post) => (
              <div key={post.id} className="rounded-xl border border-gray-200 bg-white p-3">
                <div className="flex items-center justify-between mb-1">
                  <p className="text-xs text-gray-500">{post.id}</p>
                  <p className="text-xs font-semibold text-purple-700">{post.status || 'scheduled'}</p>
                </div>
                <p className="text-xs text-gray-600 mb-1">{post.scheduledFor || 'No schedule time'}</p>
                <p className="text-sm text-gray-900 line-clamp-2">{post.content || 'No content'}</p>
                <p className="text-xs text-gray-500 mt-1">{post.platforms.join(', ') || 'No platform info'}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="glass-card border border-white/40 rounded-2xl p-5 mb-6">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-lg font-bold text-gray-900">Saved Carousels</h3>
          <button
            onClick={handleLoadSavedCarousels}
            disabled={isLoadingSaved}
            className="px-3 py-2 rounded-xl bg-gray-100 text-gray-700 hover:bg-gray-200 disabled:opacity-50 flex items-center gap-2"
          >
            <RefreshCw size={14} className={isLoadingSaved ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
        {savedCarousels.length === 0 ? (
          <p className="text-sm text-gray-600">No saved carousels yet. Generate one and it will appear here.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {savedCarousels.slice(0, 9).map((item) => {
              const preview = item?.slides?.[0]?.url;
              return (
                <button
                  key={item.carouselId}
                  onClick={() => selectSavedCarousel(item)}
                  className="text-left rounded-xl border border-gray-200 bg-white hover:border-purple-400 transition-colors overflow-hidden"
                >
                  {preview && (
                    <img src={preview} alt={item.carouselId} className="w-full aspect-square object-cover" />
                  )}
                  <div className="p-2">
                    <p className="text-xs text-gray-500">{item.createdAt || ''}</p>
                    <p className="text-sm font-semibold text-gray-900 truncate">{item.prompt || 'Saved carousel'}</p>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      <div className="glass-card border border-white/40 rounded-2xl p-5 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={3}
            className="md:col-span-3 px-3 py-2 rounded-xl border border-gray-200 focus:border-purple-400 outline-none"
            placeholder="Prompt (e.g., a carousel giving 7 tips for more efficient studying)"
          />
          <div className="flex flex-col gap-3">
            <input
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
              className="px-3 py-2 rounded-xl border border-gray-200 focus:border-purple-400 outline-none"
              placeholder="Timezone"
            />
            <button
              onClick={handleGenerate}
              disabled={isGenerating || !prompt.trim()}
              className="px-4 py-2 rounded-xl bg-gradient-to-r from-purple-600 to-purple-500 text-white hover:from-purple-700 hover:to-purple-600 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {isGenerating && <Loader2 size={16} className="animate-spin" />}
              {isGenerating ? 'Generating...' : 'Generate Carousel'}
            </button>
          </div>
        </div>
      </div>

      {carousel && (
        <>
          <div className="glass-card border border-white/40 rounded-2xl p-5 mb-6">
            <h3 className="text-lg font-bold text-gray-900 mb-3">Review Slides</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {(carousel.slides || []).map((slide) => (
                <div key={slide.object || slide.url} className="rounded-xl overflow-hidden border border-gray-200 bg-white">
                  <img src={slide.url} alt={slide.kind || 'carousel slide'} className="w-full aspect-square object-cover" />
                  <div className="px-2 py-1 text-xs text-gray-600">{slide.kind}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="glass-card border border-white/40 rounded-2xl p-5">
            <h3 className="text-lg font-bold text-gray-900 mb-3">Schedule Carousel</h3>

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
              You can skip profile creation if your Late account already has connected accounts.
            </p>

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

            {accounts.length > 0 && (
              <div className="mb-4 border border-gray-200 rounded-xl p-3 max-h-36 overflow-y-auto">
                {accounts.map((acc) => (
                  <label key={acc._id} className="flex items-center gap-2 py-1 text-sm text-gray-800">
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
                    <span>{acc.platform}</span>
                    <span className="text-gray-500">{acc._id}</span>
                  </label>
                ))}
              </div>
            )}

            <textarea
              value={caption}
              onChange={(e) => setCaption(e.target.value)}
              rows={4}
              className="w-full mb-3 px-3 py-2 rounded-xl border border-gray-200 focus:border-purple-400 outline-none"
              placeholder="Caption with hashtags"
            />

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
              <input
                type="datetime-local"
                value={scheduledFor}
                onChange={(e) => setScheduledFor(e.target.value)}
                className="px-3 py-2 rounded-xl border border-gray-200 focus:border-purple-400 outline-none"
              />
              <input
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
                className="px-3 py-2 rounded-xl border border-gray-200 focus:border-purple-400 outline-none"
                placeholder="Timezone"
              />
            </div>

            <button
              onClick={handleSchedule}
              disabled={isScheduling || selectedPlatforms.length === 0 || !caption.trim() || !scheduledFor}
              className="w-full px-4 py-3 rounded-xl bg-gradient-to-r from-purple-600 to-purple-500 text-white font-semibold hover:from-purple-700 hover:to-purple-600 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              <Send size={16} />
              {isScheduling ? 'Scheduling...' : 'Schedule Carousel'}
            </button>
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
    </div>
  );
}

export default CarouselStudio;
