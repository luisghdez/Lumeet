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

export async function listLatePosts({
  sessionId = DEFAULT_SESSION_ID,
  profileId,
  status,
  limit = 25,
} = {}) {
  const params = new URLSearchParams({ sessionId, limit: String(limit) });
  if (profileId) params.set('profileId', profileId);
  if (status) params.set('status', status);
  return request(`/api/late/posts?${params.toString()}`);
}

export async function createCarousel({ prompt, timezone, hookStyle = 'illustrated' }) {
  return request('/api/carousels', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt, timezone, hook_style: hookStyle }),
  });
}

export async function getCarousel(carouselId) {
  return request(`/api/carousels/${encodeURIComponent(carouselId)}`);
}

export async function listCarousels() {
  return request('/api/carousels');
}

export async function listVideos() {
  return request('/api/videos');
}

export async function getVideo(videoId) {
  return request(`/api/videos/${encodeURIComponent(videoId)}`);
}

// ---------------------------------------------------------------------------
// Generation Center API
// ---------------------------------------------------------------------------

export async function startVideoGeneration(formData) {
  const resp = await fetch('/api/generations/video', { method: 'POST', body: formData });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(data.detail || `Upload failed (${resp.status})`);
  return data;
}

export async function startCarouselGeneration({ prompt, timezone, hookStyle = 'illustrated' }) {
  return request('/api/generations/carousel', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt, timezone, hook_style: hookStyle }),
  });
}

export async function listGenerations(limit = 50) {
  return request(`/api/generations?limit=${limit}`);
}

export async function getGeneration(generationId) {
  return request(`/api/generations/${encodeURIComponent(generationId)}`);
}

export async function patchGeneration(generationId, updates) {
  return request(`/api/generations/${encodeURIComponent(generationId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  });
}

export async function cancelGeneration(generationId) {
  return request(`/api/generations/${encodeURIComponent(generationId)}/cancel`, {
    method: 'POST',
  });
}

export { DEFAULT_SESSION_ID };
