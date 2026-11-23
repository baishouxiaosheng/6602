import { useEffect, useState } from "react";

import {
  confirmPreferences,
  confirmSteamImport,
  createProfile,
  getHealth,
  getProfile,
  getQuestionnaire,
  getRecommendation,
  parsePreferences,
  pollJob,
  previewSteamImport,
  startRecommendation,
} from "./api/client";
import type {
  HealthResponse,
  Job,
  PlayerProfile,
  PreferenceParseResult,
  QuestionnaireDefinition,
  QuestionnaireSubmission,
  RecommendationRun,
  SteamImportPreview,
} from "./api/types";
import { StepIndicator } from "./components/StepIndicator";
import { ProfileSummaryStep } from "./steps/ProfileSummaryStep";
import { QuestionnaireStep } from "./steps/QuestionnaireStep";
import { RecommendationsStep } from "./steps/RecommendationsStep";
import { SteamImportStep } from "./steps/SteamImportStep";
import "./styles.css";

type BootState =
  | { kind: "loading" }
  | { kind: "ready"; health: HealthResponse; questionnaire: QuestionnaireDefinition }
  | { kind: "error"; message: string };

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "The operation could not be completed.";
}

function App() {
  const [boot, setBoot] = useState<BootState>({ kind: "loading" });
  const [step, setStep] = useState(1);
  const [profile, setProfile] = useState<PlayerProfile | null>(null);
  const [parsedPreferences, setParsedPreferences] = useState<PreferenceParseResult | null>(null);
  const [steamPreview, setSteamPreview] = useState<SteamImportPreview | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [recommendation, setRecommendation] = useState<RecommendationRun | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([getHealth(controller.signal), getQuestionnaire(controller.signal)])
      .then(([health, questionnaire]) => setBoot({ kind: "ready", health, questionnaire }))
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        setBoot({ kind: "error", message: errorMessage(reason) });
      });
    return () => controller.abort();
  }, []);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function handleQuestionnaire(submission: QuestionnaireSubmission) {
    await run(async () => {
      const created = await createProfile(submission);
      setProfile(created);
      if (submission.additional_preferences) {
        const parsed = await parsePreferences(created.profile_id, submission.additional_preferences);
        setParsedPreferences(parsed);
      } else {
        setStep(2);
      }
    });
  }

  async function handlePreferenceConfirmation(constraints: string[]) {
    if (!profile || !parsedPreferences) return;
    await run(async () => {
      const updated = await confirmPreferences(profile.profile_id, parsedPreferences, constraints);
      setProfile(updated);
      setParsedPreferences(null);
      setStep(2);
    });
  }

  async function handleSteamPreview(identity: string) {
    if (!profile) return;
    await run(async () => {
      setSteamPreview(await previewSteamImport(profile.profile_id, identity));
    });
  }

  async function handleSteamConfirm(favorites: Array<{ appid: number; liked_aspects: string[] }>) {
    if (!profile || !steamPreview) return;
    await run(async () => {
      const queued = await confirmSteamImport(profile.profile_id, steamPreview.preview_token, favorites);
      setJob(queued);
      await pollJob(queued.job_id, setJob);
      setProfile(await getProfile(profile.profile_id));
      setJob(null);
      setStep(3);
    });
  }

  async function handleRecommendation() {
    if (!profile) return;
    await run(async () => {
      const started = await startRecommendation(profile.profile_id);
      setJob(started.job);
      await pollJob(started.job.job_id, setJob);
      setRecommendation(await getRecommendation(started.runId));
      setJob(null);
      setStep(4);
    });
  }

  if (boot.kind === "loading") {
    return <main className="splash" aria-live="polite"><div className="loader" /><p>Connecting to the Game Gene Agent…</p></main>;
  }

  if (boot.kind === "error") {
    return <main className="splash"><div className="fatal-card"><p className="eyebrow">Connection error</p><h1>Backend unavailable</h1><p>{boot.message}</p><button className="button button-primary" onClick={() => window.location.reload()}>Try again</button></div></main>;
  }

  return (
    <main className="app-shell">
      <header className="app-header">
        <div className="brand"><span className="brand-mark">GG</span><div><strong>Game Gene Agent</strong><small>SYE 6602 Course Demo</small></div></div>
        <div className="backend-status" title={`${boot.health.service} v${boot.health.version}`}><span />Backend connected</div>
      </header>

      <div className="workflow-shell">
        <StepIndicator current={step} />
        {error && <div className="notice notice-error global-error" role="alert"><span>{error}</span><button aria-label="Dismiss error" onClick={() => setError("")}>×</button></div>}

        {step === 1 && (
          <QuestionnaireStep
            definition={boot.questionnaire}
            busy={busy}
            parsedPreferences={parsedPreferences}
            onSubmit={handleQuestionnaire}
            onConfirmPreferences={handlePreferenceConfirmation}
          />
        )}
        {step === 2 && profile && (
          <SteamImportStep
            definition={boot.questionnaire}
            preview={steamPreview}
            job={job}
            busy={busy}
            onPreview={handleSteamPreview}
            onConfirm={handleSteamConfirm}
            onSkip={() => setStep(3)}
          />
        )}
        {step === 3 && profile && (
          <ProfileSummaryStep
            profile={profile}
            definition={boot.questionnaire}
            job={job}
            busy={busy}
            onRecommend={handleRecommendation}
          />
        )}
        {step === 4 && recommendation && (
          <RecommendationsStep recommendation={recommendation} onRestart={() => window.location.reload()} />
        )}
      </div>

      <footer><span>Evidence-grounded recommendations</span><span>Steam data · deterministic compatibility · Qwen ranking</span></footer>
    </main>
  );
}

export default App;
