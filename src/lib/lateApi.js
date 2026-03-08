const DEFAULT_SESSION_ID = 'local-dev-session';

async function request(path, options = {}) {
  const resp = await fetch(path, options);
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw new Error(data.detail || data.message || `Request failed (${resp.status})`);
  }
  return data;
}

export async function createLateProfile({ name, description = '', sessionId = DEFAULT_SESSION_ID }) {
  return request('/api/late/profiles', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sessionId, name, description }),
  });
}

export async function getLateConnectUrl({
  platform,
  profileId,
  redirectUrl,
  sessionId = DEFAULT_SESSION_ID,
}) {
  const params = new URLSearchParams({
    platform,
    sessionId,
  });
  if (profileId) params.set('profileId', profileId);
  if (redirectUrl) params.set('redirectUrl', redirectUrl);
  return request(`/api/late/connect-url?${params.toString()}`);
}

export async function listLateAccounts({ sessionId = DEFAULT_SESSION_ID, profileId } = {}) {
  const params = new URLSearchParams({ sessionId });
  if (profileId) params.set('profileId', profileId);
  return request(`/api/late/accounts?${params.toString()}`);
}

export async function createLatePost(payload) {
  return request('/api/late/posts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export { DEFAULT_SESSION_ID };
