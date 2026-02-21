import React, { useState, useEffect } from 'react';
import { Video, Play, Loader2 } from 'lucide-react';

// Individual Variant Row Component with its own state
function VariantRow({ column, processingTime, isLoadingView = false }) {
  const [status, setStatus] = useState('processing');

  useEffect(() => {
    const timer = setTimeout(() => {
      setStatus('ready');
    }, processingTime);

    return () => clearTimeout(timer);
  }, [processingTime]);

  const isReady = status === 'ready';

  return (
    <div
      className={`glass-card border border-white/40 rounded-2xl p-3 opacity-0 transform -translate-y-4 ${!isLoadingView ? 'hover:shadow-lg' : ''} transition-all duration-200`}
      style={{
        animation: `slideDownFade 0.6s ease-out ${column.delay}ms forwards`
      }}
    >
      <div className="flex items-center space-x-3">
        {/* Video Thumbnail */}
        <div className="relative w-12 h-20 rounded-lg overflow-hidden group cursor-pointer flex-shrink-0">
          <img
            src={column.thumbnail}
            alt={column.name}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-200"
          />
          <div className="absolute inset-0 bg-black/20 group-hover:bg-black/10 transition-colors" />
          
          {!isLoadingView && (
            <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
              <div className="bg-white/90 rounded-full p-1.5">
                <Play size={14} className="text-purple-600" />
              </div>
            </div>
          )}
          
          {isReady && isLoadingView && (
            <div className="absolute inset-0 bg-green-500/20 flex items-center justify-center">
              <div className="bg-green-500 rounded-full p-1">
                <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                </svg>
              </div>
            </div>
          )}
          
          {isReady && !isLoadingView && (
            <div className="absolute top-2 right-2 bg-green-500 rounded-full p-1">
              <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
              </svg>
            </div>
          )}
        </div>
        
        {/* Content */}
        <div className="flex-1 flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-gray-900 text-sm">{column.name}</h3>
            <p className="text-xs text-gray-600">
              {isReady ? 'Ready for download' : isLoadingView ? 'Processing video variant...' : 'Processing...'}
            </p>
          </div>
          
          {/* Status Indicator or Action Button */}
          <div className="flex items-center space-x-2">
            {isReady ? (
              isLoadingView ? (
                <div className="flex items-center space-x-1">
                  <div className="w-1.5 h-1.5 bg-green-500 rounded-full"></div>
                  <span className="text-xs text-green-600 font-medium">Ready</span>
                </div>
              ) : (
                <button className="px-4 py-2 bg-gradient-to-r from-purple-600 to-purple-500 text-white font-semibold rounded-lg hover:from-purple-700 hover:to-purple-600 transition-all duration-200 text-sm">
                  Download
                </button>
              )
            ) : (
              <div className="flex items-center space-x-1">
                <Loader2 size={16} className="text-purple-600 animate-spin" />
                <span className="text-xs text-gray-500">Processing...</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function VariantLab() {
  const [selectedTemplate, setSelectedTemplate] = useState('template-1');
  const [quantity, setQuantity] = useState(1);
  const [changeType, setChangeType] = useState('script');
  const [viewState, setViewState] = useState('form'); // 'form', 'loading', 'results'

  // Mock video templates with 9:16 aspect ratio placeholders
  const videoTemplates = [
    { id: 'template-1', name: 'Tech Tutorial', thumbnail: 'https://picsum.photos/180/320?random=1' },
    { id: 'template-2', name: 'Lifestyle Vlog', thumbnail: 'https://picsum.photos/180/320?random=2' },
    { id: 'template-3', name: 'Educational', thumbnail: 'https://picsum.photos/180/320?random=3' },
    { id: 'template-4', name: 'Product Review', thumbnail: 'https://picsum.photos/180/320?random=4' },
    { id: 'template-5', name: 'Fashion & Beauty', thumbnail: 'https://picsum.photos/180/320?random=5' },
    { id: 'template-6', name: 'Cooking Show', thumbnail: 'https://picsum.photos/180/320?random=6' },
    { id: 'template-7', name: 'Fitness Guide', thumbnail: 'https://picsum.photos/180/320?random=7' },
    { id: 'template-8', name: 'Travel Diary', thumbnail: 'https://picsum.photos/180/320?random=8' },
    { id: 'template-9', name: 'Gaming Content', thumbnail: 'https://picsum.photos/180/320?random=9' },
  ];

  const changeTypes = [
    { id: 'script', name: 'Script', description: 'Modify the video script and dialogue' },
    { id: 'scene', name: 'Scene', description: 'Change the visual scenes and settings' },
    { id: 'voice', name: 'Voice', description: 'Alter the voice characteristics' },
  ];

  const handleSubmit = () => {
    console.log('Variant Lab submitted:', {
      template: selectedTemplate,
      quantity,
      changeType
    });
    
    setViewState('loading');
  };

  const handleReset = () => {
    setViewState('form');
  };

  const selectedChangeTypeData = changeTypes.find(ct => ct.id === changeType);

  // Generate loading columns based on quantity
  const generateLoadingColumns = () => {
    const columns = [];
    for (let i = 0; i < quantity; i++) {
      columns.push({
        id: i + 1,
        name: `Variant ${i + 1}`,
        thumbnail: `https://picsum.photos/180/320?random=${10 + i}`,
        delay: i * 300, // Animation delay for staggered entrance
        processingTime: 2000 + (i * 500) // Staggered completion times
      });
    }
    return columns;
  };

  const loadingColumns = generateLoadingColumns();

  // Form View Component
  const FormView = () => (
    <div className="w-full max-w-4xl flex-1 flex flex-col justify-center">
      {/* Header with Greeting */}
      <div className="mb-12 text-center">
        <div className="flex items-center justify-center gap-4">
          <Video size={28} className="text-purple-600" />
          <h1 className="text-4xl font-semibold text-gray-900">Variant Lab</h1>
        </div>
        <p className="text-gray-600 mt-2">Create video variants with different templates and settings</p>
      </div>
      
      {/* Video Template Selection */}
      <div className="mb-8">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Select Video Template</h3>
        <div className="flex gap-4 overflow-x-auto pb-4 scrollbar-hide">
          {videoTemplates.map((template) => (
            <button
              key={template.id}
              onClick={() => setSelectedTemplate(template.id)}
              className={`relative group rounded-xl overflow-hidden border-2 transition-all duration-200 flex-shrink-0 ${
                selectedTemplate === template.id
                  ? 'border-purple-500 ring-2 ring-purple-200'
                  : 'border-gray-200 hover:border-purple-300'
              }`}
              style={{ width: '120px' }}
            >
              <div className="aspect-[9/16] w-full">
                <img
                  src={template.thumbnail}
                  alt={template.name}
                  className="w-full h-full object-cover"
                />
                <div className="absolute inset-0 bg-black/20 group-hover:bg-black/10 transition-colors" />
                <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                  <div className="bg-white/90 rounded-full p-2">
                    <Play size={16} className="text-purple-600" />
                  </div>
                </div>
              </div>
              <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent p-2">
                <p className="text-white text-xs font-medium truncate">{template.name}</p>
              </div>
              {selectedTemplate === template.id && (
                <div className="absolute top-2 right-2 bg-purple-500 rounded-full p-1">
                  <div className="w-2 h-2 bg-white rounded-full" />
                </div>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Quantity and Change Type Selection */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        {/* Quantity Selection */}
        <div>
          <label className="block text-sm font-semibold text-gray-900 mb-3">Quantity</label>
          <div className="glass-card border border-white/40 rounded-2xl p-4 h-20 flex items-center">
            <div className="flex items-center justify-between w-full">
              <button
                onClick={() => setQuantity(Math.max(1, quantity - 1))}
                className="w-8 h-8 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center text-gray-600 font-semibold"
              >
                -
              </button>
              <span className="text-2xl font-bold text-gray-900 px-4">{quantity}</span>
              <button
                onClick={() => setQuantity(quantity + 1)}
                className="w-8 h-8 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center text-gray-600 font-semibold"
              >
                +
              </button>
            </div>
          </div>
        </div>

        {/* Change Type Selection */}
        <div>
          <label className="block text-sm font-semibold text-gray-900 mb-3">What to Change</label>
          <div className="glass-card border border-white/40 rounded-2xl p-4 h-20 flex items-center">
            <div className="flex items-center justify-between w-full">
              <button
                onClick={() => {
                  const currentIndex = changeTypes.findIndex(ct => ct.id === changeType);
                  const prevIndex = currentIndex > 0 ? currentIndex - 1 : changeTypes.length - 1;
                  setChangeType(changeTypes[prevIndex].id);
                }}
                className="w-8 h-8 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center text-gray-600 font-semibold"
              >
                ‹
              </button>
              <div className="text-center px-4">
                <div className="font-bold text-gray-900 text-lg">{selectedChangeTypeData.name}</div>
                <div className="text-xs text-gray-600 mt-1">{selectedChangeTypeData.description}</div>
              </div>
              <button
                onClick={() => {
                  const currentIndex = changeTypes.findIndex(ct => ct.id === changeType);
                  const nextIndex = currentIndex < changeTypes.length - 1 ? currentIndex + 1 : 0;
                  setChangeType(changeTypes[nextIndex].id);
                }}
                className="w-8 h-8 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center text-gray-600 font-semibold"
              >
                ›
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Generate Button */}
      <div className="flex justify-center">
        <button
          onClick={handleSubmit}
          className="px-8 py-4 bg-gradient-to-r from-purple-600 to-purple-500 text-white font-semibold rounded-2xl hover:from-purple-700 hover:to-purple-600 transition-all duration-200 shadow-lg hover:shadow-xl"
        >
          Generate Variants
        </button>
      </div>
    </div>
  );

  // Loading View Component
  const LoadingView = () => (
    <div className="w-full max-w-4xl h-full flex flex-col py-8">
      <div className="text-center mb-8 flex-shrink-0">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Generating Your Variants</h2>
        <p className="text-gray-600">Creating {quantity} unique video variant{quantity > 1 ? 's' : ''}...</p>
      </div>
      
      <div className="flex-1 overflow-y-auto">
        <div className="space-y-2 pb-4">
          {loadingColumns.map((column) => (
            <VariantRow
              key={column.id}
              column={column}
              processingTime={column.processingTime}
              isLoadingView={true}
            />
          ))}
        </div>
      </div>
    </div>
  );

  // Results View Component
  const ResultsView = () => (
    <div className="w-full max-w-4xl h-full flex flex-col py-8">
      <div className="text-center mb-8 flex-shrink-0">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Your Variants Are Ready!</h2>
        <p className="text-gray-600">Here are your {quantity} generated video variant{quantity > 1 ? 's' : ''}</p>
      </div>
      
      <div className="flex-1 overflow-y-auto">
        <div className="space-y-2 pb-4">
          {loadingColumns.map((column) => (
            <VariantRow
              key={column.id}
              column={column}
              processingTime={column.processingTime}
              isLoadingView={false}
            />
          ))}
        </div>
      </div>

      {/* Back Button */}
      <div className="flex justify-center pt-4 flex-shrink-0">
        <button
          onClick={handleReset}
          className="px-6 py-3 bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold rounded-xl transition-all duration-200"
        >
          Create New Variants
        </button>
      </div>
    </div>
  );

  return (
    <div className="h-full flex flex-col items-center justify-center px-4 py-8">
      {viewState === 'form' && <FormView />}
      {viewState === 'loading' && <LoadingView />}
      {viewState === 'results' && <ResultsView />}
    </div>
  );
}

export default VariantLab;
