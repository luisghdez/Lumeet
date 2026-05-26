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

export async function listTikTokDiscoveryNiches() {
  return request('/api/organizer/tiktok/niches');
}

export async function listSuggestedTikTokAccounts({ niche = '' } = {}) {
  const query = niche ? `?niche=${encodeURIComponent(niche)}` : '';
  return request(`/api/organizer/tiktok/suggested-accounts${query}`);
}

export async function createTikTokAccountDiscovery({
  niche,
  limit = 25,
  videosPerSource = 20,
  refresh = false,
}) {
  return request('/api/organizer/tiktok/account-discovery', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ niche, limit, videosPerSource, refresh }),
  });
}

export async function getTikTokAccountDiscovery(discoveryId) {
  return request(`/api/organizer/tiktok/account-discovery/${encodeURIComponent(discoveryId)}`);
}

export async function createTikTokAccountJob({
  account,
  maxItems = 100,
  nicheHint = '',
  analyze = true,
  retryFailed = false,
  maxDurationSec = 30,
  tagConcurrency = 2,
  maxAnalysisFrames = 12,
}) {
  return request('/api/organizer/tiktok/account-jobs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      account,
      maxItems,
      nicheHint,
      analyze,
      retryFailed,
      maxDurationSec,
      tagConcurrency,
      maxAnalysisFrames,
    }),
  });
}

export async function getTikTokAccountJob(jobId) {
  return request(`/api/organizer/tiktok/account-jobs/${encodeURIComponent(jobId)}`);
}

export async function listTikTokAccountJobs({ limit = 25 } = {}) {
  return request(`/api/organizer/tiktok/account-jobs?limit=${encodeURIComponent(limit)}`);
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

export async function listAccountPlannerArchetypes() {
  return request('/api/account-planner/archetypes');
}

export async function createAccountPlan({ archetype = 'studytok', postCount = 10, batchId = '' } = {}) {
  return request('/api/account-planner/plans', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ archetype, postCount, batchId }),
  });
}

export async function createStudyTokSimplePlan({
  postCount = 30,
  relatablePerDay = 3,
  hookDemoPerDay = 1,
  startDate = '',
  dailyTimes = [],
  timezone = 'UTC',
} = {}) {
  return request('/api/account-planner/studytok/simple-plans', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      postCount,
      relatablePerDay,
      hookDemoPerDay,
      startDate,
      dailyTimes,
      timezone,
    }),
  });
}

export async function getAccountPlan(planId) {
  return request(`/api/account-planner/plans/${encodeURIComponent(planId)}`);
}

export async function listAccountPlans({ limit = 25 } = {}) {
  return request(`/api/account-planner/plans?limit=${encodeURIComponent(limit)}`);
}

export async function updateAccountPlan(planId, updates) {
  return request(`/api/account-planner/plans/${encodeURIComponent(planId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  });
}

export async function generateAccountPlanPosts(
  planId,
  { dryRun = false, limit = 0, modelId = '', extensionVideoId = '' } = {},
) {
  return request(`/api/account-planner/plans/${encodeURIComponent(planId)}/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dryRun, limit, modelId, extensionVideoId }),
  });
}

export async function scheduleAccountPlanPosts(
  planId,
  { sessionId = 'local-dev-session', profileId, platforms = [], timezone = 'UTC' } = {},
) {
  return request(`/api/account-planner/plans/${encodeURIComponent(planId)}/schedule`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sessionId, profileId, platforms, timezone }),
  });
}

export async function deleteAccountPlanBulkRun(planId, bulkRunId) {
  return request(
    `/api/account-planner/plans/${encodeURIComponent(planId)}/bulk-runs/${encodeURIComponent(bulkRunId)}`,
    { method: 'DELETE' },
  );
}

export async function updateAccountPlanPost({ planId, slot, updates }) {
  return request(`/api/account-planner/plans/${encodeURIComponent(planId)}/posts/${encodeURIComponent(slot)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  });
}

export async function swapAccountPlanPost({ planId, slot }) {
  return request(`/api/account-planner/plans/${encodeURIComponent(planId)}/posts/${encodeURIComponent(slot)}/swap`, {
    method: 'POST',
  });
}

export async function getAccountPlanPostOverlay({ planId, slot }) {
  return request(`/api/account-planner/plans/${encodeURIComponent(planId)}/posts/${encodeURIComponent(slot)}/overlay`);
}

export async function renderAccountPlanPostOverlay({ planId, slot, overlay }) {
  return request(`/api/account-planner/plans/${encodeURIComponent(planId)}/posts/${encodeURIComponent(slot)}/overlay/render`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(overlay),
  });
}

export async function revertAccountPlanPostOverlay({ planId, slot }) {
  return request(`/api/account-planner/plans/${encodeURIComponent(planId)}/posts/${encodeURIComponent(slot)}/overlay/revert`, {
    method: 'POST',
  });
}
