export type Tier = "S" | "A" | "B" | "C" | "Rogue";
export type Urgency = "URGENT" | "HIGH" | "MODERATE";

export interface ArchetypeSummary {
  archetype: string;
  slug: string;
  meta_share: number;
  deck_count: number;
  best_placement: number;
  tier: Tier;
}

export interface MetaData {
  generated_at: string;
  tournament_count: number;
  deck_count: number;
  date_range: { start: string; end: string };
  rotation_date: string;
  tier_thresholds: Record<string, number>;
  archetypes: ArchetypeSummary[];
}

export interface BuylistCard {
  card_name: string;
  card_id: string | null;
  set_code: string | null;
  set_number: string | null;
  priority_score: number;
  urgency: Urgency;
  core_flex: "core" | "flex";
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

export interface TrendCard {
  card_name: string;
  early_count: number;
  late_count: number;
  early_pct: number;
  late_pct: number;
  delta: number;
}

export interface TrendsData {
  midpoint: string;
  early_decks: number;
  late_decks: number;
  cards: TrendCard[];
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
}

export interface ArchetypeDetail {
  archetype: string;
  slug: string;
  tier: Tier;
  meta_share: number;
  deck_count: number;
  best_placement: number;
  core_cards: ArchetypeCard[];
  all_cards: ArchetypeCard[];
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
