import type {
  ApiError,
  CatalogGame,
  HealthResponse,
  Job,
  PlayerProfile,
  PreferenceParseResult,
  QuestionnaireDefinition,
  QuestionnaireSubmission,
  RecommendationRun,
  SteamImportPreview,
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export class ApiClientError extends Error {
  readonly payload?: ApiError;

  constructor(message: string, payload?: ApiError) {
    super(message);
    this.name = "ApiClientError";
    this.payload = payload;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!response.ok) {
    let payload: ApiError | undefined;
    try {
      payload = (await response.json()) as ApiError;
    } catch {
      payload = undefined;
    }
    throw new ApiClientError(payload?.message ?? `Request failed (${response.status}).`, payload);
  }
  return (await response.json()) as T;
}

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return request<HealthResponse>("/api/health", { signal });
}

export function getQuestionnaire(signal?: AbortSignal): Promise<QuestionnaireDefinition> {
  return request<QuestionnaireDefinition>("/api/questionnaire", { signal });
}

export async function createProfile(
  submission: QuestionnaireSubmission,
): Promise<PlayerProfile> {
  const result = await request<{ profile: PlayerProfile }>("/api/profiles", {
    method: "POST",
    body: JSON.stringify(submission),
  });
  return result.profile;
}

export async function parsePreferences(
  profileId: string,
  text: string,
): Promise<PreferenceParseResult> {
  const result = await request<{ parsed_preferences: PreferenceParseResult }>(
    `/api/profiles/${profileId}/preferences/parse`,
    { method: "POST", body: JSON.stringify({ text }) },
  );
  return result.parsed_preferences;
}

export async function confirmPreferences(
  profileId: string,
  parsedPreferences: PreferenceParseResult,
  confirmedHardConstraints: string[],
): Promise<PlayerProfile> {
  const result = await request<{ profile: PlayerProfile }>(
    `/api/profiles/${profileId}/preferences/confirm`,
    {
      method: "PUT",
      body: JSON.stringify({
        parsed_preferences: parsedPreferences,
        confirmed_hard_constraints: confirmedHardConstraints,
      }),
    },
  );
  return result.profile;
}

export async function previewSteamImport(
  profileId: string,
  steamIdOrUrl: string,
): Promise<SteamImportPreview> {
  const result = await request<{ preview: SteamImportPreview }>(
    `/api/profiles/${profileId}/steam-import/preview`,
    {
      method: "POST",
      body: JSON.stringify({ steam_id_or_url: steamIdOrUrl, consent: true }),
    },
  );
  return result.preview;
}

export async function confirmSteamImport(
  profileId: string,
  previewToken: string,
  favoriteGames: Array<{ appid: number; liked_aspects: string[] }>,
): Promise<Job> {
  const result = await request<{ job: Job }>(
    `/api/profiles/${profileId}/steam-import/confirm`,
    {
      method: "POST",
      body: JSON.stringify({
        preview_token: previewToken,
        favorite_games: favoriteGames,
      }),
    },
  );
  return result.job;
}

export async function getProfile(profileId: string): Promise<PlayerProfile> {
  const result = await request<{ profile: PlayerProfile }>(`/api/profiles/${profileId}`);
  return result.profile;
}

export async function getJob(jobId: string): Promise<Job> {
  const result = await request<{ job: Job }>(`/api/jobs/${jobId}`);
  return result.job;
}

export async function pollJob(
  jobId: string,
  onUpdate?: (job: Job) => void,
  intervalMs = 2_000,
): Promise<Job> {
  for (;;) {
    const job = await getJob(jobId);
    onUpdate?.(job);
    if (job.status === "completed") return job;
    if (job.status === "failed") {
      throw new ApiClientError(job.error?.message ?? "Background operation failed.");
    }
    await new Promise((resolve) => window.setTimeout(resolve, intervalMs));
  }
}

export async function startRecommendation(
  profileId: string,
): Promise<{ runId: string; job: Job }> {
  const result = await request<{ run_id: string; job: Job }>("/api/recommendations", {
    method: "POST",
    body: JSON.stringify({
      profile_id: profileId,
      tracks: ["same_track", "cross_track"],
    }),
  });
  return { runId: result.run_id, job: result.job };
}

export async function getRecommendation(runId: string): Promise<RecommendationRun> {
  const result = await request<{ recommendation: RecommendationRun }>(
    `/api/recommendations/${runId}`,
  );
  return result.recommendation;
}

export async function getCatalogGame(appid: number, signal?: AbortSignal): Promise<CatalogGame> {
  const result = await request<{ game: CatalogGame }>(`/api/catalog/games/${appid}`, { signal });
  return result.game;
}
