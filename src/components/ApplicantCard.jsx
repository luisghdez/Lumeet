import React from 'react';
import { MapPin, Clock } from 'lucide-react';

function ApplicantCard({ applicant }) {
  const { name, avatar, university, location, bio, tags, lastActive } = applicant;

  return (
    <div className="relative glass-card rounded-3xl p-6 border border-white/20">
      {/* Multi-layer glassy gradient overlays */}
      <div className="absolute inset-0 rounded-3xl bg-gradient-to-t from-white/20 to-transparent pointer-events-none" />

      <div className="relative">
        {/* Header with Avatar and Name */}
        <div className="flex items-start gap-4 mb-5">
          <div className="relative">
            <div className="absolute inset-0 rounded-3xl bg-gradient-to-br from-purple-400 to-pink-400 blur-lg opacity-40" />
            <img
              src={avatar}
              alt={name}
              className="relative w-20 h-20 rounded-3xl object-cover ring-2 ring-white/60"
            />
            <div className="absolute -bottom-1 -right-1 w-5 h-5 bg-gradient-to-br from-green-400 to-emerald-400 rounded-full border-3 border-white" />
          </div>
          <div className="flex-1 min-w-0 pt-1">
            <h3 className="text-xl font-bold text-gray-900 truncate">{name}</h3>
            <div className="flex items-center gap-1.5 text-sm text-gray-700 mt-1.5">
              <MapPin size={15} className="flex-shrink-0 text-purple-500" strokeWidth={2.5} />
              <span className="truncate font-medium">{location}</span>
            </div>
          </div>
        </div>

        {/* University Badge */}
        <div className="mb-4">
          <div className="inline-flex items-center px-4 py-2 rounded-2xl glass border border-white/50">
            <p className="text-sm font-semibold text-gray-700">
              {university}
            </p>
          </div>
        </div>

        {/* Bio */}
        <p className="text-sm text-gray-800 mb-5 line-clamp-2 leading-relaxed font-medium">{bio}</p>

        {/* Tags */}
        <div className="flex flex-wrap gap-2 mb-5">
          {tags.slice(0, 2).map((tag, index) => (
            <span
              key={index}
              className="px-3.5 py-1.5 text-xs font-semibold glass border border-white/50 text-gray-700 rounded-full"
            >
              {tag}
            </span>
          ))}
        </div>

        {/* Footer with Last Active and Hire Button */}
        <div className="flex items-center justify-between pt-5 border-t border-white/50">
          <div className="flex items-center gap-2 text-xs text-gray-600 font-medium glass px-3 py-1.5 rounded-xl border border-white/40">
            <Clock size={14} className="text-purple-500" />
            <span>Active {lastActive}</span>
          </div>
          <button className="px-6 py-2.5 rounded-2xl text-sm font-bold glass border border-purple-200/50 text-purple-700 hover:bg-purple-50/50 transition-all duration-200 hover:border-purple-300/70">
            Hire
          </button>
        </div>
      </div>
    </div>
  );
}

export default ApplicantCard;

