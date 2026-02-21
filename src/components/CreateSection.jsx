import React, { useState } from 'react';
import { Send, ChevronDown, Sparkles } from 'lucide-react';

function CreateSection() {
  const [prompt, setPrompt] = useState('');
  const [selectedModel, setSelectedModel] = useState('emma-thompson');
  const [isModelDropdownOpen, setIsModelDropdownOpen] = useState(false);

  const models = [
    { id: 'emma-thompson', name: 'Emma Thompson', description: 'Mental health & wellness creator', avatar: 'https://i.pravatar.cc/150?img=1' },
    { id: 'marcus-chen', name: 'Marcus Chen', description: 'Tech & coding tutorials', avatar: 'https://i.pravatar.cc/150?img=13' },
    { id: 'sophia-rodriguez', name: 'Sophia Rodriguez', description: 'Environmental & sustainability', avatar: 'https://i.pravatar.cc/150?img=5' },
    { id: 'james-wilson', name: 'James Wilson', description: 'Business & finance content', avatar: 'https://i.pravatar.cc/150?img=12' },
    { id: 'aria-patel', name: 'Aria Patel', description: 'Fashion & lifestyle influencer', avatar: 'https://i.pravatar.cc/150?img=9' },
    { id: 'noah-kim', name: 'Noah Kim', description: 'Film & creative content', avatar: 'https://i.pravatar.cc/150?img=14' },
  ];

  const handleSubmit = (e) => {
    e.preventDefault();
    if (prompt.trim()) {
      console.log('Prompt submitted:', prompt, 'Model:', selectedModel);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const selectedModelData = models.find(m => m.id === selectedModel);

  return (
    <div className="h-full flex flex-col items-center justify-center px-4 py-8">
      <div className="w-full max-w-3xl flex-1 flex flex-col justify-center">
        
        {/* Header with Greeting */}
        <div className="mb-12 text-center">
          <div className="flex items-center justify-center gap-4">
            <Sparkles size={28} className="text-purple-600" />
            <h1 className="text-4xl font-semibold text-gray-900">Good afternoon, Luis</h1>
          </div>
        </div>
        
        {/* Person Model Selector - Positioned at top */}
        <div className="mb-8">
          <div className="relative inline-block">
            <button
              type="button"
              onClick={() => setIsModelDropdownOpen(!isModelDropdownOpen)}
              className="flex items-center gap-2 px-4 py-2 glass border border-white/40 rounded-xl text-sm font-medium text-gray-800"
            >
              <span className="text-gray-600">Creator:</span>
              <span className="font-semibold">{selectedModelData.name}</span>
              <ChevronDown size={16} className="text-gray-500" />
            </button>

            {/* Dropdown Menu */}
            {isModelDropdownOpen && (
              <div className="absolute top-full left-0 mt-2 w-80 glass-card border border-white/40 rounded-2xl overflow-hidden z-50">
                {models.map((model) => (
                  <button
                    key={model.id}
                    onClick={() => {
                      setSelectedModel(model.id);
                      setIsModelDropdownOpen(false);
                    }}
                    className={`w-full text-left px-4 py-3 border-b border-white/30 last:border-b-0 flex items-center gap-3 ${
                      selectedModel === model.id ? 'bg-purple-100/50' : ''
                    }`}
                  >
                    <img
                      src={model.avatar}
                      alt={model.name}
                      className="w-8 h-8 rounded-full object-cover ring-1 ring-white/40"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="font-semibold text-gray-900 text-sm">{model.name}</div>
                      <div className="text-xs text-gray-600 mt-0.5">{model.description}</div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Main Input Container - Minimal ChatGPT Style */}
        <div className="w-full">
          <form onSubmit={handleSubmit} className="relative">
            <div className="glass-card border border-white/40 rounded-3xl p-2">
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Describe what you want this creator to do..."
                rows={1}
                className="w-full px-5 py-4 bg-transparent border-none text-gray-900 placeholder-gray-500 focus:outline-none resize-none text-base leading-relaxed"
                style={{ 
                  minHeight: '56px',
                  maxHeight: '200px',
                  height: 'auto'
                }}
                onInput={(e) => {
                  e.target.style.height = 'auto';
                  e.target.style.height = e.target.scrollHeight + 'px';
                }}
              />
              
              {/* Send Button - Inside the input */}
              <div className="flex justify-end px-3 pb-2">
                <button
                  type="submit"
                  disabled={!prompt.trim()}
                  className={`p-2 rounded-xl ${
                    prompt.trim() 
                      ? 'bg-gradient-to-r from-purple-600 to-purple-500 text-white' 
                      : 'bg-gray-200 text-gray-400'
                  }`}
                >
                  <Send size={18} />
                </button>
              </div>
            </div>
          </form>

          {/* Helper Text */}
          <div className="mt-4 text-center">
            <p className="text-xs text-gray-500">
              Press Enter to send, Shift + Enter for new line
            </p>
          </div>
        </div>

      </div>
    </div>
  );
}

export default CreateSection;

