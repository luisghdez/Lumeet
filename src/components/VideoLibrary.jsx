import React, { useEffect, useMemo, useState } from 'react';
import { CheckCircle2, Film, Link2, Play, RefreshCw, Send } from 'lucide-react';
import AccountRow from './AccountRow';
import {
  createLatePost,
  createLateProfile,
  DEFAULT_SESSION_ID,
  getLateConnectUrl,
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

const SOCIAL_PLATFORMS = [
  'instagram',
  'tiktok',
  'youtube',
  'facebook',
  'linkedin',
  'threads',
  'twitter',
];

function VideoLibrary() {
  const [videos, setVideos] = useState([]);
  const [isLoadingVideos, setIsLoadingVideos] = useState(false);
  const [selectedVideo, setSelectedVideo] = useState(null);
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

  const selectedPlatforms = useMemo(
    () =>
      accounts
        .filter((acc) => selectedAccountIds.includes(acc._id))
        .map((acc) => ({ platform: acc.platform, accountId: acc._id }))
        .filter((t) => t.platform && t.accountId),
    [accounts, selectedAccountIds],
  );

  // ---- Data loading ----

  const handleLoadVideos = async () => {
    setIsLoadingVideos(true);
    setError('');
    try {
      const data = await listVideos();
      setVideos(data.videos || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoadingVideos(false);
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

  // ---- Render ----

  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-8 text-center">
        <div className="flex items-center justify-center gap-3">
          <Film size={24} className="text-purple-600" />
          <h2 className="text-3xl font-bold text-gray-900">Video Library</h2>
        </div>
        <p className="text-gray-600 mt-2">Browse past generated videos and schedule or publish them.</p>
      </div>

      {/* Video Gallery */}
      <div className="glass-card border border-white/40 rounded-2xl p-5 mb-6">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-lg font-bold text-gray-900">Generated Videos</h3>
          <button
            onClick={handleLoadVideos}
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
