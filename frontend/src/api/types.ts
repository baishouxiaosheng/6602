export type GeneId =
  | "challenge"
  | "strategy"
  | "pace"
  | "progression"
  | "exploration"
  | "creation"
  | "narrative"
  | "immersion"
  | "social";

export type CanonicalGenre =
  | "action"
  | "adventure"
  | "rpg"
  | "strategy"
  | "simulation"
  | "casual";

export type Track = "same_track" | "cross_track";

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  environment: string;
}

export interface ApiError {
  ok: false;
  code: string;
  message: string;
  retryable: boolean;
  details: Record<string, unknown>;
}

export interface QuestionnaireGene {
  gene_id: GeneId;
  label: string;
  description: string;
}

export interface QuestionnaireDefinition {
  version: string;
  genes: QuestionnaireGene[];
  scale: Record<string, string>;
  canonical_genres: CanonicalGenre[];
  max_important_genes: number;
  max_familiar_genres: number;
}

export interface FamiliarGenre {
  genre: CanonicalGenre;
  rank: number;
  weight: number;
}

export interface HardFilters {
  platforms: string[];
  required_language: string;
  max_price_usd_cents: number | null;
  social_requirement: "any" | "no_mandatory_multiplayer" | "multiplayer_required";
  controller_required: boolean;
  exclude_owned: boolean;
}

export interface QuestionnaireSubmission {
  display_name: string;
  gene_targets: Record<GeneId, number>;
  important_genes: GeneId[];
  familiar_genres: FamiliarGenre[];
  hard_filters: HardFilters;
  additional_preferences: string;
}

export interface GeneContribution {
  gene_id: GeneId;
  questionnaire_target: number;
  library_adjustment: number;
  text_adjustment: number;
  final_target: number;
  weight: number;
  sources: string[];
}

export interface PlayerProfile {
  profile_id: string;
  display_name: string;
  gene_contributions: GeneContribution[];
  familiar_genres: FamiliarGenre[];
  hard_filters: HardFilters;
  soft_descriptor_preferences: string[];
  owned_appids: number[];
  free_text: string;
  warnings: string[];
}

export interface PreferenceParseResult {
  gene_adjustments: Partial<Record<GeneId, number>>;
  soft_descriptor_preferences: string[];
  potential_hard_constraints: string[];
  unsupported_requests: string[];
}

export interface OwnedGame {
  appid: number;
  name: string | null;
  playtime_minutes: number;
  is_favorite: boolean;
  liked_aspects: string[];
  participates_in_profile: boolean;
}

export interface SteamImportPreview {
  preview_token: string;
  steam_id_masked: string;
  games: OwnedGame[];
  warnings: string[];
}

export interface JobError {
  code: string;
  message: string;
  retryable: boolean;
}

export interface Job {
  job_id: string;
  job_type: "steam_import" | "catalog_batch" | "recommendation";
  status: "queued" | "running" | "completed" | "failed";
  current_step: string;
  processed_items: number;
  total_items: number;
  result_ref: string | null;
  error: JobError | null;
}

export interface RecommendationItem {
  appid: number;
  name: string;
  track: Track;
  ai_rank: number;
  compatibility_score: number;
  ranking_reason: string;
  matched_gene_ids: GeneId[];
  evidence_ids: string[];
  caution: string | null;
}

export interface RecommendationRun {
  run_id: string;
  profile_id: string;
  status: "running" | "ok" | "closest_only" | "no_match" | "failed";
  same_track: RecommendationItem[];
  cross_track: RecommendationItem[];
  message: string | null;
  created_at: string;
}
