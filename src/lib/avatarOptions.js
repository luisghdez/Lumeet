/**
 * Avatar Studio — Visual Option Manifest
 *
 * Each option carries:
 *   - id: stable key (sent to backend)
 *   - label: user-facing text
 *   - prompt: short fragment merged into the avatar generation prompt
 *   - thumbnail: optional path to a static image asset under src/assets/avatar-options
 *   - swatch: optional CSS color (used when no thumbnail is generated)
 *   - icon: optional lucide-react icon name (rendered by AvatarStudio)
 *
 * Sections describe how a category renders in the builder panel:
 *   - kind: 'photo' | 'swatch' | 'icon'
 *   - required: must be selected before Generate is enabled
 *   - allowMultiple: if true, value is an array of ids
 *   - columns: thumbnail grid columns
 */

import maleThumb from '../assets/avatar-options/gender-male.png';
import femaleThumb from '../assets/avatar-options/gender-female.png';
import nonbinaryThumb from '../assets/avatar-options/gender-nonbinary.png';
import transwomanThumb from '../assets/avatar-options/gender-transwoman.png';
import transmanThumb from '../assets/avatar-options/gender-transman.png';

import africanThumb from '../assets/avatar-options/ethnicity-african.png';
import asianThumb from '../assets/avatar-options/ethnicity-asian.png';
import europeanThumb from '../assets/avatar-options/ethnicity-european.png';
import indianThumb from '../assets/avatar-options/ethnicity-indian.png';
import middleEasternThumb from '../assets/avatar-options/ethnicity-middle-eastern.png';
import mixedThumb from '../assets/avatar-options/ethnicity-mixed.png';
import latinAmericanThumb from '../assets/avatar-options/ethnicity-latin-american.png';
import indigenousThumb from '../assets/avatar-options/ethnicity-indigenous.png';
import pacificIslanderThumb from '../assets/avatar-options/ethnicity-pacific-islander.png';

import ageYoungThumb from '../assets/avatar-options/age-young-adult.png';
import ageAdultThumb from '../assets/avatar-options/age-adult.png';
import ageMatureThumb from '../assets/avatar-options/age-mature.png';

import hairStraight from '../assets/avatar-options/hair-straight.png';
import hairWavy from '../assets/avatar-options/hair-wavy.png';
import hairCurly from '../assets/avatar-options/hair-curly.png';
import hairCoily from '../assets/avatar-options/hair-coily.png';
import hairBuzz from '../assets/avatar-options/hair-buzz.png';

import outfitCasual from '../assets/avatar-options/outfit-casual.png';
import outfitStreetwear from '../assets/avatar-options/outfit-streetwear.png';
import outfitFormal from '../assets/avatar-options/outfit-formal.png';
import outfitAthletic from '../assets/avatar-options/outfit-athletic.png';
import outfitYAcademia from '../assets/avatar-options/outfit-academia.png';
import outfitCozy from '../assets/avatar-options/outfit-cozy.png';

export const AVATAR_SECTIONS = [
  {
    id: 'gender',
    label: 'Gender',
    icon: 'User',
    kind: 'photo',
    required: true,
    columns: 3,
    options: [
      { id: 'female', label: 'Female', prompt: 'female-presenting', thumbnail: femaleThumb },
      { id: 'male', label: 'Male', prompt: 'male-presenting', thumbnail: maleThumb },
      { id: 'non_binary', label: 'Non-binary', prompt: 'androgynous non-binary', thumbnail: nonbinaryThumb },
      { id: 'trans_woman', label: 'Trans woman', prompt: 'trans woman', thumbnail: transwomanThumb },
      { id: 'trans_man', label: 'Trans man', prompt: 'trans man', thumbnail: transmanThumb },
    ],
  },

  {
    id: 'ethnicity',
    label: 'Ethnicity / Origin Base',
    icon: 'Globe',
    kind: 'photo',
    required: true,
    columns: 3,
    options: [
      { id: 'african', label: 'African', prompt: 'African features and heritage', thumbnail: africanThumb },
      { id: 'asian', label: 'East Asian', prompt: 'East Asian features and heritage', thumbnail: asianThumb },
      { id: 'european', label: 'European', prompt: 'European features and heritage', thumbnail: europeanThumb },
      { id: 'indian', label: 'South Asian', prompt: 'South Asian / Indian features and heritage', thumbnail: indianThumb },
      { id: 'middle_eastern', label: 'Middle Eastern', prompt: 'Middle Eastern features and heritage', thumbnail: middleEasternThumb },
      { id: 'mixed', label: 'Mixed', prompt: 'mixed-race features', thumbnail: mixedThumb },
      { id: 'latin_american', label: 'Latin American', prompt: 'Latin American features and heritage', thumbnail: latinAmericanThumb },
      { id: 'indigenous', label: 'Indigenous', prompt: 'Indigenous American features and heritage', thumbnail: indigenousThumb },
      { id: 'pacific_islander', label: 'Pacific Islander', prompt: 'Pacific Islander features and heritage', thumbnail: pacificIslanderThumb },
    ],
  },

  {
    id: 'skinTone',
    label: 'Skin Tone',
    icon: 'Palette',
    kind: 'swatch',
    required: true,
    columns: 6,
    options: [
      { id: 'porcelain', label: 'Porcelain', prompt: 'porcelain skin tone', swatch: '#F5DEC4' },
      { id: 'fair', label: 'Fair', prompt: 'fair skin tone', swatch: '#EFC9A6' },
      { id: 'light', label: 'Light', prompt: 'light skin tone', swatch: '#E1B189' },
      { id: 'medium', label: 'Medium', prompt: 'medium / olive skin tone', swatch: '#C99069' },
      { id: 'tan', label: 'Tan', prompt: 'tan / golden skin tone', swatch: '#A4724B' },
      { id: 'caramel', label: 'Caramel', prompt: 'caramel skin tone', swatch: '#82542F' },
      { id: 'brown', label: 'Brown', prompt: 'rich brown skin tone', swatch: '#5C3A20' },
      { id: 'deep', label: 'Deep', prompt: 'deep brown skin tone', swatch: '#3B2412' },
    ],
  },

  {
    id: 'eyeColor',
    label: 'Eye Color',
    icon: 'Eye',
    kind: 'swatch',
    required: false,
    columns: 6,
    options: [
      { id: 'brown', label: 'Brown', prompt: 'brown eyes', swatch: '#6B3F1D' },
      { id: 'hazel', label: 'Hazel', prompt: 'hazel eyes', swatch: '#8E7141' },
      { id: 'amber', label: 'Amber', prompt: 'amber eyes', swatch: '#B07A2C' },
      { id: 'green', label: 'Green', prompt: 'green eyes', swatch: '#3F6B45' },
      { id: 'blue', label: 'Blue', prompt: 'blue eyes', swatch: '#3A6B91' },
      { id: 'gray', label: 'Gray', prompt: 'gray eyes', swatch: '#7A8A93' },
      { id: 'violet', label: 'Violet', prompt: 'unusual violet eyes', swatch: '#6E4F86' },
      { id: 'heterochromia', label: 'Two-tone', prompt: 'heterochromia, two different eye colors', swatch: 'linear-gradient(90deg, #3A6B91 50%, #6B3F1D 50%)' },
    ],
  },

  {
    id: 'age',
    label: 'Age Range',
    icon: 'Clock',
    kind: 'photo',
    required: true,
    columns: 3,
    options: [
      { id: 'young_adult', label: 'Young Adult', prompt: 'in their early 20s, fresh and youthful', thumbnail: ageYoungThumb },
      { id: 'adult', label: 'Adult', prompt: 'in their mid 30s, confident and polished', thumbnail: ageAdultThumb },
      { id: 'mature', label: 'Mature', prompt: 'in their 50s, distinguished and graceful', thumbnail: ageMatureThumb },
    ],
  },

  {
    id: 'bodyType',
    label: 'Body Type',
    icon: 'PersonStanding',
    kind: 'icon',
    required: true,
    columns: 3,
    options: [
      { id: 'slim', label: 'Slim', prompt: 'slim build', icon: 'Slash' },
      { id: 'athletic', label: 'Athletic', prompt: 'athletic toned build', icon: 'Activity' },
      { id: 'average', label: 'Average', prompt: 'average build', icon: 'User' },
      { id: 'curvy', label: 'Curvy', prompt: 'curvy hourglass build', icon: 'Heart' },
      { id: 'plus_size', label: 'Plus-size', prompt: 'plus-size build', icon: 'Circle' },
      { id: 'muscular', label: 'Muscular', prompt: 'visibly muscular build', icon: 'Dumbbell' },
    ],
  },

  {
    id: 'hairType',
    label: 'Hair Type',
    icon: 'Scissors',
    kind: 'photo',
    required: true,
    columns: 3,
    options: [
      { id: 'straight', label: 'Straight', prompt: 'straight hair', thumbnail: hairStraight },
      { id: 'wavy', label: 'Wavy', prompt: 'soft wavy hair', thumbnail: hairWavy },
      { id: 'curly', label: 'Curly', prompt: 'curly hair', thumbnail: hairCurly },
      { id: 'coily', label: 'Coily', prompt: 'coily natural hair', thumbnail: hairCoily },
      { id: 'buzz', label: 'Buzz / Bald', prompt: 'buzz cut or bald', thumbnail: hairBuzz },
    ],
  },

  {
    id: 'hairLength',
    label: 'Hair Length',
    icon: 'Ruler',
    kind: 'icon',
    required: false,
    columns: 4,
    options: [
      { id: 'short', label: 'Short', prompt: 'short hair', icon: 'Minus' },
      { id: 'medium', label: 'Medium', prompt: 'medium-length hair', icon: 'AlignJustify' },
      { id: 'long', label: 'Long', prompt: 'long flowing hair', icon: 'AlignVerticalJustifyStart' },
      { id: 'extra_long', label: 'Extra long', prompt: 'extra long hair past the waist', icon: 'MoveVertical' },
    ],
  },

  {
    id: 'hairColor',
    label: 'Hair Color',
    icon: 'Droplet',
    kind: 'swatch',
    required: true,
    columns: 6,
    options: [
      { id: 'jet_black', label: 'Jet black', prompt: 'jet black hair', swatch: '#181512' },
      { id: 'dark_brown', label: 'Dark brown', prompt: 'dark brown hair', swatch: '#3B2519' },
      { id: 'brown', label: 'Brown', prompt: 'medium brown hair', swatch: '#6B4327' },
      { id: 'auburn', label: 'Auburn', prompt: 'auburn red-brown hair', swatch: '#8A3B22' },
      { id: 'red', label: 'Red / Ginger', prompt: 'natural red ginger hair', swatch: '#B5572A' },
      { id: 'blonde', label: 'Blonde', prompt: 'blonde hair', swatch: '#D9B16A' },
      { id: 'platinum', label: 'Platinum', prompt: 'platinum / silver-blonde hair', swatch: '#E6DFCB' },
      { id: 'gray', label: 'Gray / Silver', prompt: 'silver gray hair', swatch: '#9E9E9E' },
      { id: 'white', label: 'White', prompt: 'pure white hair', swatch: '#F2F2F2' },
      { id: 'pastel', label: 'Pastel pink', prompt: 'soft pastel pink hair', swatch: '#E8B6C9' },
      { id: 'electric_blue', label: 'Electric blue', prompt: 'electric blue dyed hair', swatch: '#3F6FA8' },
      { id: 'lavender', label: 'Lavender', prompt: 'lavender purple hair', swatch: '#A892C9' },
    ],
  },

  {
    id: 'tattoos',
    label: 'Tattoos',
    icon: 'Sparkles',
    kind: 'icon',
    required: false,
    columns: 4,
    options: [
      { id: 'none', label: 'None', prompt: 'no visible tattoos', icon: 'Ban' },
      { id: 'subtle', label: 'Subtle', prompt: 'a few subtle small tattoos', icon: 'Asterisk' },
      { id: 'moderate', label: 'Moderate', prompt: 'noticeable arm or chest tattoos', icon: 'Stars' },
      { id: 'full_sleeve', label: 'Full sleeve', prompt: 'full sleeve tattoos', icon: 'Layers' },
    ],
  },

  {
    id: 'piercings',
    label: 'Piercings',
    icon: 'Gem',
    kind: 'icon',
    required: false,
    columns: 4,
    options: [
      { id: 'none', label: 'None', prompt: 'no piercings', icon: 'Ban' },
      { id: 'ears', label: 'Ear studs', prompt: 'simple earring studs', icon: 'Circle' },
      { id: 'septum', label: 'Septum', prompt: 'septum nose piercing', icon: 'Triangle' },
      { id: 'brow', label: 'Eyebrow', prompt: 'eyebrow piercing', icon: 'ArrowUpRight' },
    ],
  },

  {
    id: 'extras',
    label: 'Extras',
    icon: 'Stars',
    kind: 'icon',
    required: false,
    allowMultiple: true,
    columns: 4,
    options: [
      { id: 'freckles', label: 'Freckles', prompt: 'natural freckles across the cheeks and nose', icon: 'Sparkle' },
      { id: 'glasses', label: 'Glasses', prompt: 'wearing thin-frame modern glasses', icon: 'Glasses' },
      { id: 'beard', label: 'Beard', prompt: 'well-groomed short beard', icon: 'Beer' },
      { id: 'mustache', label: 'Mustache', prompt: 'well-groomed mustache', icon: 'Smile' },
      { id: 'dimples', label: 'Dimples', prompt: 'soft dimples when smiling', icon: 'CircleDot' },
      { id: 'beauty_mark', label: 'Beauty mark', prompt: 'a small beauty mark near the lips', icon: 'Dot' },
    ],
  },

  {
    id: 'outfit',
    label: 'Outfit Vibe',
    icon: 'Shirt',
    kind: 'photo',
    required: true,
    columns: 3,
    options: [
      { id: 'casual', label: 'Casual', prompt: 'casual everyday outfit, simple t-shirt and jeans', thumbnail: outfitCasual },
      { id: 'streetwear', label: 'Streetwear', prompt: 'modern streetwear, oversized hoodie and chain', thumbnail: outfitStreetwear },
      { id: 'formal', label: 'Formal', prompt: 'sharp formal outfit, tailored blazer or dress', thumbnail: outfitFormal },
      { id: 'athletic', label: 'Athletic', prompt: 'athletic activewear, sleek athleisure', thumbnail: outfitAthletic },
      { id: 'academia', label: 'Academia', prompt: 'soft academia look, knit sweater and collared shirt', thumbnail: outfitYAcademia },
      { id: 'cozy', label: 'Cozy', prompt: 'cozy oversized sweater and beanie, lounge vibe', thumbnail: outfitCozy },
    ],
  },
];

/**
 * Build a deterministic, prompt-safe summary string from a selections object.
 * The selections shape is { sectionId: optionId | optionId[] }.
 */
export function buildPromptFromSelections(selections) {
  const parts = [];
  for (const section of AVATAR_SECTIONS) {
    const value = selections[section.id];
    if (!value) continue;
    const ids = Array.isArray(value) ? value : [value];
    if (!ids.length) continue;
    const fragments = ids
      .map((id) => section.options.find((opt) => opt.id === id))
      .filter(Boolean)
      .map((opt) => opt.prompt);
    if (!fragments.length) continue;
    parts.push(fragments.join(', '));
  }
  return parts.join('. ');
}

/** Validate that all required sections have a selection. Returns missing labels. */
export function getMissingRequired(selections) {
  const missing = [];
  for (const section of AVATAR_SECTIONS) {
    if (!section.required) continue;
    const value = selections[section.id];
    if (!value || (Array.isArray(value) && !value.length)) {
      missing.push(section.label);
    }
  }
  return missing;
}

/** Pick a random complete configuration. */
export function randomizeSelections() {
  const next = {};
  for (const section of AVATAR_SECTIONS) {
    const opts = section.options;
    if (!opts.length) continue;
    if (section.allowMultiple) {
      const sampleCount = Math.floor(Math.random() * 2);
      const shuffled = [...opts].sort(() => Math.random() - 0.5);
      next[section.id] = shuffled.slice(0, sampleCount).map((o) => o.id);
    } else {
      next[section.id] = opts[Math.floor(Math.random() * opts.length)].id;
    }
  }
  return next;
}

/** Find an option's display info by section/id. */
export function findOption(sectionId, optionId) {
  const section = AVATAR_SECTIONS.find((s) => s.id === sectionId);
  if (!section) return null;
  return section.options.find((o) => o.id === optionId) || null;
}
