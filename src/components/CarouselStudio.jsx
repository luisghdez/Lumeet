import React, { useMemo, useState } from 'react';
import { ChevronDown, Loader2, Settings2, Sparkles, X } from 'lucide-react';
import { startCarouselGeneration } from '../lib/lateApi';

const HOOK_STYLES = [
  {
    id: 'illustrated',
    name: 'Illustrated',
    description: 'Flat editorial cover with bold typography and minimal shapes.',
  },
  {
    id: 'study_desk',
    name: 'Study Desk',
    description: 'Pinterest desk flatlay with warm lifestyle-photo energy.',
  },
  {
    id: 'study_girl',
    name: 'Study Girl',
    description: 'Candid student portrait style with viral text treatment.',
  },
  {
    id: 'pinterest',
    name: 'Pinterest',
    description: 'Organic 9:9 lifestyle-photo hook with rotating study scenes.',
  },
];

const CAROUSEL_STYLES = [
  {
    id: 'illustrated',
    name: 'Illustrated',
    description: 'Current flat-illustration carousel style.',
  },
  {
    id: 'illustrated_2',
    name: 'Illustrated 2',
    description: 'Structured mini-lesson layout with clean hierarchy and icon cues.',
  },
];

function getTimezoneOptions() {
  try {
    if (typeof Intl.supportedValuesOf === 'function') {
      return Intl.supportedValuesOf('timeZone');
    }
  } catch {
    // Ignore unsupported runtimes and use a safe fallback.
  }
  return ['UTC'];
}

export default function CarouselStudio() {
  const [prompt, setPrompt] = useState('');
  const [hookStyle, setHookStyle] = useState('pinterest');
  const [carouselStyle, setCarouselStyle] = useState('illustrated_2');
  const [timezone, setTimezone] = useState(Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [generationId, setGenerationId] = useState('');

  const timezoneOptions = useMemo(getTimezoneOptions, []);
  const canSubmit = prompt.trim().length >= 3 && !isSubmitting;

  async function handleSubmit() {
    if (!canSubmit) return;
    setIsSubmitting(true);
    setError('');
    setGenerationId('');

    try {
      const res = await startCarouselGeneration({
        prompt: prompt.trim(),
        timezone,
        hookStyle,
        carouselStyle,
      });
      setGenerationId(res.generationId || '');
      setPrompt('');
    } catch (err) {
      setError(err?.message || 'Failed to start carousel generation.');
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="h-full flex flex-col items-center justify-center px-4 py-8">
      <div className="w-full max-w-2xl flex-1 flex flex-col justify-center">
        <div className="mb-10 text-center">
          <h1 className="text-4xl font-semibold text-gray-900">Create Carousel</h1>
          <p className="text-gray-600 mt-2">
            Enter one prompt and generate a ready-to-post carousel.
          </p>
        </div>

        <div className="space-y-4">
          <div className="rounded-2xl border border-gray-200 bg-white/70 px-4 py-3.5 shadow-sm">
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
              Prompt
            </label>
            <input
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Example: 7 study methods that help me retain more in less time"
              className="w-full bg-transparent text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none"
            />
          </div>

          <div className="flex items-center justify-center">
            <button
              type="button"
              onClick={() => setShowAdvanced(true)}
              className="inline-flex items-center gap-2 text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors"
            >
              <Settings2 size={16} />
              Advanced settings
              <ChevronDown
                size={16}
                className={`transition-transform duration-200 ${showAdvanced ? 'rotate-180' : ''}`}
              />
            </button>
          </div>

          <div className="flex items-center justify-center gap-3 pt-1">
            <button
              onClick={handleSubmit}
              disabled={!canSubmit}
              className={`inline-flex items-center gap-2 px-8 py-4 rounded-2xl font-semibold transition-all duration-200 shadow-lg hover:shadow-xl ${
                canSubmit
                  ? 'bg-gradient-to-r from-purple-600 to-purple-500 text-white hover:from-purple-700 hover:to-purple-600'
                  : 'bg-gray-200 text-gray-400 cursor-not-allowed shadow-none'
              }`}
            >
              {isSubmitting ? <Loader2 size={18} className="animate-spin" /> : <Sparkles size={18} />}
              {isSubmitting ? 'Starting...' : 'Generate Carousel'}
            </button>
          </div>

          {generationId && (
            <div className="flex justify-center">
              <span className="text-sm text-green-700 bg-green-50 border border-green-200 rounded-lg px-3 py-2">
                Started: {generationId}
              </span>
            </div>
          )}

          {error && (
            <p className="text-sm text-red-600 text-center">{error}</p>
          )}
        </div>
      </div>

      {showAdvanced && (
        <div
          className="fixed inset-0 z-40 bg-black/35 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setShowAdvanced(false)}
        >
          <div
            className="w-full max-w-3xl glass-card border border-white/40 rounded-2xl p-5 md:p-6 space-y-5 max-h-[85vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">Advanced settings</h2>
              <button
                type="button"
                onClick={() => setShowAdvanced(false)}
                className="p-1.5 rounded-lg text-gray-500 hover:text-gray-800 hover:bg-white/70 transition-colors"
              >
                <X size={18} />
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-semibold text-gray-900 mb-2">
                  Hook Style
                </label>
                <div className="grid grid-cols-1 gap-2">
                  {HOOK_STYLES.map((option) => (
                    <button
                      key={option.id}
                      type="button"
                      onClick={() => setHookStyle(option.id)}
                      className={`text-left rounded-xl border px-3 py-2.5 transition ${
                        hookStyle === option.id
                          ? 'border-purple-400 bg-purple-50'
                          : 'border-gray-200 bg-white/80 hover:border-purple-300'
                      }`}
                    >
                      <p className="text-sm font-semibold text-gray-900">{option.name}</p>
                      <p className="text-xs text-gray-600 mt-0.5">{option.description}</p>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-900 mb-2">
                  Carousel Style
                </label>
                <div className="grid grid-cols-1 gap-2">
                  {CAROUSEL_STYLES.map((option) => (
                    <button
                      key={option.id}
                      type="button"
                      onClick={() => setCarouselStyle(option.id)}
                      className={`text-left rounded-xl border px-3 py-2.5 transition ${
                        carouselStyle === option.id
                          ? 'border-purple-400 bg-purple-50'
                          : 'border-gray-200 bg-white/80 hover:border-purple-300'
                      }`}
                    >
                      <p className="text-sm font-semibold text-gray-900">{option.name}</p>
                      <p className="text-xs text-gray-600 mt-0.5">{option.description}</p>
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div>
              <label className="block text-sm font-semibold text-gray-900 mb-2">
                Timezone
              </label>
              <select
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
                className="w-full rounded-xl border border-gray-200 bg-white/80 px-3 py-2.5 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-purple-300 focus:border-purple-300 transition"
              >
                {timezoneOptions.map((tz) => (
                  <option key={tz} value={tz}>
                    {tz}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
