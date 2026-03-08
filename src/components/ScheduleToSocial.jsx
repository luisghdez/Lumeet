import React, { useEffect, useMemo, useState } from 'react';
import { CalendarClock, Link2, RefreshCw, Send, CheckCircle2 } from 'lucide-react';
import {
  createLatePost,
  createLateProfile,
  getLateConnectUrl,
  listLateAccounts,
  DEFAULT_SESSION_ID,
} from '../lib/lateApi';

const SOCIAL_PLATFORMS = [
  'twitter',
  'instagram',
  'facebook',
  'linkedin',
  'tiktok',
  'youtube',
  'pinterest',
  'reddit',
  'bluesky',
  'threads',
  'googlebusiness',
  'telegram',
  'snapchat',
];

function toAbsoluteUrl(urlOrPath) {
  if (!urlOrPath) return '';
  if (urlOrPath.startsWith('http://') || urlOrPath.startsWith('https://')) {
    return urlOrPath;
  }
  return `${window.location.origin}${urlOrPath}`;
}

function toIsoLocal(datetimeLocal) {
  if (!datetimeLocal) return null;
  const localDate = new Date(datetimeLocal);
  if (Number.isNaN(localDate.getTime())) return null;
  return localDate.toISOString();
}

function ScheduleToSocial({ jobId, resultUrl }) {
  const [profileId, setProfileId] = useState('');
  const [profileName, setProfileName] = useState('Lumeet Profile');
  const [caption, setCaption] = useState('Generated with Lumeet');
  const [platformToConnect, setPlatformToConnect] = useState('twitter');
  const [accounts, setAccounts] = useState([]);
  const [selectedAccountIds, setSelectedAccountIds] = useState([]);
  const [publishNow, setPublishNow] = useState(false);
  const [scheduledFor, setScheduledFor] = useState('');
  const [timezone, setTimezone] = useState(Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC');
  const [includeGeneratedVideo, setIncludeGeneratedVideo] = useState(true);
  const [statusMessage, setStatusMessage] = useState('');
  const [error, setError] = useState('');
  const [isCreatingProfile, setIsCreatingProfile] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isLoadingAccounts, setIsLoadingAccounts] = useState(false);
  const [isScheduling, setIsScheduling] = useState(false);

  const hasAccounts = accounts.length > 0;

  const selectedPlatforms = useMemo(
    () => accounts
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
      setAccounts(data.accounts || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoadingAccounts(false);
    }
  };

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('late_connected') === '1') {
      setStatusMessage('Social account connected. Refreshing accounts...');
      loadAccounts();
      params.delete('late_connected');
      const cleanQuery = params.toString();
      const nextUrl = `${window.location.pathname}${cleanQuery ? `?${cleanQuery}` : ''}`;
      window.history.replaceState({}, '', nextUrl);
    }
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
    setIsScheduling(true);
    setError('');
    setStatusMessage('');
    try {
      const payload = {
        sessionId: DEFAULT_SESSION_ID,
        profileId: profileId || undefined,
        content: caption,
        platforms: selectedPlatforms,
        publishNow,
        timezone: publishNow ? undefined : timezone,
        scheduledFor: publishNow ? undefined : toIsoLocal(scheduledFor),
        includeResultVideo: includeGeneratedVideo,
        jobId: jobId || undefined,
        mediaUrls: includeGeneratedVideo && resultUrl ? [toAbsoluteUrl(resultUrl)] : [],
      };
      const data = await createLatePost(payload);
      const postId = data?.post?._id || data?._id || 'created';
      setStatusMessage(`Post scheduled successfully (${postId}).`);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsScheduling(false);
    }
  };

  return (
    <div className="mt-8 w-full max-w-3xl glass-card border border-white/40 rounded-2xl p-5">
      <div className="flex items-center gap-3 mb-4">
        <CalendarClock size={20} className="text-purple-600" />
        <h3 className="text-lg font-bold text-gray-900">Schedule to Social</h3>
      </div>

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
          onClick={loadAccounts}
          disabled={isLoadingAccounts}
          className="px-4 py-2 rounded-xl bg-gray-100 text-gray-700 hover:bg-gray-200 disabled:opacity-50 flex items-center justify-center gap-2"
        >
          <RefreshCw size={16} className={isLoadingAccounts ? 'animate-spin' : ''} />
          Refresh Accounts
        </button>
      </div>

      {hasAccounts && (
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
        rows={3}
        className="w-full mb-3 px-3 py-2 rounded-xl border border-gray-200 focus:border-purple-400 outline-none"
        placeholder="Caption/content"
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
        <label className="flex items-center gap-2 text-sm text-gray-700">
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
          placeholder="Timezone (e.g. America/New_York)"
        />
      </div>

      <label className="flex items-center gap-2 text-sm text-gray-700 mb-4">
        <input
          type="checkbox"
          checked={includeGeneratedVideo}
          onChange={(e) => setIncludeGeneratedVideo(e.target.checked)}
        />
        Include generated video URL from this job
      </label>

      <button
        onClick={handleSchedule}
        disabled={isScheduling || selectedPlatforms.length === 0 || !caption.trim()}
        className="w-full px-4 py-3 rounded-xl bg-gradient-to-r from-purple-600 to-purple-500 text-white font-semibold hover:from-purple-700 hover:to-purple-600 disabled:opacity-50 flex items-center justify-center gap-2"
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
  );
}

export default ScheduleToSocial;
