import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { GeneId, PlayerProfile, QuestionnaireDefinition } from "./api/types";
import App from "./App";

const geneIds: GeneId[] = [
  "challenge",
  "strategy",
  "pace",
  "progression",
  "exploration",
  "creation",
  "narrative",
  "immersion",
  "social",
];

const questionnaire: QuestionnaireDefinition = {
  version: "v1",
  genes: geneIds.map((geneId) => ({
    gene_id: geneId,
    label: geneId[0].toUpperCase() + geneId.slice(1),
    description: `${geneId} preference`,
  })),
  scale: { "0": "None", "1": "Low", "2": "Medium", "3": "High", "4": "Core" },
  canonical_genres: ["action", "adventure", "rpg", "strategy", "simulation", "casual"],
  max_important_genes: 3,
  max_familiar_genres: 3,
};

const profile: PlayerProfile = {
  profile_id: "p_test",
  display_name: "Demo Player",
  gene_contributions: geneIds.map((geneId) => ({
    gene_id: geneId,
    questionnaire_target: 2,
    library_adjustment: 0,
    text_adjustment: geneId === "pace" ? -1 : 0,
    final_target: geneId === "pace" ? 1 : 2,
    weight: geneId === "challenge" ? 2 : 1,
    sources: ["questionnaire"],
  })),
  familiar_genres: [{ genre: "rpg", rank: 1, weight: 3 }],
  hard_filters: {
    platforms: ["windows"],
    required_language: "english",
    max_price_usd_cents: null,
    social_requirement: "any",
    controller_required: false,
    exclude_owned: true,
  },
  soft_descriptor_preferences: [],
  owned_appids: [],
  free_text: "",
  warnings: [],
};

const health = {
  status: "ok",
  service: "Game Gene Agent API",
  version: "1.3.0",
  environment: "test",
};

function jsonResponse(data: unknown, ok = true) {
  return Promise.resolve({ ok, status: ok ? 200 : 400, json: async () => data });
}

function baseFetch(extra?: (url: string, init?: RequestInit) => unknown) {
  return vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith("/api/health")) return jsonResponse(health);
    if (url.endsWith("/api/questionnaire")) return jsonResponse(questionnaire);
    const result = extra?.(url, init);
    if (result) return result;
    throw new Error(`Unexpected request: ${init?.method ?? "GET"} ${url}`);
  });
}

describe("Game Gene workflow", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("loads the backend and nine-gene questionnaire", async () => {
    vi.stubGlobal("fetch", baseFetch());

    render(<App />);

    expect(await screen.findByText("Backend connected")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "What kind of experience do you want?" })).toBeInTheDocument();
    expect(screen.getAllByRole("slider")).toHaveLength(9);
  });

  it("creates a questionnaire-only profile and allows Steam import to be skipped", async () => {
    vi.stubGlobal("fetch", baseFetch((url, init) => {
      if (url.endsWith("/api/profiles") && init?.method === "POST") {
        return jsonResponse({ ok: true, profile });
      }
      return undefined;
    }));
    render(<App />);

    fireEvent.change(await screen.findByLabelText("Display name"), { target: { value: "Demo Player" } });
    fireEvent.click(screen.getByRole("button", { name: "Build player profile" }));

    expect(await screen.findByRole("heading", { name: "Import your public Steam library" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Skip Steam import" }));
    expect(await screen.findByRole("heading", { name: "Demo Player's game-gene profile" })).toBeInTheDocument();
  });

  it("requires confirmation of AI-suggested hard constraints", async () => {
    const controllerProfile = {
      ...profile,
      hard_filters: { ...profile.hard_filters, controller_required: true },
      soft_descriptor_preferences: ["pixel_graphics"],
    };
    vi.stubGlobal("fetch", baseFetch((url, init) => {
      if (url.endsWith("/api/profiles") && init?.method === "POST") {
        return jsonResponse({ ok: true, profile });
      }
      if (url.endsWith("/preferences/parse")) {
        return jsonResponse({
          ok: true,
          parsed_preferences: {
            gene_adjustments: { pace: -1 },
            soft_descriptor_preferences: ["pixel_graphics"],
            potential_hard_constraints: ["controller_required"],
            unsupported_requests: [],
          },
        });
      }
      if (url.endsWith("/preferences/confirm")) {
        return jsonResponse({ ok: true, profile: controllerProfile });
      }
      return undefined;
    }));
    render(<App />);

    fireEvent.change(await screen.findByLabelText("Display name"), { target: { value: "Demo Player" } });
    fireEvent.change(
      screen.getByPlaceholderText(/I want a calmer game/),
      { target: { value: "Pixel art and controller support." } },
    );
    fireEvent.click(screen.getByRole("button", { name: "Build player profile" }));

    expect(await screen.findByRole("heading", { name: "Review your free-text preferences" })).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Controller Required"));
    fireEvent.click(screen.getByRole("button", { name: "Confirm and continue" }));
    expect(await screen.findByRole("heading", { name: "Import your public Steam library" })).toBeInTheDocument();
  });

  it("renders a legitimate no-match result without filler games", async () => {
    vi.stubGlobal("fetch", baseFetch((url, init) => {
      if (url.endsWith("/api/profiles") && init?.method === "POST") return jsonResponse({ profile });
      if (url.endsWith("/api/recommendations") && init?.method === "POST") {
        return jsonResponse({ run_id: "r_1", job: { job_id: "j_1", status: "queued", current_step: "queued", processed_items: 0, total_items: 2, result_ref: null, error: null, job_type: "recommendation" } });
      }
      if (url.endsWith("/api/jobs/j_1")) {
        return jsonResponse({ job: { job_id: "j_1", status: "completed", current_step: "completed", processed_items: 2, total_items: 2, result_ref: "r_1", error: null, job_type: "recommendation" } });
      }
      if (url.endsWith("/api/recommendations/r_1")) {
        return jsonResponse({ recommendation: { run_id: "r_1", profile_id: "p_test", status: "no_match", same_track: [], cross_track: [], message: "No eligible catalog games matched the current profile.", created_at: "2026-01-01T00:00:00Z" } });
      }
      return undefined;
    }));
    render(<App />);
    fireEvent.change(await screen.findByLabelText("Display name"), { target: { value: "Demo Player" } });
    fireEvent.click(screen.getByRole("button", { name: "Build player profile" }));
    fireEvent.click(await screen.findByRole("button", { name: "Skip Steam import" }));
    fireEvent.click(await screen.findByRole("button", { name: "Generate recommendations" }));

    expect(await screen.findByRole("heading", { name: "Your recommendations" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getAllByText("No eligible match in this track")).toHaveLength(2));
    expect(screen.getAllByText(/thresholds were not lowered/)).toHaveLength(2);
  });

  it("renders Batch 6A fixture games in both recommendation tracks", async () => {
    vi.stubGlobal("fetch", baseFetch((url, init) => {
      if (url.endsWith("/api/profiles") && init?.method === "POST") return jsonResponse({ profile });
      if (url.endsWith("/api/recommendations") && init?.method === "POST") {
        return jsonResponse({ run_id: "r_fixture", job: { job_id: "j_fixture", status: "queued", current_step: "queued", processed_items: 0, total_items: 2, result_ref: null, error: null, job_type: "recommendation" } });
      }
      if (url.endsWith("/api/jobs/j_fixture")) {
        return jsonResponse({ job: { job_id: "j_fixture", status: "completed", current_step: "completed", processed_items: 2, total_items: 2, result_ref: "r_fixture", error: null, job_type: "recommendation" } });
      }
      if (url.endsWith("/api/recommendations/r_fixture")) {
        return jsonResponse({ recommendation: {
          run_id: "r_fixture",
          profile_id: "p_test",
          status: "ok",
          same_track: [{ appid: 1145360, name: "Hades", track: "same_track", ai_rank: 1, compatibility_score: 0.925, ranking_reason: "Strong verified game-gene fit.", matched_gene_ids: ["challenge"], evidence_ids: ["ev_1145360_challenge"], caution: null }],
          cross_track: [{ appid: 646570, name: "Slay the Spire", track: "cross_track", ai_rank: 1, compatibility_score: 0.73625, ranking_reason: "A compatible cross-genre discovery.", matched_gene_ids: ["strategy"], evidence_ids: ["ev_646570_strategy"], caution: null }],
          message: null,
          created_at: "2026-11-22T00:00:00Z",
        } });
      }
      return undefined;
    }));
    render(<App />);
    fireEvent.change(await screen.findByLabelText("Display name"), { target: { value: "Demo Player" } });
    fireEvent.click(screen.getByRole("button", { name: "Build player profile" }));
    fireEvent.click(await screen.findByRole("button", { name: "Skip Steam import" }));
    fireEvent.click(await screen.findByRole("button", { name: "Generate recommendations" }));

    expect(await screen.findByRole("heading", { name: "Hades" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Slay the Spire" })).toBeInTheDocument();
    expect(screen.getByText("93%")).toBeInTheDocument();
    expect(screen.getByText("74%")).toBeInTheDocument();
    expect(screen.getByText("ev_1145360_challenge")).toBeInTheDocument();
  });
});
