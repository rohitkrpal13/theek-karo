/**
 * Theek Karo design tokens (Phase 4) — single source of truth consumed by
 * Tailwind v4 `@theme` (globals.css), inline styles and JS logic.
 *
 * Brand intent: improvement, trust, civic participation, transparency,
 * progress, inclusivity. Neutral palette keeps it apolitical.
 */

export const colors = {
  // primary: deep civic green — "improvement in progress"
  primary: "#157F4A",
  primaryStrong: "#0E6B3D",
  primarySoft: "#E7F4EC",
  // secondary: warm amber used sparingly for highlights
  secondary: "#C98A16",
  secondarySoft: "#FBF3E0",
  // neutrals (surface-first)
  background: { light: "#F7F8F6", dark: "#121512" },
  surface: { light: "#FFFFFF", dark: "#1B1F1B" },
  surfaceRaised: { light: "#FFFFFF", dark: "#232823" },
  text: { light: "#171A17", dark: "#EDF0EA" },
  textMuted: { light: "#5A6158", dark: "#A9B0A5" },
  border: { light: "#DFE3DB", dark: "#333A33" },
  // semantic
  success: "#0E7A43",
  warning: "#B7791F",
  error: "#B3261E",
  info: "#1D6FA3",
  // severity (always paired with icon+text, never color alone)
  severity: {
    low: "#0E7A43",
    medium: "#B7791F",
    high: "#D05B12",
    critical: "#B3261E",
  },
  // trust tiers (provenance)
  tiers: {
    official: "#1D4ED8",
    verified: "#0E7A43",
    citizen: "#7C5BB8",
    ai: "#64748B",
    unverified: "#9AA0A6",
  },
  focus: "#1D4ED8",
  scrim: "rgba(10,12,10,0.5)",
};

export const spacing = {
  xxs: 4, xs: 8, sm: 12, md: 16, lg: 24, xl: 32, xxl: 48, xxxl: 64,
};

export const radius = { sm: 6, md: 10, lg: 14, xl: 20, pill: 999 };

export const elevation = {
  sm: "0 1px 2px rgba(16,20,16,0.06)",
  md: "0 2px 8px rgba(16,20,16,0.08)",
  lg: "0 8px 24px rgba(16,20,16,0.12)",
  overlay: "0 16px 48px rgba(16,20,16,0.18)",
};

export const breakpoints = {
  mobile: 0,   // default base
  tablet: 640,
  laptop: 1024,
  desktop: 1280,
  largeDesktop: 1536,
};

/** Typographic scale (px). */
export const typeScale = {
  display: 34,
  h1: 28,
  h2: 22,
  h3: 18,
  body: 15,
  bodySmall: 13,
  caption: 12,
  label: 12,
  button: 14,
  stat: 26,
};

/**
 * Indian script font strategy. No single family serves every script well:
 * per-script system font stacks with Latin fallback; Urdu is RTL.
 * Families are deliberately system-first (zero network cost, native hinting),
 * with branded webfont as a future enhancement slot.
 */
export const scriptFonts: Record<string, { fontFamily: string; direction: "ltr" | "rtl" }> = {
  latin: { fontFamily: "'Inter','system-ui','Segoe UI',Arial,sans-serif", direction: "ltr" },
  devanagari: {
    fontFamily: "'Noto Sans Devanagari','Mukta','Mangal','Nirmala UI','system-ui',sans-serif",
    direction: "ltr",
  },
  bengali: {
    fontFamily: "'Noto Sans Bengali','Hind Siliguri','Vrinda','Nirmala UI','system-ui',sans-serif",
    direction: "ltr",
  },
  tamil: {
    fontFamily: "'Noto Sans Tamil','Latha','Nirmala UI','system-ui',sans-serif",
    direction: "ltr",
  },
  telugu: {
    fontFamily: "'Noto Sans Telugu','Gautami','Nirmala UI','system-ui',sans-serif",
    direction: "ltr",
  },
  kannada: {
    fontFamily: "'Noto Sans Kannada','Tunga','Nirmala UI','system-ui',sans-serif",
    direction: "ltr",
  },
  malayalam: {
    fontFamily: "'Noto Sans Malayalam','Kartika','Nirmala UI','system-ui',sans-serif",
    direction: "ltr",
  },
  gujarati: {
    fontFamily: "'Noto Sans Gujarati','Shruti','Nirmala UI','system-ui',sans-serif",
    direction: "ltr",
  },
  marathi: {
    fontFamily: "'Noto Sans Devanagari','Mukta','Mangal','Nirmala UI','system-ui',sans-serif",
    direction: "ltr",
  },
  gurmukhi: {
    fontFamily: "'Noto Sans Gurmukhi','Raavi','Nirmala UI','system-ui',sans-serif",
    direction: "ltr",
  },
  odia: {
    fontFamily: "'Noto Sans Oriya','Kalinga','Nirmala UI','system-ui',sans-serif",
    direction: "ltr",
  },
  assamese: {
    fontFamily: "'Noto Sans Bengali','Hind Siliguri','Nirmala UI','system-ui',sans-serif",
    direction: "ltr",
  },
  urdu: { fontFamily: "'Noto Nastaliq Urdu','Urdu Typesetting','system-ui',sans-serif", direction: "rtl" },
  maithili: {
    fontFamily: "'Noto Sans Devanagari','Mangal','Nirmala UI','system-ui',sans-serif",
    direction: "ltr",
  },
};

/** 15-language registry (PRD §11): script family + native name. */
export const languages: Array<{
  code: string;
  native: string;
  english: string;
  script: keyof typeof scriptFonts;
}> = [
  { code: "en", native: "English", english: "English", script: "latin" },
  { code: "hi", native: "हिन्दी", english: "Hindi", script: "devanagari" },
  { code: "bn", native: "বাংলা", english: "Bengali", script: "bengali" },
  { code: "te", native: "తెలుగు", english: "Telugu", script: "telugu" },
  { code: "mr", native: "मराठी", english: "Marathi", script: "marathi" },
  { code: "ta", native: "தமிழ்", english: "Tamil", script: "tamil" },
  { code: "gu", native: "ગુજરાતી", english: "Gujarati", script: "gujarati" },
  { code: "kn", native: "ಕನ್ನಡ", english: "Kannada", script: "kannada" },
  { code: "ml", native: "മലയാളം", english: "Malayalam", script: "malayalam" },
  { code: "or", native: "ଓଡ଼ିଆ", english: "Odia", script: "odia" },
  { code: "pa", native: "ਪੰਜਾਬੀ", english: "Punjabi", script: "gurmukhi" },
  { code: "as", native: "অসমীয়া", english: "Assamese", script: "assamese" },
  { code: "ur", native: "اردو", english: "Urdu", script: "urdu" },
  { code: "mai", native: "मैथिली", english: "Maithili", script: "maithili" },
  { code: "sd", native: "سنڌي", english: "Sindhi", script: "urdu" },
];

/** Component-state tints map (colors are never the sole status signal). */
export const stateTints = {
  default: { bg: "surface", text: "text" },
  hover: { bg: "#F0F3EE", text: "#171A17" },
  active: { bg: "#E7F4EC", text: "#0E6B3D" },
  disabled: { bg: "#EDF0EA", text: "#9AA0A6" },
};

/** Motion durations; `prefers-reduced-motion` zeroes these in CSS. */
export const motion = {
  fast: 120,
  base: 200,
  slow: 320,
  reduced: 0,
};

export const tokens = {
  colors,
  spacing,
  radius,
  elevation,
  breakpoints,
  typeScale,
  scriptFonts,
  languages,
  stateTints,
  motion,
};

export default tokens;