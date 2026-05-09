export const CAMPAIGN_TYPES = [
  {
    id: 'app',
    label: 'App',
    eyebrow: 'Digital product',
    description: 'Promote an app, tool, or platform with real usage footage.',
  },
  {
    id: 'product',
    label: 'Product',
    eyebrow: 'Physical product',
    description: 'Promote a physical item with product images and creator-led context.',
  },
];

export const CAMPAIGN_NICHES = [
  {
    id: 'gym-clothing-brand',
    label: 'Gym clothing brand',
    campaignType: 'product',
    description: 'Show the fit, lifestyle, and confidence behind the clothing.',
    requiredAsset: {
      type: 'productImages',
      label: 'Clothing images',
      helper: 'Upload at least one product or outfit image for the campaign plan.',
      accept: 'image/*',
    },
    plan: [
      {
        label: 'Outfit and product showcase',
        contentPillarId: 'product_demo',
        percentage: 35,
        description: 'Clean try-ons, fit checks, and detail shots that make the clothing easy to understand.',
        examples: ['Mirror fit check', 'Legging stretch test', 'Gym bag outfit flat lay'],
      },
      {
        label: 'Gym lifestyle and mirror content',
        contentPillarId: 'relatable_lifestyle',
        percentage: 25,
        description: 'Creator-led clips that make the clothing feel native to daily gym routines.',
        examples: ['Pre-workout mirror video', 'Walking into the gym', 'Post-lift confidence clip'],
      },
      {
        label: 'Social proof and transformation context',
        contentPillarId: 'transformation_progress',
        percentage: 20,
        description: 'Content that connects the product to confidence, progress, or community.',
        examples: ['Before class vs after class', 'Why this set became my favorite', 'Friend reaction angle'],
      },
      {
        label: 'Trending sounds and creator hooks',
        contentPillarId: 'trend_reaction',
        percentage: 20,
        description: 'Trend-native clips built around quick hooks, sounds, and repeatable formats.',
        examples: ['POV gym crush notices the fit', 'This set carried my workout', 'GRWM for leg day'],
      },
    ],
  },
  {
    id: 'study-education-app',
    label: 'Study/Education app',
    campaignType: 'app',
    description: 'Position the app as a useful part of a student routine.',
    requiredAsset: {
      type: 'appVideos',
      label: 'App overview video',
      helper: 'Upload at least one real screen recording or overview video of the app.',
      accept: 'video/*',
    },
    plan: [
      {
        label: 'Trending sounds and videos',
        contentPillarId: 'trend_reaction',
        percentage: 30,
        description: 'Trend-backed formats that make the app feel native to social feeds.',
        examples: ['Study desk trend', 'Library day-in-the-life', 'POV finals week sound'],
      },
      {
        label: 'Hook plus showing demo',
        contentPillarId: 'app_demo',
        percentage: 10,
        description: 'Short direct-response clips that show the app solving one clear problem.',
        examples: ['I wish I had this before finals', 'How I organize a study session', 'One feature in 10 seconds'],
      },
      {
        label: 'Relatable study content',
        contentPillarId: 'relatable_lifestyle',
        percentage: 30,
        description: 'Low-pressure student scenarios that make the app feel useful and believable.',
        examples: ['Procrastination reset', 'Sunday study plan', 'When your notes are chaos'],
      },
      {
        label: 'Inspiration content',
        contentPillarId: 'educational_tips',
        percentage: 30,
        description: 'Motivational content around consistency, goals, and becoming a better student.',
        examples: ['Romanticizing studying', 'Academic comeback', 'Small habits that compound'],
      },
    ],
  },
  {
    id: 'gym-app',
    label: 'Gym App',
    campaignType: 'app',
    description: 'Show how the app supports workouts, consistency, and progress.',
    requiredAsset: {
      type: 'appVideos',
      label: 'App overview video',
      helper: 'Upload at least one real screen recording or overview video of the app.',
      accept: 'video/*',
    },
    plan: [
      {
        label: 'Workout and demo walkthroughs',
        contentPillarId: 'routine_explainer',
        percentage: 30,
        description: 'Practical videos that show the app being used before, during, or after workouts.',
        examples: ['Building a leg day plan', 'Tracking a PR', 'Using the timer between sets'],
      },
      {
        label: 'Transformation and progress content',
        contentPillarId: 'transformation_progress',
        percentage: 25,
        description: 'Aspirational clips around measurable progress and consistency.',
        examples: ['Week one vs week four', 'How I stopped guessing workouts', 'Progress photo routine'],
      },
      {
        label: 'Relatable gym routines',
        contentPillarId: 'relatable_lifestyle',
        percentage: 25,
        description: 'Everyday gym moments that make the app feel approachable.',
        examples: ['No idea what to train today', 'Beginner gym anxiety', 'Busy day quick workout'],
      },
      {
        label: 'Trending sounds and quick hooks',
        contentPillarId: 'trend_reaction',
        percentage: 20,
        description: 'Fast trend formats that frame the app around a memorable hook.',
        examples: ['POV you finally have a plan', 'Gym bro checklist', 'This app fixed my split'],
      },
    ],
  },
];

export function getCampaignType(typeId) {
  return CAMPAIGN_TYPES.find((type) => type.id === typeId) || null;
}

export function getCampaignNiche(nicheId) {
  return CAMPAIGN_NICHES.find((niche) => niche.id === nicheId) || null;
}

export function getNichesForType(typeId) {
  return CAMPAIGN_NICHES.filter((niche) => niche.campaignType === typeId);
}
