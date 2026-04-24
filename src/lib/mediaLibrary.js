import { useEffect, useSyncExternalStore } from 'react';
import {
  listModels,
  listExtensionVideos,
  listHooks,
  listSounds,
  listVideos,
  listCarousels,
} from './lateApi';

const VIDEO_PAGE_SIZE = 5;

// ---------------------------------------------------------------------------
// Lightweight pub-sub store shared across the app.
// Data is fetched once and kept in memory for the lifetime of the page, so
// navigating between tabs renders instantly instead of re-hitting the API.
// ---------------------------------------------------------------------------

function createStore(fetcher, extract, initialData = []) {
  let state = { data: initialData, loading: false, loaded: false, error: null };
  let pending = null;
  const listeners = new Set();

  const emit = () => {
    listeners.forEach((listener) => listener(state));
  };

  const setState = (patch) => {
    state = { ...state, ...patch };
    emit();
  };

  const load = (force = false) => {
    if (pending) return pending;
    if (state.loaded && !force) return Promise.resolve(state.data);
    setState({ loading: true, error: null });
    pending = (async () => {
      try {
        const raw = await fetcher();
        const items = extract(raw) || [];
        setState({ data: items, loading: false, loaded: true, error: null });
        return items;
      } catch (err) {
        console.error('Media library load failed:', err);
        setState({ loading: false, error: err });
        return [];
      } finally {
        pending = null;
      }
    })();
    return pending;
  };

  const subscribe = (listener) => {
    listeners.add(listener);
    return () => listeners.delete(listener);
  };

  const getSnapshot = () => state;

  const mutate = (updater) => {
    const nextData =
      typeof updater === 'function' ? updater(state.data) : updater;
    setState({ data: nextData });
  };

  return { load, subscribe, getSnapshot, mutate };
}

export const modelStore = createStore(listModels, (d) => d?.models);
export const extensionVideoStore = createStore(
  listExtensionVideos,
  (d) => d?.extensionVideos
);
export const hookStore = createStore(listHooks, (d) => d?.hooks);
export const soundStore = createStore(listSounds, (d) => d?.sounds);

// Generated video library (paginated). Data shape: { items, total }.
export const videoStore = createStore(
  () => listVideos({ limit: VIDEO_PAGE_SIZE, offset: 0 }),
  (d) => ({
    items: d?.videos || [],
    total: d?.total ?? (d?.videos?.length || 0),
  }),
  { items: [], total: 0 }
);

export const carouselStore = createStore(
  listCarousels,
  (d) => d?.carousels
);

// ---------------------------------------------------------------------------
// Asset warm-up: prime the browser HTTP cache so the first render of pickers
// paints instantly instead of waterfall-loading thumbnails.
// ---------------------------------------------------------------------------

const MODEL_WARM_COUNT = 12;
const HOOK_WARM_COUNT = 6;
const EXT_VIDEO_WARM_COUNT = 6;
const LIBRARY_VIDEO_WARM_COUNT = 5;
const CAROUSEL_WARM_COUNT = 12;

const warmedImages = new Set();
const warmedVideos = new Set();

function warmImage(url) {
  if (!url || warmedImages.has(url)) return;
  warmedImages.add(url);
  const img = new window.Image();
  img.decoding = 'async';
  img.loading = 'eager';
  img.src = url;
}

function warmVideoMetadata(url) {
  if (!url || warmedVideos.has(url)) return;
  warmedVideos.add(url);
  const video = document.createElement('video');
  video.preload = 'metadata';
  video.muted = true;
  video.playsInline = true;
  video.src = url;
  const cleanup = () => {
    video.removeEventListener('loadedmetadata', cleanup);
    video.removeEventListener('error', cleanup);
    video.removeAttribute('src');
    video.load();
  };
  video.addEventListener('loadedmetadata', cleanup, { once: true });
  video.addEventListener('error', cleanup, { once: true });
}

function warmModelAssets(models) {
  models.slice(0, MODEL_WARM_COUNT).forEach((m) => warmImage(m.url));
}

function warmHookAssets(hooks) {
  hooks.slice(0, HOOK_WARM_COUNT).forEach((h) => warmVideoMetadata(h.url));
}

function warmExtensionVideoAssets(videos) {
  videos
    .slice(0, EXT_VIDEO_WARM_COUNT)
    .forEach((v) => warmVideoMetadata(v.url));
}

function warmLibraryVideoAssets(videos) {
  videos
    .slice(0, LIBRARY_VIDEO_WARM_COUNT)
    .forEach((v) => warmVideoMetadata(v.url));
}

function warmCarouselAssets(carousels) {
  const slice = carousels.slice(0, CAROUSEL_WARM_COUNT);
  slice.forEach((c) => {
    const firstImage = c.mediaUrls?.[0] || c.slides?.[0]?.url;
    if (firstImage) warmImage(firstImage);
  });
}

// ---------------------------------------------------------------------------
// Public entrypoint — call once on app boot to kick off every fetch in
// parallel. Safe to call multiple times; stores short-circuit if already
// loaded / in-flight.
// ---------------------------------------------------------------------------

let preloadPromise = null;

export function preloadMediaLibrary() {
  if (preloadPromise) return preloadPromise;
  preloadPromise = (async () => {
    const [models, extVideos, hooks, , videosData, carousels] = await Promise.all([
      modelStore.load().then((items) => {
        warmModelAssets(items);
        return items;
      }),
      extensionVideoStore.load().then((items) => {
        warmExtensionVideoAssets(items);
        return items;
      }),
      hookStore.load().then((items) => {
        warmHookAssets(items);
        return items;
      }),
      soundStore.load(),
      videoStore.load().then((data) => {
        warmLibraryVideoAssets(data?.items || []);
        return data;
      }),
      carouselStore.load().then((items) => {
        warmCarouselAssets(items);
        return items;
      }),
    ]);
    return { models, extVideos, hooks, videosData, carousels };
  })();
  return preloadPromise;
}

// ---------------------------------------------------------------------------
// React hooks — consume stores via useSyncExternalStore so any mutation
// broadcasts to every subscriber in the tree.
// ---------------------------------------------------------------------------

function useStore(store) {
  const snapshot = useSyncExternalStore(
    store.subscribe,
    store.getSnapshot,
    store.getSnapshot
  );
  useEffect(() => {
    store.load();
  }, [store]);
  return snapshot;
}

export function useModels() {
  const { data, loading, loaded, error } = useStore(modelStore);
  return {
    models: data,
    loading: loading && !loaded,
    error,
    refresh: () => modelStore.load(true),
    setModels: modelStore.mutate,
  };
}

export function useExtensionVideos() {
  const { data, loading, loaded, error } = useStore(extensionVideoStore);
  return {
    extensionVideos: data,
    loading: loading && !loaded,
    error,
    refresh: () => extensionVideoStore.load(true),
    setExtensionVideos: extensionVideoStore.mutate,
  };
}

export function useHooks() {
  const { data, loading, loaded, error } = useStore(hookStore);
  return {
    hooks: data,
    loading: loading && !loaded,
    error,
    refresh: () => hookStore.load(true),
    setHooks: hookStore.mutate,
  };
}

export function useSounds() {
  const { data, loading, loaded, error } = useStore(soundStore);
  return {
    sounds: data,
    loading: loading && !loaded,
    error,
    refresh: () => soundStore.load(true),
    setSounds: soundStore.mutate,
  };
}

export function useLibraryVideos() {
  const { data, loading, loaded, error } = useStore(videoStore);
  const setVideos = (updater) => {
    videoStore.mutate((prev) => {
      const items = typeof updater === 'function' ? updater(prev?.items || []) : updater;
      return { items: Array.isArray(items) ? items : prev?.items || [], total: prev?.total || 0 };
    });
  };
  const setTotal = (total) => {
    videoStore.mutate((prev) => ({ items: prev?.items || [], total }));
  };
  return {
    videos: data?.items || [],
    total: data?.total || 0,
    loading: loading && !loaded,
    error,
    refresh: () => videoStore.load(true),
    setVideos,
    setTotal,
  };
}

export function useLibraryCarousels() {
  const { data, loading, loaded, error } = useStore(carouselStore);
  return {
    carousels: data,
    loading: loading && !loaded,
    error,
    refresh: () => carouselStore.load(true),
    setCarousels: carouselStore.mutate,
  };
}
