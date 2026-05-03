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

export async function createCarousel({
  prompt,
  timezone,
  hookStyle = 'illustrated',
  carouselStyle = 'illustrated',
}) {
  return request('/api/carousels', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      prompt,
      timezone,
      hook_style: hookStyle,
      carousel_style: carouselStyle,
    }),
  });
}

export async function getCarousel(carouselId) {
  return request(`/api/carousels/${encodeURIComponent(carouselId)}`);
}

export async function listCarousels() {
  return request('/api/carousels');
}

export async function listVideos({ limit = 0, offset = 0 } = {}) {
  const params = new URLSearchParams();
  if (limit) params.set('limit', String(limit));
  if (offset) params.set('offset', String(offset));
  const qs = params.toString();
  return request(`/api/videos${qs ? `?${qs}` : ''}`);
}

export async function getVideo(videoId) {
  return request(`/api/videos/${encodeURIComponent(videoId)}`);
}

export async function deleteVideo(videoId) {
  return request(`/api/videos/${encodeURIComponent(videoId)}`, { method: 'DELETE' });
}

// ---------------------------------------------------------------------------
// Generation Center API
// ---------------------------------------------------------------------------

export async function startVideoGeneration(formData, { noTrim = false } = {}) {
  const path = noTrim ? '/api/generations/video/no-trim' : '/api/generations/video';
  const resp = await fetch(path, { method: 'POST', body: formData });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(data.detail || `Upload failed (${resp.status})`);
  return data;
}

export async function startCarouselGeneration({
  prompt,
  timezone,
  hookStyle = 'illustrated',
  carouselStyle = 'illustrated',
}) {
  return request('/api/generations/carousel', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      prompt,
      timezone,
      hook_style: hookStyle,
      carousel_style: carouselStyle,
    }),
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

/** Remove a completed or failed generation from the Generation Center list. */
export async function dismissGeneration(generationId) {
  return request(`/api/generations/${encodeURIComponent(generationId)}`, {
    method: 'DELETE',
  });
}

// ---------------------------------------------------------------------------
// Hook Library API
// ---------------------------------------------------------------------------

export async function listHooks() {
  return request('/api/hooks');
}

export async function getHook(hookId) {
  return request(`/api/hooks/${encodeURIComponent(hookId)}`);
}

export async function updateHookLabel(hookId, label) {
  return request(`/api/hooks/${encodeURIComponent(hookId)}/label`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ label }),
  });
}

export async function deleteHook(hookId) {
  return request(`/api/hooks/${encodeURIComponent(hookId)}`, { method: 'DELETE' });
}

// ---------------------------------------------------------------------------
// Sound Library API
// ---------------------------------------------------------------------------

export async function listSounds() {
  return request('/api/sounds');
}

export async function getSound(soundId) {
  return request(`/api/sounds/${encodeURIComponent(soundId)}`);
}

export async function updateSoundLabel(soundId, label) {
  return request(`/api/sounds/${encodeURIComponent(soundId)}/label`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ label }),
  });
}

// ---------------------------------------------------------------------------
// Remix API
// ---------------------------------------------------------------------------

export async function startRemix(formData) {
  const resp = await fetch('/api/remix', { method: 'POST', body: formData });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(data.detail || `Remix failed (${resp.status})`);
  return data;
}

// ---------------------------------------------------------------------------
// Model Library API
// ---------------------------------------------------------------------------

export async function listModels() {
  return request('/api/models');
}

export async function uploadModel(formData) {
  const resp = await fetch('/api/models', { method: 'POST', body: formData });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(data.detail || `Model upload failed (${resp.status})`);
  return data;
}

export async function updateModelLabel(modelId, label) {
  return request(`/api/models/${encodeURIComponent(modelId)}/label`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ label }),
  });
}

export async function deleteModel(modelId) {
  return request(`/api/models/${encodeURIComponent(modelId)}`, { method: 'DELETE' });
}

// ---------------------------------------------------------------------------
// Extension Video Library API
// ---------------------------------------------------------------------------

export async function listExtensionVideos() {
  return request('/api/extension-videos');
}

export async function uploadExtensionVideo(formData) {
  const resp = await fetch('/api/extension-videos', { method: 'POST', body: formData });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(data.detail || `Extension video upload failed (${resp.status})`);
  return data;
}

export async function updateExtensionVideoLabel(extId, label) {
  return request(`/api/extension-videos/${encodeURIComponent(extId)}/label`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ label }),
  });
}

export async function deleteExtensionVideo(extId) {
  return request(`/api/extension-videos/${encodeURIComponent(extId)}`, { method: 'DELETE' });
}

// ---------------------------------------------------------------------------
// Avatar Studio API
// ---------------------------------------------------------------------------

/**
 * Start an AI avatar generation. Returns { generationId } and the caller
 * should poll getGeneration(generationId) until status === 'completed'.
 * The generation's output.model is a saved model record that can be reused
 * directly in the existing video generation flow via modelId.
 */
export async function startAvatarGeneration({ selections, promptSummary, label }) {
  return request('/api/avatars', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      selections: selections || {},
      promptSummary: promptSummary || '',
      label: label || '',
    }),
  });
}

export { DEFAULT_SESSION_ID };
