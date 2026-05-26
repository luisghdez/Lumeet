function accountId(accountOrId) {
  if (typeof accountOrId === 'string') return accountOrId.trim();
  return String(accountOrId?._id ?? accountOrId?.id ?? '').trim();
}

function profileIdFromAccount(raw) {
  if (typeof raw?.profileId === 'string') return raw.profileId.trim();
  if (raw?.profileId && typeof raw.profileId === 'object') {
    return String(raw.profileId._id ?? '').trim();
  }
  if (typeof raw?.profile?._id === 'string') return raw.profile._id.trim();
  return '';
}

export function formatUsername(username) {
  const cleaned = String(username || '').trim().replace(/^@+/, '');
  return cleaned ? `@${cleaned}` : '';
}

export function normalizeLateAccount(raw) {
  const profileData = raw?.metadata?.profileData || {};
  const id = accountId(raw);
  const platform = String(raw?.platform ?? raw?.provider ?? '').trim();
  const username = String(raw?.username ?? profileData?.username ?? '').trim().replace(/^@+/, '');
  const displayName = String(raw?.displayName ?? profileData?.displayName ?? '').trim();

  return {
    _id: id,
    id,
    platform,
    username,
    displayName,
    profileUrl: String(raw?.profileUrl ?? profileData?.profileUrl ?? '').trim(),
    profileId: profileIdFromAccount(raw),
  };
}

export function normalizeLateAccounts(rawAccounts = []) {
  return (rawAccounts || [])
    .map(normalizeLateAccount)
    .filter((account) => account._id && account.platform);
}

export function accountDisplayName(account) {
  const displayName = String(account?.displayName ?? '').trim();
  if (displayName) return displayName;

  const handle = formatUsername(account?.username);
  if (handle) return handle;

  const id = accountId(account);
  const platform = account?.platform || 'account';
  if (!id) return platform;
  const shortId = id.length > 10 ? `${id.slice(0, 4)}...${id.slice(-4)}` : id;
  return `${platform} (${shortId})`;
}

export function accountSubtitle(account) {
  const platformLabel = (account?.platform || 'account').replaceAll('_', ' ');
  const handle = formatUsername(account?.username);
  const displayName = String(account?.displayName ?? '').trim();

  if (displayName && handle) return `${platformLabel} · ${handle}`;
  if (platformLabel) return platformLabel;

  const id = accountId(account);
  if (id.length > 10) return `${id.slice(0, 4)}…${id.slice(-4)}`;
  return id;
}

/** @deprecated use accountDisplayName */
export function accountLabel(account) {
  return accountDisplayName(account);
}
