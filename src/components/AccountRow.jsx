import React, { useState } from 'react';
import { Pencil, Check, X } from 'lucide-react';
import { getNickname, setNickname as saveNickname, accountLabel } from '../lib/accountNicknames';

/**
 * AccountRow – renders a single account with checkbox, platform, nickname,
 * and an inline pencil button to edit the nickname.
 *
 * Props:
 *   account          – { _id, platform, profileId }
 *   checked          – boolean
 *   onToggle         – (checked: boolean) => void
 */
export default function AccountRow({ account, checked, onToggle }) {
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState('');

  const nick = getNickname(account._id);
  const label = accountLabel(account);

  const startEdit = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDraft(nick);
    setIsEditing(true);
  };

  const confirmEdit = () => {
    saveNickname(account._id, draft);
    setIsEditing(false);
  };

  const cancelEdit = () => {
    setIsEditing(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') confirmEdit();
    if (e.key === 'Escape') cancelEdit();
  };

  if (isEditing) {
    return (
      <div className="flex items-center gap-2 py-1 text-sm text-gray-800">
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => onToggle(e.target.checked)}
        />
        <span className="font-medium capitalize">{account.platform}</span>
        <input
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Enter nickname..."
          className="flex-1 min-w-0 px-2 py-0.5 rounded-lg border border-purple-300 focus:border-purple-500 outline-none text-sm"
        />
        <button
          type="button"
          onClick={confirmEdit}
          className="p-0.5 rounded hover:bg-green-50 text-green-600"
        >
          <Check size={14} />
        </button>
        <button
          type="button"
          onClick={cancelEdit}
          className="p-0.5 rounded hover:bg-red-50 text-red-400"
        >
          <X size={14} />
        </button>
      </div>
    );
  }

  return (
    <label className="flex items-center gap-2 py-1 text-sm text-gray-800 group">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onToggle(e.target.checked)}
      />
      <span className="font-medium capitalize">{account.platform}</span>
      <span className={nick ? 'text-purple-600 font-medium' : 'text-gray-400 text-xs'}>
        {nick || account._id}
      </span>
      <button
        type="button"
        onClick={startEdit}
        className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-gray-100 text-gray-400 transition-opacity"
        title="Set nickname"
      >
        <Pencil size={12} />
      </button>
    </label>
  );
}
