import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Image, Film, Loader2, CheckCircle2, XCircle, ArrowLeft, X, ToggleLeft, ToggleRight, Sparkles, Plus, Save, User, Trash2, UserCircle2 } from 'lucide-react';
import CarouselStudio from './CarouselStudio';
import RemixStudio from './RemixStudio';
import AvatarStudio from './AvatarStudio';
import {
  startVideoGeneration,
  uploadModel,
  deleteModel,
  uploadExtensionVideo,
  deleteExtensionVideo,
} from '../lib/lateApi';
import { useModels, useExtensionVideos } from '../lib/mediaLibrary';

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
      className={`relative flex flex-col items-center justify-center rounded-2xl border-2 transition-all duration-200 cursor-pointer shadow-[inset_0_1px_0_0_rgba(255,255,255,0.35)]
        ${
          isDragging
            ? 'border-dashed border-nimbus-600/45 bg-white/28'
            : file
              ? 'border-solid border-nimbus-500/40 bg-white/25'
              : 'border-dashed border-nimbus-400/45 bg-white/15 hover:border-nimbus-500/50 hover:bg-white/22'
        }
        ${file ? 'p-3' : 'p-5 md:p-8'}`}
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
          <p className="text-xs text-gray-500 mt-1">Tap to upload</p>
        </>
      )}
    </div>
  );
}


// ---------- Extended Toggle ----------

function ExtendedToggle({ extended, onChange }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!extended)}
      aria-pressed={extended}
      className={`flex items-center justify-between gap-3 w-full sm:w-auto px-4 py-2.5 rounded-xl border-2 transition-all duration-300 text-sm font-medium shadow-[inset_0_1px_0_0_rgba(255,255,255,0.35)]
        ${extended
          ? 'border-nimbus-500/45 bg-white/35 text-nimbus-900'
          : 'border-nimbus-400/45 bg-white/40 text-nimbus-700 hover:border-nimbus-500/45'}`}
    >
      <span className="flex items-center gap-2.5">
        {extended
          ? <ToggleRight size={20} className="text-purple-600 transition-transform duration-300" />
          : <ToggleLeft size={20} className="text-gray-400 transition-transform duration-300" />}
        <span>Extended Mode</span>
      </span>

      <span className="flex items-center gap-2">
        <span className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-300 ${extended ? 'bg-purple-500' : 'bg-gray-300'}`}>
          <span
            className={`inline-block h-5 w-5 transform rounded-full bg-white transition-transform duration-300 ${extended ? 'translate-x-5' : 'translate-x-0.5'}`}
          />
        </span>
        <span className={`text-xs px-1.5 py-0.5 rounded-full font-semibold transition-all duration-300
        ${extended ? 'bg-purple-200 text-purple-700' : 'bg-gray-100 text-gray-400'}`}>
          {extended ? 'ON' : 'OFF'}
        </span>
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
              className={`relative w-16 h-16 rounded-xl overflow-hidden border-2 transition-all duration-200 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.25)]
                ${isSelected
                  ? 'border-nimbus-600 ring-2 ring-white/70 shadow-md'
                  : 'border-nimbus-400/40 hover:border-nimbus-500/48'}`}
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
          className="w-16 h-16 rounded-xl border-2 border-dashed border-nimbus-400/45 bg-white/10 hover:border-nimbus-500/50 hover:bg-white/18 flex flex-col items-center justify-center transition-all duration-200 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.35)]"
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
                className={`relative w-20 h-14 rounded-xl overflow-hidden border-2 transition-all duration-200 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.25)]
                  ${isSelected
                    ? 'border-nimbus-600 ring-2 ring-white/70 shadow-md'
                    : 'border-nimbus-400/40 hover:border-nimbus-500/48'}`}
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
            className="w-20 h-14 rounded-xl border-2 border-dashed border-nimbus-400/45 bg-white/10 hover:border-nimbus-500/50 hover:bg-white/18 flex flex-col items-center justify-center transition-all duration-200 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.35)]"
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

function CreateSection({ onVideoGenerationStarted }) {
  const [createTab, setCreateTab] = useState('video'); // 'video' | 'carousel' | 'remix' | 'avatar'
  const [viewState, setViewState] = useState('upload'); // 'upload' | 'error'
  const [videoFile, setVideoFile] = useState(null);
  const [additionalVideoFile, setAdditionalVideoFile] = useState(null);
  const [extended, setExtended] = useState(false);
  const [videoPreview, setVideoPreview] = useState(null);
  const [additionalVideoPreview, setAdditionalVideoPreview] = useState(null);
  const [error, setError] = useState(null);
  const [isSubmittingVideo, setIsSubmittingVideo] = useState(false);
  const [queueState, setQueueState] = useState('idle'); // 'idle' | 'confirming' | 'queued'
  const uploadScrollRef = useRef(null);
  const previousExtendedRef = useRef(extended);

  // Saved models — shared cache (loaded once at app boot, kept in memory)
  const { models: savedModels, loading: loadingModels, setModels: setSavedModels } = useModels();
  const [selectedModelId, setSelectedModelId] = useState(null);

  // Saved extension videos — shared cache
  const { extensionVideos: savedExtensionVideos, loading: loadingExtVideos, setExtensionVideos: setSavedExtensionVideos } = useExtensionVideos();
  const [selectedExtVideoId, setSelectedExtVideoId] = useState(null);

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

  // Keep auto-scroll scoped to the upload container to avoid page-level jumps.
  useEffect(() => {
    const wasExtended = previousExtendedRef.current;
    previousExtendedRef.current = extended;

    if (!wasExtended && extended && uploadScrollRef.current) {
      const timeout = setTimeout(() => {
        if (uploadScrollRef.current) {
          uploadScrollRef.current.scrollTo({
            top: uploadScrollRef.current.scrollHeight,
            behavior: 'smooth',
          });
        }
      }, 260);
      return () => clearTimeout(timeout);
    }

    return undefined;
  }, [extended]);

  // Preview URLs
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

  // Derive whether the form is submittable
  const hasModel = selectedModelId;
  const hasExtVideo = additionalVideoFile || selectedExtVideoId;
  const canSubmit = hasModel && videoFile && (!extended || hasExtVideo);

  // Submit job — uses the new /api/generations/video endpoint
  const handleSubmit = useCallback(async () => {
    if (!canSubmit || isSubmittingVideo) return;

    setError(null);
    setQueueState('confirming');
    setIsSubmittingVideo(true);

    const formData = new FormData();
    if (selectedModelId) {
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
      await startVideoGeneration(formData);
      onVideoGenerationStarted?.();
      setQueueState('queued');
    } catch (err) {
      setQueueState('idle');
      setError(err.message);
      setViewState('error');
    } finally {
      setIsSubmittingVideo(false);
    }
  }, [canSubmit, isSubmittingVideo, selectedModelId, videoFile, additionalVideoFile, selectedExtVideoId, extended, onVideoGenerationStarted]);

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
    setViewState('upload');
    setVideoFile(null);
    setAdditionalVideoFile(null);
    setSelectedModelId(null);
    setSelectedExtVideoId(null);
    setExtended(false);
    setError(null);
    setQueueState('idle');
  }, []);

  const handleUploadViewScrollIntent = useCallback((e) => {
    if (!extended) {
      e.preventDefault();
      e.stopPropagation();
    }
  }, [extended]);

  const renderVideoContent = () => {
    if (queueState !== 'idle') {
      const isConfirming = queueState === 'confirming';

      return (
        <div className="h-full flex items-center justify-center px-4 py-8">
          <div
            className="create-form-enter w-full max-w-sm rounded-3xl glass-card p-6 text-center shadow-xl"
            role="status"
            aria-live="polite"
          >
            <div className="mx-auto mb-4 inline-flex h-14 w-14 items-center justify-center rounded-full bg-white/70">
              {isConfirming ? (
                <Loader2 size={26} className="text-nimbus-700 animate-spin" />
              ) : (
                <CheckCircle2 size={28} className="text-emerald-600" />
              )}
            </div>
            <h2 className="font-display text-2xl font-medium tracking-tight text-ink-950">
              {isConfirming ? 'Confirming queue…' : 'Queued'}
            </h2>
            <p className="mt-2 text-sm text-nimbus-700">
              {isConfirming ? 'One moment.' : 'Track it in Generation Center.'}
            </p>

            {!isConfirming && (
              <button
                type="button"
                onClick={handleReset}
                className="mt-5 inline-flex items-center justify-center rounded-2xl bg-ink-950 px-5 py-3 text-sm font-semibold text-white shadow-pill transition-transform duration-200 hover:-translate-y-0.5"
              >
                Create another video
              </button>
            )}
          </div>
        </div>
      );
    }

    // ---------- Upload View ----------
    if (viewState === 'upload') {
      return (
        <div
          ref={uploadScrollRef}
          onWheelCapture={handleUploadViewScrollIntent}
          onTouchMoveCapture={handleUploadViewScrollIntent}
          className={`h-full flex flex-col items-center px-4 pt-2 pb-6 md:pt-4 md:pb-8 ${extended ? 'overflow-y-auto' : 'overflow-y-hidden'}`}
        >
          <div className="w-full max-w-2xl">
            {/* Saved Models */}
            <section className="mb-5">
              <h3 className="text-sm font-bold text-gray-700 mb-2 flex items-center gap-2">
                <User size={15} className="text-purple-500" />
                Model Image
                {selectedModelId && <span className="text-[10px] bg-purple-100 text-purple-600 px-1.5 py-0.5 rounded-full font-semibold">SAVED</span>}
              </h3>
              <div className="glass-card rounded-2xl p-3">
                <ModelPicker
                  models={savedModels}
                  selectedModelId={selectedModelId}
                  onSelect={setSelectedModelId}
                  onUploadNew={handleModelUploaded}
                  onDelete={handleDeleteModel}
                  loading={loadingModels}
                />
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
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-4">
              <ExtendedToggle extended={extended} onChange={setExtended} />
              <p
                className={`text-xs font-medium transition-all duration-300 ease-out ${
                  extended ? 'text-purple-600 opacity-100 translate-y-0 max-h-8' : 'text-purple-400/70 opacity-0 -translate-y-1 max-h-0 overflow-hidden'
                }`}
              >
                Second section video required
              </p>
            </div>

            {/* Extension Video: library or upload */}
            <div
              className={`overflow-hidden transition-all duration-300 ease-in-out ${
                extended ? 'max-h-[560px] opacity-100 mb-6' : 'max-h-0 opacity-0 mb-0 pointer-events-none'
              }`}
            >
              <section className="pt-1">
                <h3 className="text-sm font-bold text-gray-700 mb-2 flex items-center gap-2">
                  <Film size={15} className="text-purple-500" />
                  Extension Video
                  {selectedExtVideoId && <span className="text-[10px] bg-purple-100 text-purple-600 px-1.5 py-0.5 rounded-full font-semibold">SAVED</span>}
                </h3>
                <div className="glass-card rounded-2xl p-3">
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
                    <div className="mt-3 pt-3 border-t border-nimbus-400/20">
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
            </div>

            <div className="flex justify-center mb-8 md:mb-12">
              <button
                type="button"
                onClick={handleSubmit}
                disabled={!canSubmit || isSubmittingVideo}
                className={`px-8 py-4 font-semibold rounded-2xl transition-all duration-200 shadow-lg hover:shadow-xl inline-flex items-center justify-center gap-2 min-w-[12rem]
                  ${canSubmit && !isSubmittingVideo
                    ? 'bg-gradient-to-r from-purple-600 to-purple-500 text-white hover:from-purple-700 hover:to-purple-600'
                    : 'bg-gray-200 text-gray-400 cursor-not-allowed shadow-none'}`}
              >
                {isSubmittingVideo ? (
                  <>
                    <Loader2 size={20} className="animate-spin shrink-0" />
                    Sending…
                  </>
                ) : (
                  'Generate Video'
                )}
              </button>
            </div>
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
              className="w-full sm:w-auto px-6 py-3 bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold rounded-xl transition-all duration-200"
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
          {[
            { id: 'video', label: 'Video', Icon: Film },
            { id: 'carousel', label: 'Carousel', Icon: Image },
            { id: 'remix', label: 'Remix', Icon: Sparkles },
            { id: 'avatar', label: 'Avatar', Icon: UserCircle2 },
          ].map(({ id, label, Icon }) => {
            const isActive = createTab === id;
            return (
              <button
                key={id}
                type="button"
                onClick={() => setCreateTab(id)}
                aria-pressed={isActive}
                className={`inline-flex items-center px-3 py-2 md:px-5 md:py-2.5 rounded-xl text-sm font-semibold transition-all duration-300 ease-out ${
                  isActive
                    ? 'bg-gradient-to-r from-purple-600 to-purple-500 text-white shadow'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                <Icon size={16} className="flex-shrink-0" />
                <span
                  className={`overflow-hidden whitespace-nowrap transition-all duration-300 ease-out ${
                    isActive
                      ? 'max-w-[100px] opacity-100 ml-2'
                      : 'max-w-0 opacity-0 ml-0 sm:max-w-[100px] sm:opacity-100 sm:ml-2'
                  }`}
                >
                  {label}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex-1 min-h-0">
        <div
          key={createTab}
          style={{ animation: 'slideDownFade 0.22s ease-out' }}
          className="h-full"
        >
          {createTab === 'video'
            ? renderVideoContent()
            : createTab === 'carousel'
              ? <CarouselStudio />
              : createTab === 'remix'
                ? <RemixStudio />
                : <AvatarStudio
                    onGenerationStarted={onVideoGenerationStarted}
                    onUseAvatarForVideo={(avatar) => {
                      setSelectedModelId(avatar.modelId);
                      setCreateTab('video');
                    }}
                  />}
        </div>
      </div>
    </div>
  );
}

export default CreateSection;
