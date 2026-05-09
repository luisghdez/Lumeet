import React, { useMemo, useReducer } from 'react';
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  Dumbbell,
  Image as ImageIcon,
  Loader2,
  Package,
  RotateCcw,
  Shirt,
  Smartphone,
  Sparkles,
  Upload,
  User,
  Video,
  X,
} from 'lucide-react';
import { useModels } from '../lib/mediaLibrary';
import {
  CAMPAIGN_TYPES,
  getCampaignNiche,
  getCampaignType,
  getNichesForType,
} from '../lib/campaignNiches';

const STEPS = [
  { id: 'type', label: 'Type' },
  { id: 'model', label: 'Model' },
  { id: 'niche', label: 'Niche' },
  { id: 'assets', label: 'Assets' },
  { id: 'plan', label: 'Plan' },
];

const initialState = {
  campaignType: null,
  modelId: null,
  nicheId: null,
  appVideos: [],
  productImages: [],
};

function campaignReducer(state, action) {
  switch (action.type) {
    case 'setCampaignType':
      return {
        ...state,
        campaignType: action.campaignType,
        nicheId: null,
        appVideos: [],
        productImages: [],
      };
    case 'setModel':
      return { ...state, modelId: action.modelId };
    case 'setNiche':
      return {
        ...state,
        nicheId: action.nicheId,
        appVideos: [],
        productImages: [],
      };
    case 'addAssets': {
      const entries = Array.from(action.files || []).map((file) => ({
        id: `${file.name}-${file.lastModified}-${crypto.randomUUID?.() || Math.random()}`,
        file,
      }));
      return {
        ...state,
        [action.assetType]: [...state[action.assetType], ...entries],
      };
    }
    case 'removeAsset':
      return {
        ...state,
        [action.assetType]: state[action.assetType].filter((asset) => asset.id !== action.assetId),
      };
    case 'reset':
      return initialState;
    default:
      return state;
  }
}

function getAssetCount(state, assetType) {
  return assetType ? state[assetType]?.length || 0 : 0;
}

function getIconForType(typeId) {
  if (typeId === 'app') return Smartphone;
  return Package;
}

function getIconForNiche(nicheId) {
  if (nicheId === 'study-education-app') return BookOpen;
  if (nicheId === 'gym-clothing-brand') return Shirt;
  return Dumbbell;
}

function getStepTitle(stepId) {
  if (stepId === 'type') return 'What are you promoting?';
  if (stepId === 'model') return 'Choose the creator model';
  if (stepId === 'niche') return 'Pick the campaign niche';
  if (stepId === 'assets') return 'Add the source material';
  return 'Your campaign content mix';
}

function getStepDescription(stepId) {
  if (stepId === 'type') return 'Start with the campaign format so the rest of the flow only asks for what matters.';
  if (stepId === 'model') return 'Select one saved model that will represent this campaign.';
  if (stepId === 'niche') return 'Choose the closest niche. This drives the content split and asset requirements.';
  if (stepId === 'assets') return 'Add real source material so the next step can become specific and usable.';
  return 'Review the recommended split. This is the stopping point for this phase.';
}

function CampaignProgress({ currentIndex }) {
  return (
    <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-hide" aria-label="Campaign setup progress">
      {STEPS.map((step, index) => {
        const isCurrent = index === currentIndex;
        const isDone = index < currentIndex;
        return (
          <div key={step.id} className="flex items-center gap-2 shrink-0">
            <span
              className={`inline-flex h-8 items-center gap-2 rounded-full px-3 text-xs font-semibold transition-colors ${
                isCurrent
                  ? 'bg-ink-950 text-white shadow-pill'
                  : isDone
                    ? 'bg-white/70 text-ink-950'
                    : 'bg-white/35 text-nimbus-700'
              }`}
            >
              {isDone ? <CheckCircle2 size={13} /> : <span>{index + 1}</span>}
              {step.label}
            </span>
            {index < STEPS.length - 1 && <span className="h-px w-5 bg-white/50" aria-hidden />}
          </div>
        );
      })}
    </div>
  );
}

function ChoiceCard({ title, eyebrow, description, selected, onClick, icon: Icon }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={`group rounded-3xl border-2 p-5 text-left transition-all duration-200 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.35)] ${
        selected
          ? 'border-nimbus-700/60 bg-white/55 ring-2 ring-white/70 shadow-md'
          : 'border-nimbus-400/35 bg-white/20 hover:border-nimbus-500/50 hover:bg-white/32'
      }`}
    >
      <div className="flex items-start justify-between gap-4">
        <span className="inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-white/65 text-nimbus-800">
          <Icon size={21} />
        </span>
        <span
          className={`mt-1 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border ${
            selected ? 'border-purple-500 bg-purple-500' : 'border-nimbus-400/60 bg-white/50'
          }`}
        >
          {selected && <CheckCircle2 size={13} className="text-white" />}
        </span>
      </div>
      {eyebrow && (
        <p className="mt-4 text-[10px] font-bold uppercase tracking-[0.16em] text-purple-600">
          {eyebrow}
        </p>
      )}
      <h3 className="mt-1 font-display text-xl font-medium tracking-tight text-ink-950">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-nimbus-700">{description}</p>
    </button>
  );
}

function SavedModelPicker({ models, loading, selectedModelId, onSelect }) {
  if (loading) {
    return (
      <div className="flex items-center justify-center rounded-3xl glass-card p-10">
        <Loader2 size={20} className="animate-spin text-purple-500" />
        <span className="ml-2 text-sm font-medium text-nimbus-700">Loading saved models...</span>
      </div>
    );
  }

  if (!models.length) {
    return (
      <div className="rounded-3xl glass-card p-8 text-center">
        <div className="mx-auto mb-4 inline-flex h-12 w-12 items-center justify-center rounded-full bg-white/65">
          <User size={22} className="text-nimbus-700" />
        </div>
        <h3 className="font-display text-xl font-medium tracking-tight text-ink-950">No saved models yet</h3>
        <p className="mx-auto mt-2 max-w-sm text-sm leading-6 text-nimbus-700">
          Create or upload a model in the existing Create flow, then come back to assign it to a campaign.
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      {models.map((model) => {
        const selected = model.modelId === selectedModelId;
        const label = model.label || model.modelId.slice(0, 8);
        return (
          <button
            key={model.modelId}
            type="button"
            onClick={() => onSelect(selected ? null : model.modelId)}
            aria-pressed={selected}
            className={`group overflow-hidden rounded-3xl border-2 bg-white/25 text-left transition-all duration-200 ${
              selected
                ? 'border-nimbus-700/70 ring-2 ring-white/70 shadow-md'
                : 'border-nimbus-400/35 hover:border-nimbus-500/50 hover:bg-white/35'
            }`}
          >
            <div className="relative aspect-[4/5] overflow-hidden bg-white/35">
              <img src={model.url} alt={label} className="h-full w-full object-cover" loading="lazy" />
              {selected && (
                <span className="absolute right-2 top-2 inline-flex rounded-full bg-purple-500 p-1 text-white shadow">
                  <CheckCircle2 size={14} />
                </span>
              )}
            </div>
            <div className="px-3 py-2">
              <p className="truncate text-sm font-semibold text-ink-950">{label}</p>
              <p className="text-[11px] text-nimbus-600">Saved model</p>
            </div>
          </button>
        );
      })}
    </div>
  );
}

function FilePreview({ asset, assetType, onRemove }) {
  const [previewUrl, setPreviewUrl] = React.useState('');

  React.useEffect(() => {
    const url = URL.createObjectURL(asset.file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [asset.file]);

  const isVideo = asset.file.type.startsWith('video/');

  return (
    <div className="group relative overflow-hidden rounded-2xl border border-white/60 bg-white/35">
      <div className="aspect-video bg-white/30">
        {isVideo ? (
          <video src={previewUrl} className="h-full w-full object-cover" muted playsInline preload="metadata" />
        ) : (
          <img src={previewUrl} alt="" className="h-full w-full object-cover" />
        )}
      </div>
      <div className="px-3 py-2">
        <p className="truncate text-xs font-semibold text-ink-950">{asset.file.name}</p>
        <p className="text-[11px] text-nimbus-600">{(asset.file.size / (1024 * 1024)).toFixed(1)} MB</p>
      </div>
      <button
        type="button"
        onClick={() => onRemove(assetType, asset.id)}
        className="absolute right-2 top-2 inline-flex h-7 w-7 items-center justify-center rounded-full bg-ink-950/80 text-white opacity-0 transition-opacity group-hover:opacity-100"
        aria-label={`Remove ${asset.file.name}`}
      >
        <X size={14} />
      </button>
    </div>
  );
}

function AssetUploadStep({ niche, assets, onAddAssets, onRemoveAsset }) {
  const rule = niche?.requiredAsset;
  if (!rule) return null;

  const Icon = rule.type === 'appVideos' ? Video : ImageIcon;
  const count = assets.length;

  return (
    <div className="space-y-5">
      <label className="block cursor-pointer rounded-3xl border-2 border-dashed border-nimbus-400/45 bg-white/20 p-8 text-center transition-colors hover:border-nimbus-500/55 hover:bg-white/30">
        <input
          type="file"
          accept={rule.accept}
          multiple
          className="hidden"
          onChange={(event) => {
            onAddAssets(rule.type, event.target.files);
            event.target.value = '';
          }}
        />
        <span className="mx-auto mb-4 inline-flex h-14 w-14 items-center justify-center rounded-full bg-white/65 text-nimbus-800">
          <Upload size={24} />
        </span>
        <span className="block font-display text-xl font-medium tracking-tight text-ink-950">
          {rule.label}
        </span>
        <span className="mt-2 block text-sm leading-6 text-nimbus-700">{rule.helper}</span>
        <span className="mt-4 inline-flex items-center gap-2 rounded-full bg-white/60 px-3 py-1.5 text-xs font-semibold text-nimbus-700">
          <Icon size={14} />
          {count > 0 ? `${count} added` : 'At least one required'}
        </span>
      </label>

      {count > 0 && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {assets.map((asset) => (
            <FilePreview
              key={asset.id}
              asset={asset}
              assetType={rule.type}
              onRemove={onRemoveAsset}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function CampaignSummary({ campaignType, model, niche, assetCount }) {
  return (
    <aside className="glass-card rounded-3xl p-5 lg:sticky lg:top-8">
      <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-purple-600">Campaign brief</p>
      <h2 className="mt-1 font-display text-2xl font-medium tracking-tight text-ink-950">
        {niche?.label || 'New campaign'}
      </h2>
      <div className="mt-5 space-y-3 text-sm">
        <SummaryRow label="Type" value={campaignType?.label || 'Not selected'} />
        <SummaryRow label="Model" value={model?.label || (model ? model.modelId.slice(0, 8) : 'Not selected')} />
        <SummaryRow label="Niche" value={niche?.label || 'Not selected'} />
        <SummaryRow label="Assets" value={assetCount ? `${assetCount} added` : 'None yet'} />
      </div>
    </aside>
  );
}

function SummaryRow({ label, value }) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-2xl bg-white/35 px-3 py-2">
      <span className="text-nimbus-600">{label}</span>
      <span className="max-w-[11rem] truncate text-right font-semibold text-ink-950">{value}</span>
    </div>
  );
}

function CampaignPlanPreview({ niche, campaignType, model, assetCount }) {
  return (
    <div className="space-y-5">
      <div className="rounded-3xl bg-ink-950 p-6 text-white shadow-pill">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-white/50">Recommended split</p>
            <h3 className="mt-2 font-display text-3xl font-medium tracking-tight">{niche.label}</h3>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-white/70">{niche.description}</p>
          </div>
          <div className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1.5 text-xs font-semibold text-white/80">
            <Sparkles size={14} />
            Stops before generation
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {niche.plan.map((item) => (
          <div key={item.label} className="rounded-3xl glass-card p-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-purple-600">
                  {item.percentage}% of content
                </p>
                <h4 className="mt-1 font-display text-xl font-medium tracking-tight text-ink-950">
                  {item.label}
                </h4>
              </div>
              <span className="inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-white/65 text-sm font-bold text-ink-950">
                {item.percentage}%
              </span>
            </div>
            <p className="mt-3 text-sm leading-6 text-nimbus-700">{item.description}</p>
            <div className="mt-4 flex flex-wrap gap-1.5">
              {item.examples.map((example) => (
                <span key={example} className="rounded-full bg-white/55 px-2.5 py-1 text-[11px] font-medium text-nimbus-700">
                  {example}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="rounded-3xl glass-card p-5">
        <p className="text-sm font-semibold text-ink-950">Brief summary</p>
        <p className="mt-2 text-sm leading-6 text-nimbus-700">
          This {campaignType.label.toLowerCase()} campaign uses {model?.label || 'the selected model'} with {assetCount} source asset{assetCount === 1 ? '' : 's'}.
          The next step can turn these buckets into scripts, references, and generation inputs.
        </p>
      </div>
    </div>
  );
}

export default function CampaignStudio() {
  const [state, dispatch] = useReducer(campaignReducer, initialState);
  const [stepIndex, setStepIndex] = React.useState(0);
  const currentStep = STEPS[stepIndex].id;
  const { models, loading: loadingModels } = useModels();

  const campaignType = getCampaignType(state.campaignType);
  const availableNiches = useMemo(() => getNichesForType(state.campaignType), [state.campaignType]);
  const niche = getCampaignNiche(state.nicheId);
  const selectedModel = models.find((model) => model.modelId === state.modelId) || null;
  const assetType = niche?.requiredAsset?.type;
  const relevantAssets = assetType ? state[assetType] : [];
  const assetCount = getAssetCount(state, assetType);

  const canContinue = useMemo(() => {
    if (currentStep === 'type') return Boolean(state.campaignType);
    if (currentStep === 'model') return Boolean(state.modelId);
    if (currentStep === 'niche') return Boolean(state.nicheId);
    if (currentStep === 'assets') return assetCount > 0;
    return false;
  }, [assetCount, currentStep, state.campaignType, state.modelId, state.nicheId]);

  const goNext = () => {
    if (canContinue && stepIndex < STEPS.length - 1) {
      setStepIndex((index) => index + 1);
    }
  };

  const goBack = () => {
    setStepIndex((index) => Math.max(0, index - 1));
  };

  const handleReset = () => {
    dispatch({ type: 'reset' });
    setStepIndex(0);
  };

  const renderStep = () => {
    if (currentStep === 'type') {
      return (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {CAMPAIGN_TYPES.map((type) => (
            <ChoiceCard
              key={type.id}
              title={type.label}
              eyebrow={type.eyebrow}
              description={type.description}
              icon={getIconForType(type.id)}
              selected={state.campaignType === type.id}
              onClick={() => dispatch({ type: 'setCampaignType', campaignType: type.id })}
            />
          ))}
        </div>
      );
    }

    if (currentStep === 'model') {
      return (
        <SavedModelPicker
          models={models}
          loading={loadingModels}
          selectedModelId={state.modelId}
          onSelect={(modelId) => dispatch({ type: 'setModel', modelId })}
        />
      );
    }

    if (currentStep === 'niche') {
      return (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {availableNiches.map((item) => (
            <ChoiceCard
              key={item.id}
              title={item.label}
              eyebrow={campaignType?.label}
              description={item.description}
              icon={getIconForNiche(item.id)}
              selected={state.nicheId === item.id}
              onClick={() => dispatch({ type: 'setNiche', nicheId: item.id })}
            />
          ))}
        </div>
      );
    }

    if (currentStep === 'assets') {
      return (
        <AssetUploadStep
          niche={niche}
          assets={relevantAssets}
          onAddAssets={(type, files) => dispatch({ type: 'addAssets', assetType: type, files })}
          onRemoveAsset={(type, assetId) => dispatch({ type: 'removeAsset', assetType: type, assetId })}
        />
      );
    }

    return (
      <CampaignPlanPreview
        niche={niche}
        campaignType={campaignType}
        model={selectedModel}
        assetCount={assetCount}
      />
    );
  };

  return (
    <div className="mx-auto flex h-full max-w-7xl flex-col">
      <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-purple-600">Campaign Studio</p>
          <h1 className="mt-2 font-display text-display-xs font-medium tracking-tightest text-ink-950 md:text-display-sm">
            Create an influencer campaign
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-nimbus-700 md:text-base">
            A focused onboarding flow for turning a product or app into a clear content plan.
          </p>
        </div>
        <button
          type="button"
          onClick={handleReset}
          className="inline-flex items-center justify-center gap-2 rounded-full bg-white/55 px-4 py-2 text-sm font-semibold text-nimbus-800 transition-colors hover:bg-white/75"
        >
          <RotateCcw size={15} />
          Reset
        </button>
      </div>

      <CampaignProgress currentIndex={stepIndex} />

      <div className="mt-6 grid flex-1 grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <section className="glass-card rounded-[2rem] p-5 md:p-7">
          <div className="mb-6">
            <h2 className="font-display text-3xl font-medium tracking-tight text-ink-950">
              {getStepTitle(currentStep)}
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-nimbus-700">
              {getStepDescription(currentStep)}
            </p>
          </div>

          <div style={{ animation: 'slideDownFade 0.22s ease-out' }} key={currentStep}>
            {renderStep()}
          </div>

          <div className="mt-8 flex items-center justify-between gap-3">
            <button
              type="button"
              onClick={goBack}
              disabled={stepIndex === 0}
              className="inline-flex items-center gap-2 rounded-full bg-white/45 px-4 py-2 text-sm font-semibold text-nimbus-800 transition-colors hover:bg-white/65 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <ArrowLeft size={15} />
              Back
            </button>

            {currentStep !== 'plan' ? (
              <button
                type="button"
                onClick={goNext}
                disabled={!canContinue}
                className={`inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-semibold transition-all duration-200 ${
                  canContinue
                    ? 'bg-ink-950 text-white shadow-pill hover:-translate-y-0.5'
                    : 'bg-white/45 text-nimbus-500 cursor-not-allowed'
                }`}
              >
                Continue
                <ArrowRight size={15} />
              </button>
            ) : (
              <span className="inline-flex items-center gap-2 rounded-full bg-emerald-500/15 px-4 py-2 text-sm font-semibold text-emerald-700">
                <CheckCircle2 size={15} />
                Plan ready
              </span>
            )}
          </div>
        </section>

        <CampaignSummary
          campaignType={campaignType}
          model={selectedModel}
          niche={niche}
          assetCount={assetCount}
        />
      </div>
    </div>
  );
}
