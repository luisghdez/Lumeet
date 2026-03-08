import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Upload, Image, Film, Loader2, CheckCircle2, Circle, XCircle, ArrowLeft, Download, Play, X } from 'lucide-react';
import ScheduleToSocial from './ScheduleToSocial';

const PIPELINE_STEPS = [
  { key: 'scene_detection', label: 'Scene Detection' },
  { key: 'frame_extraction', label: 'Frame Extraction' },
  { key: 'caption_detection', label: 'Caption Detection' },
  { key: 'scene_recreation', label: 'Scene Recreation' },
  { key: 'motion_control', label: 'Motion Control (Kling AI)' },
  { key: 'caption_overlay', label: 'Caption Overlay' },
];

const POLL_INTERVAL = 2000;

// ---------- File Drop Zone ----------

function DropZone({ label, icon: Icon, accept, file, onFileSelect, preview }) {
  const inputRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) onFileSelect(dropped);
  }, [onFileSelect]);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback(() => setIsDragging(false), []);

  return (
    <div
      className={`relative flex flex-col items-center justify-center rounded-2xl border-2 border-dashed transition-all duration-200 cursor-pointer
        ${isDragging ? 'border-purple-500 bg-purple-50/50' : file ? 'border-purple-300 bg-purple-50/30' : 'border-gray-300 hover:border-purple-400 hover:bg-purple-50/20'}
        ${file ? 'p-3' : 'p-8'}`}
      onClick={() => inputRef.current?.click()}
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => {
          const f = e.target.files[0];
          if (f) onFileSelect(f);
        }}
      />

      {file ? (
        <div className="flex items-center gap-3 w-full">
          {preview ? (
            <div className="w-16 h-16 rounded-lg overflow-hidden flex-shrink-0 bg-black/10">
              {preview.type === 'image' ? (
                <img src={preview.url} alt="" className="w-full h-full object-cover" />
              ) : (
                <video src={preview.url} className="w-full h-full object-cover" muted />
              )}
            </div>
          ) : (
            <div className="w-16 h-16 rounded-lg bg-purple-100 flex items-center justify-center flex-shrink-0">
              <Icon size={24} className="text-purple-600" />
            </div>
          )}
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-gray-900 truncate">{file.name}</p>
            <p className="text-xs text-gray-500">{(file.size / (1024 * 1024)).toFixed(1)} MB</p>
          </div>
          <button
            type="button"
            className="p-1.5 rounded-full hover:bg-gray-200 transition-colors"
            onClick={(e) => { e.stopPropagation(); onFileSelect(null); }}
          >
            <X size={16} className="text-gray-500" />
          </button>
        </div>
      ) : (
        <>
          <Icon size={32} className="text-gray-400 mb-3" />
          <p className="text-sm font-semibold text-gray-700">{label}</p>
          <p className="text-xs text-gray-500 mt-1">Click or drag & drop</p>
        </>
      )}
    </div>
  );
}


// ---------- Step Progress Item ----------

function StepItem({ step, index }) {
  const statusIcon = {
    pending: <Circle size={18} className="text-gray-300" />,
    running: <Loader2 size={18} className="text-purple-600 animate-spin" />,
    completed: <CheckCircle2 size={18} className="text-green-500" />,
    failed: <XCircle size={18} className="text-red-500" />,
  };

  return (
    <div
      className="flex items-center gap-3 py-3 px-4 rounded-xl transition-colors duration-200"
      style={{
        opacity: 0,
        animation: `slideDownFade 0.4s ease-out ${index * 100}ms forwards`,
      }}
    >
      {statusIcon[step.status] || statusIcon.pending}
      <div className="flex-1">
        <p className={`text-sm font-medium ${step.status === 'running' ? 'text-purple-700' : step.status === 'completed' ? 'text-gray-700' : 'text-gray-500'}`}>
          {step.label}
        </p>
        {step.message && step.status !== 'pending' && (
          <p className="text-xs text-gray-500 mt-0.5">{step.message}</p>
        )}
      </div>
    </div>
  );
}


// ---------- Main Component ----------

function CreateSection() {
  const [viewState, setViewState] = useState('upload'); // 'upload' | 'processing' | 'result' | 'error'
  const [imageFile, setImageFile] = useState(null);
  const [videoFile, setVideoFile] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [videoPreview, setVideoPreview] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [steps, setSteps] = useState(PIPELINE_STEPS.map(s => ({ ...s, status: 'pending', message: '' })));
  const [error, setError] = useState(null);
  const [resultUrl, setResultUrl] = useState(null);
  const pollRef = useRef(null);

  // Preview URLs
  useEffect(() => {
    if (imageFile) {
      const url = URL.createObjectURL(imageFile);
      setImagePreview({ type: 'image', url });
      return () => URL.revokeObjectURL(url);
    } else {
      setImagePreview(null);
    }
  }, [imageFile]);

  useEffect(() => {
    if (videoFile) {
      const url = URL.createObjectURL(videoFile);
      setVideoPreview({ type: 'video', url });
      return () => URL.revokeObjectURL(url);
    } else {
      setVideoPreview(null);
    }
  }, [videoFile]);

  // Cleanup poll on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  // Poll job status
  const startPolling = useCallback((id) => {
    if (pollRef.current) clearInterval(pollRef.current);

    pollRef.current = setInterval(async () => {
      try {
        const resp = await fetch(`/api/jobs/${id}`);
        if (!resp.ok) return;
        const data = await resp.json();

        setSteps(data.steps);

        if (data.status === 'completed') {
          clearInterval(pollRef.current);
          pollRef.current = null;
          setResultUrl(`/api/jobs/${id}/result`);
          setViewState('result');
        } else if (data.status === 'failed') {
          clearInterval(pollRef.current);
          pollRef.current = null;
          setError(data.error || 'Pipeline failed.');
          setViewState('error');
        }
      } catch (err) {
        console.error('Poll error:', err);
      }
    }, POLL_INTERVAL);
  }, []);

  // Submit job
  const handleSubmit = useCallback(async () => {
    if (!imageFile || !videoFile) return;

    setViewState('processing');
    setSteps(PIPELINE_STEPS.map(s => ({ ...s, status: 'pending', message: '' })));
    setError(null);

    const formData = new FormData();
    formData.append('image', imageFile);
    formData.append('video', videoFile);

    try {
      const resp = await fetch('/api/generate', { method: 'POST', body: formData });
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || `Upload failed (${resp.status})`);
      }
      const { job_id } = await resp.json();
      setJobId(job_id);
      startPolling(job_id);
    } catch (err) {
      setError(err.message);
      setViewState('error');
    }
  }, [imageFile, videoFile, startPolling]);

  // Reset everything
  const handleReset = useCallback(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    setViewState('upload');
    setImageFile(null);
    setVideoFile(null);
    setJobId(null);
    setSteps(PIPELINE_STEPS.map(s => ({ ...s, status: 'pending', message: '' })));
    setError(null);
    setResultUrl(null);
  }, []);

  // ---------- Upload View ----------
  if (viewState === 'upload') {
    return (
      <div className="h-full flex flex-col items-center justify-center px-4 py-8">
        <div className="w-full max-w-2xl flex-1 flex flex-col justify-center">
          <div className="mb-10 text-center">
            <h1 className="text-4xl font-semibold text-gray-900">Create Video</h1>
            <p className="text-gray-600 mt-2">Upload a reference video and model image to generate your video</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
            <DropZone
              label="Model Image"
              icon={Image}
              accept="image/*"
              file={imageFile}
              onFileSelect={setImageFile}
              preview={imagePreview}
            />
            <DropZone
              label="Reference Video"
              icon={Film}
              accept="video/*"
              file={videoFile}
              onFileSelect={setVideoFile}
              preview={videoPreview}
            />
          </div>

          <div className="flex justify-center">
            <button
              onClick={handleSubmit}
              disabled={!imageFile || !videoFile}
              className={`px-8 py-4 font-semibold rounded-2xl transition-all duration-200 shadow-lg hover:shadow-xl
                ${imageFile && videoFile
                  ? 'bg-gradient-to-r from-purple-600 to-purple-500 text-white hover:from-purple-700 hover:to-purple-600'
                  : 'bg-gray-200 text-gray-400 cursor-not-allowed shadow-none'}`}
            >
              Generate Video
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ---------- Processing View ----------
  if (viewState === 'processing') {
    const completedCount = steps.filter(s => s.status === 'completed').length;
    const progressPercent = Math.round((completedCount / steps.length) * 100);

    return (
      <div className="h-full flex flex-col items-center justify-center px-4 py-8">
        <div className="w-full max-w-lg flex-1 flex flex-col justify-center">
          <div className="text-center mb-8">
            <h2 className="text-2xl font-bold text-gray-900 mb-2">Generating Your Video</h2>
            <p className="text-gray-600">This may take a few minutes...</p>
          </div>

          {/* Progress bar */}
          <div className="w-full h-2 bg-gray-200 rounded-full mb-8 overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-purple-500 to-purple-600 rounded-full transition-all duration-500"
              style={{ width: `${progressPercent}%` }}
            />
          </div>

          {/* Steps list */}
          <div className="glass-card border border-white/40 rounded-2xl divide-y divide-white/20">
            {steps.map((step, i) => (
              <StepItem key={step.key} step={step} index={i} />
            ))}
          </div>
        </div>
      </div>
    );
  }

  // ---------- Result View ----------
  if (viewState === 'result') {
    return (
      <div className="h-full flex flex-col items-center justify-center px-4 py-8">
        <div className="w-full max-w-4xl flex-1 flex flex-col justify-center items-center">
          <div className="text-center mb-6">
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-green-100 mb-4">
              <CheckCircle2 size={28} className="text-green-600" />
            </div>
            <h2 className="text-2xl font-bold text-gray-900 mb-1">Video Ready!</h2>
            <p className="text-gray-600">Your generated video is ready to download</p>
          </div>

          {/* Video Player */}
          {resultUrl && (
            <div className="w-full max-w-xs aspect-[9/16] rounded-2xl overflow-hidden bg-black shadow-xl mb-6">
              <video
                src={resultUrl}
                controls
                autoPlay
                className="w-full h-full object-contain"
              />
            </div>
          )}

          <div className="flex gap-4">
            <button
              onClick={handleReset}
              className="px-6 py-3 bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold rounded-xl transition-all duration-200"
            >
              <span className="flex items-center gap-2">
                <ArrowLeft size={18} />
                New Video
              </span>
            </button>
            {resultUrl && (
              <a
                href={resultUrl}
                download="lumeet_output.mp4"
                className="px-6 py-3 bg-gradient-to-r from-purple-600 to-purple-500 text-white font-semibold rounded-xl hover:from-purple-700 hover:to-purple-600 transition-all duration-200"
              >
                <span className="flex items-center gap-2">
                  <Download size={18} />
                  Download
                </span>
              </a>
            )}
          </div>

          <ScheduleToSocial jobId={jobId} resultUrl={resultUrl} />
        </div>
      </div>
    );
  }

  // ---------- Error View ----------
  if (viewState === 'error') {
    return (
      <div className="h-full flex flex-col items-center justify-center px-4 py-8">
        <div className="w-full max-w-lg flex-1 flex flex-col justify-center items-center">
          <div className="text-center mb-6">
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-red-100 mb-4">
              <XCircle size={28} className="text-red-600" />
            </div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">Generation Failed</h2>
            <p className="text-gray-600 text-sm max-w-md">{error}</p>
          </div>

          <button
            onClick={handleReset}
            className="px-6 py-3 bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold rounded-xl transition-all duration-200"
          >
            <span className="flex items-center gap-2">
              <ArrowLeft size={18} />
              Try Again
            </span>
          </button>
        </div>
      </div>
    );
  }

  return null;
}

export default CreateSection;
