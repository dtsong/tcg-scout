export type Tier = "S" | "A" | "B" | "C" | "Rogue";

export type TimeWindow = "all" | "7d" | "30d" | "custom";

export interface FormatInfo {
  slug: string;
  name: string;
  name_en: string;
  description: string;
  dataset_start: string;
  dataset_end: string;
  status: "active" | "upcoming";
  tournament_count?: number;
  deck_count?: number;
}

export interface ArchetypeSummary {
  archetype: string;
  slug: string;
  meta_share: number;
  deck_count: number;
  best_placement: number;
  tier: Tier;
  weighted_share?: number;
  sprite_filenames?: string[];
}

export interface MetaData {
  generated_at: string;
  tournament_count: number;
  deck_count: number;
  date_range: { start: string; end: string };
  rotation_date: string;
  tier_thresholds: Record<string, number>;
  archetypes: ArchetypeSummary[];
  format?: { slug: string; name: string; name_en: string };
}

export interface BuylistCard {
  card_name: string;
  card_id: string | null;
  set_code: string | null;
  set_number: string | null;
  priority_score: number;
  core_flex: "core" | "flex";
  image_path?: string;
  archetypes: string[];
  avg_copies: number;
  inclusion_rate: number;
}

export interface StapleCard {
  card_name: string;
  deck_count: number;
  usage_pct: number;
  avg_copies: number;
}

export interface TrendCardArchetype {
  archetype: string;
  early_pct: number;
  late_pct: number;
  delta: number;
}

export interface TrendCard {
  card_name: string;
  early_count: number;
  late_count: number;
  early_pct: number;
  late_pct: number;
  delta: number;
  direction?: "surging" | "declining";
  archetypes?: TrendCardArchetype[];
}

export interface TrendsData {
  midpoint: string;
  early_decks: number;
  late_decks: number;
  surging: TrendCard[];
  declining: TrendCard[];
}

export interface WinningEdgeCard {
  card_name: string;
  field_pct: number;
  win_pct: number;
  edge: number;
  winner_decks: number;
  field_decks: number;
}

export interface AceSpec {
  card_name: string;
  deck_count: number;
  usage_pct: number;
}

export interface ArchetypeCard {
  card_name: string;
  inclusion_pct: number;
  avg_copies: number;
  decks_with: number;
  category?: "Pokemon" | "Trainer" | "Energy";
}

export interface ArchetypeResult {
  tournament_name: string;
  date: string;
  standing: number;
  player_name: string;
}

export interface ArchetypeRadar {
  meta_share: number;
  weighted_share: number;
  consistency: number;
  ceiling: number;
  popularity: number;
  core_density: number;
}

export interface ArchetypeDetail {
  archetype: string;
  slug: string;
  tier: Tier;
  meta_share: number;
  weighted_share?: number;
  deck_count: number;
  best_placement: number;
  sprite_filenames?: string[];
  core_cards: ArchetypeCard[];
  all_cards: ArchetypeCard[];
  results?: ArchetypeResult[];
  radar?: ArchetypeRadar;
}

export interface TimelineWeek {
  week: string;
  tournament_count: number;
  deck_count: number;
  archetypes: Record<string, number>;
}

export interface TimelineData {
  weeks: TimelineWeek[];
  archetype_order: string[];
}

export interface CLDecklistCard {
  card_name_jp: string;
  card_name_en: string | null;
  count: number;
  category: string;
}

export interface CLPlacement {
  standing: number;
  player_name: string;
  region: string;
  deck_code: string;
  decklist: CLDecklistCard[];
}

export interface CLDivision {
  event_id: number;
  event_name: string;
  division: string;
  date: string;
  placements: CLPlacement[];
}
