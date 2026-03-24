const STORAGE_KEY = 'lumeet_account_nicknames';

function _read() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function _write(map) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(map));
}

export function getNicknames() {
  return _read();
}

export function getNickname(accountId) {
  return _read()[accountId] || '';
}

export function setNickname(accountId, nickname) {
  const map = _read();
  if (nickname && nickname.trim()) {
    map[accountId] = nickname.trim();
  } else {
    delete map[accountId];
  }
  _write(map);
}

export function removeNickname(accountId) {
  const map = _read();
  delete map[accountId];
  _write(map);
}

/**
 * Return a display label for an account: nickname if set, otherwise
 * the platform name + a truncated version of the ID.
 */
export function accountLabel(account) {
  const nick = getNickname(account._id);
  if (nick) return nick;
  const shortId = account._id.length > 10
    ? `${account._id.slice(0, 4)}...${account._id.slice(-4)}`
    : account._id;
  return `${account.platform} (${shortId})`;
}
