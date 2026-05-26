import React from 'react';
import { accountDisplayName, accountSubtitle } from '../lib/lateAccounts';

/**
 * AccountRow – renders a single account with checkbox, platform, and handle.
 */
export default function AccountRow({ account, checked, onToggle }) {
  const title = accountDisplayName(account);
  const subtitle = accountSubtitle(account);

  return (
    <label className="flex items-center gap-2 py-1 text-sm text-gray-800">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onToggle(event.target.checked)}
      />
      <span className="font-medium capitalize">{account.platform}</span>
      <span className="min-w-0 flex-1 truncate">
        <span className="font-medium text-gray-900">{title}</span>
        {subtitle && subtitle !== title ? (
          <span className="ml-1.5 text-xs text-gray-400">{subtitle}</span>
        ) : null}
      </span>
    </label>
  );
}
