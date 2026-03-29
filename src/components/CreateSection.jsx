import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Image, Film, Loader2, CheckCircle2, Circle, XCircle, ArrowLeft, Download, X, ToggleLeft, ToggleRight, Sparkles, Plus, Save, User, Trash2 } from 'lucide-react';
import ScheduleToSocial from './ScheduleToSocial';
import CarouselStudio from './CarouselStudio';
import RemixStudio from './RemixStudio';
import {
  startVideoGeneration,
  listModels,
  uploadModel,
  deleteModel,
  listExtensionVideos,
  uploadExtensionVideo,
  deleteExtensionVideo,
} from '../lib/lateApi';

const BASE_PIPELINE_STEPS = [
  { key: 'scene_detection', label: 'Scene Detection' },
  { key: 'frame_extraction', label: 'Frame Extraction' },
  { key: 'caption_detection', label: 'Caption Detection' },
  { key: 'scene_recreation', label: 'Scene Recreation' },
  { key: 'motion_control', label: 'Motion Control (Kling AI)' },
  { key: 'caption_overlay', label: 'Caption Overlay' },
];

const EXTENDED_PIPELINE_STEPS = [
  { key: 'audio_extraction', label: 'Audio Extraction' },
  { key: 'video_concatenation', label: 'Video Concatenation' },
  { key: 'audio_replacement', label: 'Audio Replacement' },
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


// ---------- Extended Toggle ----------

function ExtendedToggle({ extended, onChange }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!extended)}
      className={`flex items-center gap-2.5 px-4 py-2.5 rounded-xl border-2 transition-all duration-200 text-sm font-medium
        ${extended
          ? 'border-purple-400 bg-purple-50 text-purple-700'
          : 'border-gray-200 bg-white text-gray-500 hover:border-gray-300'}`}
    >
      {extended
        ? <ToggleRight size={20} className="text-purple-600" />
        : <ToggleLeft size={20} className="text-gray-400" />}
      <span>Extended Mode</span>
      <span className={`text-xs px-1.5 py-0.5 rounded-full font-semibold
        ${extended ? 'bg-purple-200 text-purple-700' : 'bg-gray-100 text-gray-400'}`}>
        {extended ? 'ON' : 'OFF'}
      </span>
    </button>
  );
}


// ---------- Model Picker ----------

function ModelPicker({ models, selectedModelId, onSelect, onUploadNew, onDelete, loading }) {
  const inputRef = useRef(null);
  const [uploading, setUploading] = useState(false);

  const handleUpload = useCallback(async (file) => {
    if (!file) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append('image', file);
      fd.append('label', file.name.replace(/\.[^.]+$/, ''));
      const result = await uploadModel(fd);
      onUploadNew(result);
    } catch (err) {
      console.error('Model upload failed:', err);
    } finally {
      setUploading(false);
    }
  }, [onUploadNew]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-6">
        <Loader2 size={20} className="text-purple-500 animate-spin" />
        <span className="ml-2 text-sm text-gray-500">Loading models…</span>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap gap-2.5">
      {models.map((m) => {
        const isSelected = m.modelId === selectedModelId;
        return (
          <div key={m.modelId} className="relative group">
            <button
              type="button"
              onClick={() => onSelect(isSelected ? null : m.modelId)}
              className={`relative w-16 h-16 rounded-xl overflow-hidden border-2 transition-all duration-200
                ${isSelected
                  ? 'border-purple-500 ring-2 ring-purple-300 shadow-md'
                  : 'border-gray-200 hover:border-purple-300'}`}
            >
              <img src={m.url} alt={m.label || 'model'} className="w-full h-full object-cover" />
              {isSelected && (
                <div className="absolute top-0.5 right-0.5 bg-purple-500 rounded-full p-0.5">
                  <CheckCircle2 size={10} className="text-white" />
                </div>
              )}
            </button>
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onDelete(m.modelId); }}
              className="absolute -top-1 -right-1 bg-red-500 text-white rounded-full p-0.5 opacity-0 group-hover:opacity-100 transition-opacity"
              title="Delete model"
            >
              <Trash2 size={10} />
            </button>
            <p className="text-[9px] text-center text-gray-500 truncate w-16 mt-0.5">{m.label || m.modelId.slice(0, 6)}</p>
          </div>
        );
      })}

      {/* Upload new model button */}
      <div>
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={uploading}
          className="w-16 h-16 rounded-xl border-2 border-dashed border-gray-300 hover:border-purple-400 flex flex-col items-center justify-center transition-all duration-200"
        >
          {uploading ? <Loader2 size={18} className="text-purple-500 animate-spin" /> : <Plus size={18} className="text-gray-400" />}
        </button>
        <p className="text-[9px] text-center text-gray-400 mt-0.5">{uploading ? 'Saving…' : 'Add new'}</p>
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) handleUpload(f); e.target.value = ''; }}
        />
      </div>
    </div>
  );
}


// ---------- Extension Video Picker ----------

function ExtensionVideoPicker({ videos, selectedId, onSelect, onUploadNew, onDelete, loading }) {
  const inputRef = useRef(null);
  const [uploading, setUploading] = useState(false);

  const handleUpload = useCallback(async (file) => {
    if (!file) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append('video', file);
      fd.append('label', file.name.replace(/\.[^.]+$/, ''));
      const result = await uploadExtensionVideo(fd);
      onUploadNew(result);
    } catch (err) {
      console.error('Extension video upload failed:', err);
    } finally {
      setUploading(false);
    }
  }, [onUploadNew]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-6">
        <Loader2 size={20} className="text-purple-500 animate-spin" />
        <span className="ml-2 text-sm text-gray-500">Loading extension videos…</span>
      </div>
    );
  }

  return (
    <div>
      <div className="flex flex-wrap gap-2.5">
        {videos.map((v) => {
          const isSelected = v.extensionVideoId === selectedId;
          return (
            <div key={v.extensionVideoId} className="relative group">
              <button
                type="button"
                onClick={() => onSelect(isSelected ? null : v.extensionVideoId)}
                className={`relative w-20 h-14 rounded-xl overflow-hidden border-2 transition-all duration-200
                  ${isSelected
                    ? 'border-purple-500 ring-2 ring-purple-300 shadow-md'
                    : 'border-gray-200 hover:border-purple-300'}`}
              >
                <video
                  src={v.url}
                  muted
                  playsInline
                  preload="metadata"
                  className="w-full h-full object-cover"
                  onMouseOver={(e) => e.target.play()}
                  onMouseOut={(e) => { e.target.pause(); e.target.currentTime = 0; }}
                />
                {isSelected && (
                  <div className="absolute top-0.5 right-0.5 bg-purple-500 rounded-full p-0.5">
                    <CheckCircle2 size={10} className="text-white" />
                  </div>
                )}
              </button>
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); onDelete(v.extensionVideoId); }}
                className="absolute -top-1 -right-1 bg-red-500 text-white rounded-full p-0.5 opacity-0 group-hover:opacity-100 transition-opacity"
                title="Delete"
              >
                <Trash2 size={10} />
              </button>
              <p className="text-[9px] text-center text-gray-500 truncate w-20 mt-0.5">{v.label || v.extensionVideoId.slice(0, 6)}</p>
            </div>
          );
        })}

        {/* Upload new */}
        <div>
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            disabled={uploading}
            className="w-20 h-14 rounded-xl border-2 border-dashed border-gray-300 hover:border-purple-400 flex flex-col items-center justify-center transition-all duration-200"
          >
            {uploading ? <Loader2 size={16} className="text-purple-500 animate-spin" /> : <Plus size={16} className="text-gray-400" />}
          </button>
          <p className="text-[9px] text-center text-gray-400 mt-0.5">{uploading ? 'Saving…' : 'Add new'}</p>
          <input
            ref={inputRef}
            type="file"
            accept="video/*"
            className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) handleUpload(f); e.target.value = ''; }}
          />
        </div>
      </div>
    </div>
  );
}


// ---------- Main Component ----------

function CreateSection() {
  const [createTab, setCreateTab] = useState('video'); // 'video' | 'carousel' | 'remix'
  const [viewState, setViewState] = useState('upload'); // 'upload' | 'processing' | 'result' | 'error'
  const [imageFile, setImageFile] = useState(null);
  const [videoFile, setVideoFile] = useState(null);
  const [additionalVideoFile, setAdditionalVideoFile] = useState(null);
  const [extended, setExtended] = useState(false);
  const [imagePreview, setImagePreview] = useState(null);
  const [videoPreview, setVideoPreview] = useState(null);
  const [additionalVideoPreview, setAdditionalVideoPreview] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [steps, setSteps] = useState(BASE_PIPELINE_STEPS.map(s => ({ ...s, status: 'pending', message: '' })));
  const [error, setError] = useState(null);
  const [resultUrl, setResultUrl] = useState(null);
  const [videoGcsUrl, setVideoGcsUrl] = useState(null);
  const pollRef = useRef(null);

  // Saved models state
  const [savedModels, setSavedModels] = useState([]);
  const [loadingModels, setLoadingModels] = useState(true);
  const [selectedModelId, setSelectedModelId] = useState(null);

  // Saved extension videos state
  const [savedExtensionVideos, setSavedExtensionVideos] = useState([]);
  const [loadingExtVideos, setLoadingExtVideos] = useState(true);
  const [selectedExtVideoId, setSelectedExtVideoId] = useState(null);

  // Load saved models and extension videos on mount
  useEffect(() => {
    (async () => {
      try {
        const data = await listModels();
        setSavedModels(data.models || []);
      } catch (err) {
        console.error('Failed to load models:', err);
      } finally {
        setLoadingModels(false);
      }
    })();
    (async () => {
      try {
        const data = await listExtensionVideos();
        setSavedExtensionVideos(data.extensionVideos || []);
      } catch (err) {
        console.error('Failed to load extension videos:', err);
      } finally {
        setLoadingExtVideos(false);
      }
    })();
  }, []);

  // When a saved model is selected, clear the uploaded image file (and vice versa)
  useEffect(() => {
    if (selectedModelId) setImageFile(null);
  }, [selectedModelId]);
  useEffect(() => {
    if (imageFile) setSelectedModelId(null);
  }, [imageFile]);

  // When a saved ext video is selected, clear the uploaded additional video (and vice versa)
  useEffect(() => {
    if (selectedExtVideoId) setAdditionalVideoFile(null);
  }, [selectedExtVideoId]);
  useEffect(() => {
    if (additionalVideoFile) setSelectedExtVideoId(null);
  }, [additionalVideoFile]);

  // Clear additional video when extended is turned off
  useEffect(() => {
    if (!extended) {
      setAdditionalVideoFile(null);
      setSelectedExtVideoId(null);
    }
  }, [extended]);

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

  useEffect(() => {
    if (additionalVideoFile) {
      const url = URL.createObjectURL(additionalVideoFile);
      setAdditionalVideoPreview({ type: 'video', url });
      return () => URL.revokeObjectURL(url);
    } else {
      setAdditionalVideoPreview(null);
    }
  }, [additionalVideoFile]);

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
          // Prefer GCS public URL for playback/scheduling; fall back to local endpoint.
          const gcsUrl = data.video_gcs?.url || null;
          setVideoGcsUrl(gcsUrl);
          setResultUrl(gcsUrl || `/api/jobs/${id}/result`);
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

  const allStepsForMode = useCallback((isExtended) => {
    const base = BASE_PIPELINE_STEPS.map(s => ({ ...s, status: 'pending', message: '' }));
    if (isExtended) {
      return [...base, ...EXTENDED_PIPELINE_STEPS.map(s => ({ ...s, status: 'pending', message: '' }))];
    }
    return base;
  }, []);

  // Derive whether the form is submittable
  const hasModel = imageFile || selectedModelId;
  const hasExtVideo = additionalVideoFile || selectedExtVideoId;
  const canSubmit = hasModel && videoFile && (!extended || hasExtVideo);

  // Submit job — uses the new /api/generations/video endpoint
  const handleSubmit = useCallback(async () => {
    if (!canSubmit) return;

    setViewState('processing');
    setSteps(allStepsForMode(extended));
    setError(null);

    const formData = new FormData();
    if (imageFile) {
      formData.append('image', imageFile);
    } else if (selectedModelId) {
      formData.append('modelId', selectedModelId);
    }
    formData.append('video', videoFile);
    formData.append('extended', extended ? 'true' : 'false');
    if (extended) {
      if (additionalVideoFile) {
        formData.append('additional_video', additionalVideoFile);
      } else if (selectedExtVideoId) {
        formData.append('extensionVideoId', selectedExtVideoId);
      }
    }

    try {
      const data = await startVideoGeneration(formData);
      setJobId(data.jobId);
      startPolling(data.jobId);
    } catch (err) {
      setError(err.message);
      setViewState('error');
    }
  }, [canSubmit, imageFile, selectedModelId, videoFile, additionalVideoFile, selectedExtVideoId, extended, allStepsForMode, startPolling]);

  // Model library handlers
  const handleModelUploaded = useCallback((newModel) => {
    setSavedModels((prev) => [newModel, ...prev]);
    setSelectedModelId(newModel.modelId);
  }, []);

  const handleDeleteModel = useCallback(async (modelId) => {
    try {
      await deleteModel(modelId);
      setSavedModels((prev) => prev.filter((m) => m.modelId !== modelId));
      if (selectedModelId === modelId) setSelectedModelId(null);
    } catch (err) {
      console.error('Failed to delete model:', err);
    }
  }, [selectedModelId]);

  // Extension video library handlers
  const handleExtVideoUploaded = useCallback((newVid) => {
    setSavedExtensionVideos((prev) => [newVid, ...prev]);
    setSelectedExtVideoId(newVid.extensionVideoId);
  }, []);

  const handleDeleteExtVideo = useCallback(async (extId) => {
    try {
      await deleteExtensionVideo(extId);
      setSavedExtensionVideos((prev) => prev.filter((v) => v.extensionVideoId !== extId));
      if (selectedExtVideoId === extId) setSelectedExtVideoId(null);
    } catch (err) {
      console.error('Failed to delete extension video:', err);
    }
  }, [selectedExtVideoId]);

  // Reset everything
  const handleReset = useCallback(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    setViewState('upload');
    setImageFile(null);
    setVideoFile(null);
    setAdditionalVideoFile(null);
    setSelectedModelId(null);
    setSelectedExtVideoId(null);
    setExtended(false);
    setJobId(null);
    setSteps(BASE_PIPELINE_STEPS.map(s => ({ ...s, status: 'pending', message: '' })));
    setError(null);
    setResultUrl(null);
    setVideoGcsUrl(null);
  }, []);

  const renderVideoContent = () => {
    // ---------- Upload View ----------
    if (viewState === 'upload') {
      return (
        <div className="h-full flex flex-col items-center px-4 py-8 overflow-y-auto">
          <div className="w-full max-w-2xl">
            <div className="mb-10 text-center">
              <h1 className="text-4xl font-semibold text-gray-900">Create Video</h1>
              <p className="text-gray-600 mt-2">Upload a reference video and model image to generate your video</p>
            </div>

            {/* Saved Models */}
            <section className="mb-5">
              <h3 className="text-sm font-bold text-gray-700 mb-2 flex items-center gap-2">
                <User size={15} className="text-purple-500" />
                Model Image
                {selectedModelId && <span className="text-[10px] bg-purple-100 text-purple-600 px-1.5 py-0.5 rounded-full font-semibold">SAVED</span>}
              </h3>
              <div className="glass-card border border-white/40 rounded-2xl p-3">
                <ModelPicker
                  models={savedModels}
                  selectedModelId={selectedModelId}
                  onSelect={setSelectedModelId}
                  onUploadNew={handleModelUploaded}
                  onDelete={handleDeleteModel}
                  loading={loadingModels}
                />
                {/* Or upload a one-time image */}
                {!selectedModelId && (
                  <div className="mt-3 pt-3 border-t border-gray-100">
                    <DropZone
                      label="Upload one-time image"
                      icon={Image}
                      accept="image/*"
                      file={imageFile}
                      onFileSelect={setImageFile}
                      preview={imagePreview}
                    />
                  </div>
                )}
              </div>
            </section>

            {/* Reference Video */}
            <section className="mb-5">
              <h3 className="text-sm font-bold text-gray-700 mb-2 flex items-center gap-2">
                <Film size={15} className="text-purple-500" />
                Reference Video
              </h3>
              <DropZone
                label="Reference Video"
                icon={Film}
                accept="video/*"
                file={videoFile}
                onFileSelect={setVideoFile}
                preview={videoPreview}
              />
            </section>

            {/* Extended mode toggle */}
            <div className="flex items-center justify-between mb-4">
              <ExtendedToggle extended={extended} onChange={setExtended} />
              {extended && (
                <p className="text-xs text-purple-600 font-medium">
                  Second section video required
                </p>
              )}
            </div>

            {/* Extension Video: library or upload */}
            {extended && (
              <section className="mb-6 transition-all duration-300">
                <h3 className="text-sm font-bold text-gray-700 mb-2 flex items-center gap-2">
                  <Film size={15} className="text-purple-500" />
                  Extension Video
                  {selectedExtVideoId && <span className="text-[10px] bg-purple-100 text-purple-600 px-1.5 py-0.5 rounded-full font-semibold">SAVED</span>}
                </h3>
                <div className="glass-card border border-white/40 rounded-2xl p-3">
                  <ExtensionVideoPicker
                    videos={savedExtensionVideos}
                    selectedId={selectedExtVideoId}
                    onSelect={setSelectedExtVideoId}
                    onUploadNew={handleExtVideoUploaded}
                    onDelete={handleDeleteExtVideo}
                    loading={loadingExtVideos}
                  />
                  {/* Or upload a one-time video */}
                  {!selectedExtVideoId && (
                    <div className="mt-3 pt-3 border-t border-gray-100">
                      <DropZone
                        label="Upload one-time extension video"
                        icon={Film}
                        accept="video/*"
                        file={additionalVideoFile}
                        onFileSelect={setAdditionalVideoFile}
                        preview={additionalVideoPreview}
                      />
                    </div>
                  )}
                </div>
              </section>
            )}

            {!extended && <div className="mb-6" />}

            <div className="flex justify-center mb-12">
              <button
                onClick={handleSubmit}
                disabled={!canSubmit}
                className={`px-8 py-4 font-semibold rounded-2xl transition-all duration-200 shadow-lg hover:shadow-xl
                  ${canSubmit
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

            <ScheduleToSocial jobId={jobId} resultUrl={resultUrl} videoGcsUrl={videoGcsUrl} />
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
  };

  return (
    <div className="h-full flex flex-col">
      <div className="w-full max-w-4xl mx-auto px-4 pt-2 flex justify-center">
        <div className="inline-flex p-1 rounded-2xl bg-white/70 border border-white/40">
          <button
            type="button"
            onClick={() => setCreateTab('video')}
            className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200 ${
              createTab === 'video'
                ? 'bg-gradient-to-r from-purple-600 to-purple-500 text-white shadow'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            <Film size={16} />
            Video
          </button>
          <button
            type="button"
            onClick={() => setCreateTab('carousel')}
            className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200 ${
              createTab === 'carousel'
                ? 'bg-gradient-to-r from-purple-600 to-purple-500 text-white shadow'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            <Image size={16} />
            Carousel
          </button>
          <button
            type="button"
            onClick={() => setCreateTab('remix')}
            className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200 ${
              createTab === 'remix'
                ? 'bg-gradient-to-r from-purple-600 to-purple-500 text-white shadow'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            <Sparkles size={16} />
            Remix
          </button>
        </div>
      </div>

      <div className="flex-1 min-h-0">
        <div
          key={createTab}
          style={{ animation: 'slideDownFade 0.22s ease-out' }}
          className="h-full"
        >
          {createTab === 'video' ? renderVideoContent() : createTab === 'carousel' ? <CarouselStudio /> : <RemixStudio />}
        </div>
      </div>
    </div>
  );
}

export default CreateSection;
