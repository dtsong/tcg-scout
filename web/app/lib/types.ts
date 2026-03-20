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
  trend?: "up" | "down" | "new" | "stable";
  trend_delta?: number;
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

export interface DecklistCard {
  card_name: string;
  count: number;
  category?: "Pokemon" | "Trainer" | "Energy";
}

export interface ArchetypeResult {
  tournament_name: string;
  tournament_url?: string;
  date: string;
  standing: number;
  player_name: string;
  decklist?: DecklistCard[];
}

export interface ArchetypeRadar {
  meta_share: number;
  weighted_share: number;
  consistency: number;
  ceiling: number;
  popularity: number;
  core_density: number;
}

export interface TopPerformerCard extends ArchetypeCard {
  delta_vs_field: number;
}

export interface CardAnalysisArchetype {
  archetype: string;
  slug: string;
  tier: Tier;
  delta_vs_field: number;
  top4_inclusion_pct: number;
  field_inclusion_pct: number;
  avg_copies: number;
  top4_sample_size: number;
}

export interface CardAnalysisEntry {
  card_name: string;
  category: "Pokemon" | "Trainer" | "Energy";
  archetypes: CardAnalysisArchetype[];
  avg_delta: number;
  archetype_count: number;
  max_delta: number;
  best_archetype: string;
}

export interface CardAnalysisData {
  cards: CardAnalysisEntry[];
  generated_at: string;
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
  evolution?: EvolutionEvent[];
  variants?: ArchetypeVariant[];
  weekly_shares?: { week: string; meta_share: number; deck_count: number }[];
  top4_card_stats?: TopPerformerCard[];
  top4_sample_size?: number;
  top4_low_sample?: boolean;
}

export interface ArchetypeVariant {
  name: string;
  deck_count: number;
  pct: number;
}

export interface MatchupMatrixData {
  archetypes: string[];
  matrix: number[][];
  sample_sizes: number[][];
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

export interface CardSummary {
  card_name: string;
  card_slug: string;
  card_id: string | null;
  set_code: string | null;
  set_number: string | null;
  image_url: string | null;
  category: "Pokemon" | "Trainer" | "Energy";
  rarity: string | null;
  usage_pct: number;
  avg_copies: number;
  top_archetype: string | null;
  trend_direction: "surging" | "stable" | "declining";
}

export interface CardArchetype {
  name: string;
  slug: string;
  usage_count: number;
  avg_copies: number;
  tier: Tier;
}

export interface SynergyPartner {
  card_name: string;
  support: number;
  lift: number;
  jaccard: number;
  weighted_score: number;
}

export interface SynergyPair {
  card_a: string;
  card_b: string;
  support: number;
  lift: number;
  jaccard: number;
  weighted_score: number;
  archetypes?: string[];
}

export interface CardDetail extends CardSummary {
  total_appearances: number;
  unique_archetypes: number;
  weighted_score: number;
  win_rate_proxy: number;
  copy_distribution: { copies: number; count: number }[];
  archetypes: CardArchetype[];
  weekly_usage: { week: string; usage_pct: number; avg_copies: number }[];
  synergy_partners?: SynergyPartner[];
}

export interface EvolutionCard {
  card: string;
  from_pct: number;
  to_pct: number;
}

export interface EvolutionEvent {
  week: string;
  adopted: EvolutionCard[];
  dropped: EvolutionCard[];
}

export interface MetaEvolutionMovement {
  card: string;
  archetype: string;
  direction: "adopted" | "dropped";
  from_pct: number;
  to_pct: number;
  delta: number;
  week: string;
}

export interface OverlapMatrixData {
  archetypes: {
    archetype: string;
    slug: string;
    sprite_filenames?: string[];
    weighted_share: number;
  }[];
  matrix: number[][];
}

export interface CLDecklistCard {
  card_name_jp: string;
  card_name_en: string | null;
  count: number;
  category: "Pokemon" | "Trainer" | "Energy";
  image_url: string | null;
}

interface CLPlacementBase {
  standing: number;
  player_name: string;
  region: string;
  deck_code: string;
  decklist: CLDecklistCard[];
}

export type CLPlacement = CLPlacementBase &
  (
    | { archetype: string; tier: Tier | null; sprite_filenames: string[] }
    | { archetype: null; tier: null; sprite_filenames: null }
  );

export interface CLArchetypeSummary {
  archetype: string;
  count: number;
  sprite_filenames: string[];
}

export interface CLDivision {
  event_id: number;
  event_name: string;
  division: string;
  date: string;
  archetype_summary?: CLArchetypeSummary[];
  placements: CLPlacement[];
}

export interface TechForecastCard {
  card_name: string;
  current_adoption_pct: number;
  current_avg_copies: number;
  trend_direction: "rising" | "falling" | "stable" | "new";
  trend_delta: number;
  weekly_data: Array<{
    week: string;
    adoption_pct: number;
    avg_copies: number;
    deck_count: number;
    total_decks: number;
  }>;
  top_archetypes: Array<{
    archetype: string;
    inclusion_pct: number;
    avg_copies: number;
  }>;
}

export interface TechForecast {
  generated_at: string;
  cards: TechForecastCard[];
}
