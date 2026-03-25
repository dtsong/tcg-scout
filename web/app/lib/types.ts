export type Tier = "S" | "A" | "B" | "C" | "Rogue";

export type TimeWindow = "all" | "7d" | "30d" | "custom";

export interface FormatInfo {
  slug: string;
  name: string;
  name_en: string;
  description: string;
  dataset_start: string;
  dataset_end: string;
  status: "active" | "frozen" | "upcoming";
  tournament_count?: number;
  deck_count?: number;
  generated_at?: string;
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
  set_code?: string | null;
  set_number?: string | null;
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
  confidence?: number;
}

export interface CardAnalysisEntry {
  card_name: string;
  category: "Pokemon" | "Trainer" | "Energy";
  archetypes: CardAnalysisArchetype[];
  avg_delta: number;
  weighted_impact?: number;
  confidence?: number;
  archetype_count: number;
  max_delta: number;
  best_archetype: string;
}

export interface CardAnalysisData {
  cards: CardAnalysisEntry[];
  generated_at: string;
}

export interface CrossMetaStaple {
  card_name: string;
  weighted_impact: number;
  tiered_archetype_count: number;
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
  /** Always present in exports after 2026-03-21; absent in legacy bare-array format. */
  archetype_slug?: string;
  /** Always present in exports after 2026-03-21; absent in legacy bare-array format. */
  deck_count?: number;
  direction: "adopted" | "dropped";
  from_pct: number;
  to_pct: number;
  delta: number;
  week: string;
}

/**
 * Format-wide card adoption/drop movements.
 * `highlights` is the top 5 movements by recency+magnitude (subset of `movements`).
 * `movements` is the complete list, sorted by week DESC then delta DESC.
 */
export interface MetaEvolutionData {
  highlights: MetaEvolutionMovement[];
  movements: MetaEvolutionMovement[];
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

export interface ReportSection {
  id: string;
  title: string;
  content: string;
  highlights?: string[];
}

export interface MetaReport {
  format: string;
  generated_at: string;
  data_hash: string;
  sections: ReportSection[];
}

// --- Optimal 60 types ---

export type Optimal60Consensus =
  | "core"
  | "flex-core"
  | "flex"
  | "tech"
  | "cl-signal";

export interface Optimal60Card {
  card_name: string;
  count: number;
  category: "Pokemon" | "Trainer" | "Energy";
  consensus: Optimal60Consensus;
  blended_inclusion_pct: number;
  cl_inclusion_pct: number;
  meta_inclusion_pct: number;
  inclusion_delta: number;
  blended_avg_copies: number;
  cl_avg_copies: number;
  meta_avg_copies: number;
  insight: string | null;
  set_code?: string | null;
  set_number?: string | null;
}

export interface Optimal60Detail {
  archetype: string;
  slug: string;
  format: string;
  generated_at: string;
  tier: Tier;
  meta_share: number;
  weighted_share: number;
  sprite_filenames: string[];
  quality_score: number;
  cl_deck_count: number;
  city_league_deck_count: number;
  has_cl_data: boolean;
  cl_placements: number[];
  cl_best_finish: number | null;
  total_pokemon: number;
  total_trainer: number;
  total_energy: number;
  core_lock_rate: number;
  innovation_index: number;
  cards: Optimal60Card[];
  narrative: Record<string, string>;
}

export interface Optimal60IndexEntry {
  archetype: string;
  slug: string;
  tier: Tier;
  meta_share: number;
  sprite_filenames: string[];
  quality_score: number;
  cl_deck_count: number;
  city_league_deck_count: number;
  has_cl_data: boolean;
  cl_placements: number[];
  cl_best_finish: number | null;
  innovation_index: number;
  core_lock_rate: number;
}

export interface Optimal60Index {
  format: string;
  generated_at: string;
  cl_event: string | null;
  cl_player_count: number;
  format_note: string;
  archetypes: Optimal60IndexEntry[];
}

export interface ConsensusCard {
  card_name: string;
  count: number;
  category: "Pokemon" | "Trainer" | "Energy";
  weighted_inclusion_pct: number;
  weighted_avg_copies: number;
  confidence: number;
  consensus: "core" | "common" | "tech";
  set_code?: string | null;
  set_number?: string | null;
}

export interface TechEvolutionCard {
  card_name: string;
  category: "Pokemon" | "Trainer" | "Energy";
  timeline: number[];
  copies_timeline: number[];
  trend: "adopted" | "dropped" | "shifted" | "stable";
  total_delta: number;
}

export interface NotableTech {
  card_name: string;
  event: "appeared" | "disappeared" | "surged" | "declined";
  week: string;
  from_pct: number;
  to_pct: number;
}

export interface PlacementBracket {
  bracket: "1st" | "2nd" | "3rd-4th" | "5th-8th" | "9th-16th" | "17th+";
  count: number;
  pct: number;
}

export interface ArchetypeReport {
  archetype: string;
  slug: string;
  format: string;
  generated_at: string;
  tier: Tier;
  meta_share: number;
  weighted_share: number;
  deck_count: number;
  best_placement: number;
  sprite_filenames: string[];
  consensus_60: {
    quality_score: number;
    total_pokemon: number;
    total_trainer: number;
    total_energy: number;
    cards: ConsensusCard[];
  } | null;
  tech_evolution: {
    weeks: string[];
    cards: TechEvolutionCard[];
  } | null;
  notable_techs: NotableTech[];
  placement_distribution: PlacementBracket[];
  tournament_count: number;
  /** Reserved for future use -- currently always empty ({}) from the Python export. */
  narrative: {
    summary?: string;
    consensus_rationale?: string;
    tech_evolution_analysis?: string;
  };
}

// --- Card Decklist Drill-down types ---

export interface CardDecklistResult {
  archetype: string;
  archetype_slug: string;
  tournament_name: string;
  date: string;
  standing: number;
  copies: number;
  decklist_url: string | null;
}

export interface CardDecklistData {
  card_name: string;
  top4_results: CardDecklistResult[];
}

// --- City League Tournament Index ---

export interface TournamentFinisher {
  standing: number;
  player_name: string;
  archetype: string;
  slug: string;
  sprite_filenames?: string[];
  tier?: Tier;
}

export interface ArchetypeDistEntry {
  archetype: string;
  slug: string;
  count: number;
  share: number;
  sprite_filenames?: string[];
}

export interface CityLeagueTournament {
  id: string;
  name: string;
  date: string;
  prefecture?: string | null;
  player_count?: number | null;
  source_url?: string | null;
  top_finishers: TournamentFinisher[];
  archetype_distribution: ArchetypeDistEntry[];
}

export interface RisingArchetype {
  archetype: string;
  slug: string;
  trend: string;
  trend_delta: number;
  sprite_filenames?: string[];
  tier?: Tier;
}

export interface RecentWinner {
  archetype: string;
  slug: string;
  sprite_filenames?: string[];
  date: string;
  tournament_name: string;
  player_name?: string;
}

export interface CityLeagueIndex {
  generated_at: string;
  tournament_count: number;
  deck_count: number;
  date_range: { start: string; end: string };
  rising_archetypes: RisingArchetype[];
  recent_winners: RecentWinner[];
  tournaments: CityLeagueTournament[];
}
