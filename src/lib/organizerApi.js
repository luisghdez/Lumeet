async function request(path, options = {}) {
  const resp = await fetch(path, options);
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw new Error(data.detail || data.message || `Request failed (${resp.status})`);
  }
  return data;
}

export async function scanTikTokAccount({ account, maxItems = 30 }) {
  return request('/api/organizer/tiktok/account-scan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ account, maxItems }),
  });
}

export async function getTikTokScan(scanId) {
  return request(`/api/organizer/tiktok/scans/${encodeURIComponent(scanId)}`);
}

export async function listTikTokScans({ limit = 25 } = {}) {
  return request(`/api/organizer/tiktok/scans?limit=${encodeURIComponent(limit)}`);
}

export async function createBatchFromTikTokScan({ scanId, nicheHint = '' }) {
  return request('/api/organizer/batches/from-tiktok-scan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scanId, nicheHint }),
  });
}

export async function listOrganizerBatches({ limit = 25 } = {}) {
  return request(`/api/organizer/batches?limit=${encodeURIComponent(limit)}`);
}

export async function getOrganizerBatch(batchId) {
  return request(`/api/organizer/batches/${encodeURIComponent(batchId)}`);
}

export async function updateVideoReviewStatus({ videoReferenceId, approvalStatus, notes = '' }) {
  return request(`/api/organizer/video-references/${encodeURIComponent(videoReferenceId)}/review`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ approvalStatus, notes }),
  });
}

export async function analyzeVideoReference(videoReferenceId) {
  return request(`/api/organizer/video-references/${encodeURIComponent(videoReferenceId)}/analyze`, {
    method: 'POST',
  });
}

export async function getVideoReferenceAnalysis(videoReferenceId) {
  return request(`/api/organizer/video-references/${encodeURIComponent(videoReferenceId)}/analysis`);
}

export async function analyzeOrganizerBatch({ batchId, limit = 5, retryFailed = false }) {
  return request(`/api/organizer/batches/${encodeURIComponent(batchId)}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ limit, retryFailed }),
  });
}
