import { useState } from "react";

import type { GeneId, Job, QuestionnaireDefinition, SteamImportPreview } from "../api/types";

interface SteamImportStepProps {
  definition: QuestionnaireDefinition;
  preview: SteamImportPreview | null;
  job: Job | null;
  busy: boolean;
  onPreview: (identity: string) => Promise<void>;
  onConfirm: (favorites: Array<{ appid: number; liked_aspects: string[] }>) => Promise<void>;
  onSkip: () => void;
}

function formatPlaytime(minutes: number) {
  if (minutes < 60) return `${minutes} min`;
  return `${(minutes / 60).toFixed(minutes >= 600 ? 0 : 1)} hr`;
}

function titleCase(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

export function SteamImportStep({
  definition,
  preview,
  job,
  busy,
  onPreview,
  onConfirm,
  onSkip,
}: SteamImportStepProps) {
  const [identity, setIdentity] = useState("");
  const [consent, setConsent] = useState(false);
  const [localError, setLocalError] = useState("");
  const [favorites, setFavorites] = useState<Record<number, GeneId[]>>({});

  async function submitPreview(event: React.FormEvent) {
    event.preventDefault();
    if (!identity.trim()) {
      setLocalError("Enter a SteamID64 or public Steam profile URL.");
      return;
    }
    if (!consent) {
      setLocalError("You must explicitly consent before the library is requested.");
      return;
    }
    setLocalError("");
    await onPreview(identity.trim());
  }

  function toggleFavorite(appid: number) {
    setFavorites((current) => {
      if (current[appid]) {
        const next = { ...current };
        delete next[appid];
        return next;
      }
      return { ...current, [appid]: [] };
    });
  }

  function toggleAspect(appid: number, geneId: GeneId) {
    setFavorites((current) => {
      const aspects = current[appid] ?? [];
      return {
        ...current,
        [appid]: aspects.includes(geneId)
          ? aspects.filter((item) => item !== geneId)
          : [...aspects, geneId],
      };
    });
  }

  if (!preview) {
    return (
      <section className="panel" aria-labelledby="steam-import-title">
        <div className="section-heading">
          <p className="eyebrow">Step 2 · Optional behavioral signal</p>
          <h2 id="steam-import-title">Import your public Steam library</h2>
          <p>Owned games are excluded from recommendations. Playtime is only a weak signal; selected favorites and liked aspects carry more meaning.</p>
        </div>
        {localError && <div className="notice notice-error" role="alert">{localError}</div>}
        <form className="steam-form" onSubmit={(event) => void submitPreview(event)}>
          <label className="field">
            <span>SteamID64 or public profile URL</span>
            <input value={identity} onChange={(event) => setIdentity(event.target.value)} placeholder="76561198… or https://steamcommunity.com/id/…" />
          </label>
          <label className="consent-box">
            <input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} />
            <span><strong>I consent to a one-time read of my public game library.</strong><small>No password or Steam login is requested. The API key remains on the backend.</small></span>
          </label>
          <div className="actions split-actions">
            <button type="button" className="button button-ghost" onClick={onSkip}>Skip Steam import</button>
            <button type="submit" className="button button-primary" disabled={busy}>{busy ? "Loading library…" : "Preview library"}</button>
          </div>
        </form>
      </section>
    );
  }

  return (
    <section className="panel" aria-labelledby="steam-preview-title">
      <div className="section-heading heading-with-stat">
        <div><p className="eyebrow">Library preview · not applied yet</p><h2 id="steam-preview-title">Choose meaningful favorites</h2><p>Steam account {preview.steam_id_masked} · {preview.games.length} games found</p></div>
        <div className="metric"><strong>{Object.keys(favorites).length}</strong><span>favorites</span></div>
      </div>

      {preview.games.length === 0 ? (
        <div className="empty-state"><h3>No public games found</h3><p>You can continue with the questionnaire-only profile.</p></div>
      ) : (
        <div className="library-list">
          {preview.games.map((game) => {
            const selected = favorites[game.appid] !== undefined;
            return (
              <article className={`library-game ${selected ? "selected" : ""}`} key={game.appid}>
                <div className="library-game-header">
                  <label className="favorite-toggle"><input type="checkbox" checked={selected} onChange={() => toggleFavorite(game.appid)} /><span>Favorite</span></label>
                  <div><h3>{game.name ?? `Steam App ${game.appid}`}</h3><p>AppID {game.appid} · {formatPlaytime(game.playtime_minutes)}</p></div>
                </div>
                {selected && (
                  <fieldset className="aspect-picker">
                    <legend>What do you like about it?</legend>
                    {definition.genes.map((gene) => (
                      <label key={gene.gene_id}><input type="checkbox" checked={favorites[game.appid].includes(gene.gene_id)} onChange={() => toggleAspect(game.appid, gene.gene_id)} />{gene.label}</label>
                    ))}
                  </fieldset>
                )}
              </article>
            );
          })}
        </div>
      )}

      {job && (
        <div className="job-progress" aria-live="polite">
          <div><strong>{titleCase(job.current_step)}</strong><span>{job.processed_items} / {job.total_items}</span></div>
          <progress value={job.processed_items} max={Math.max(1, job.total_items)} />
        </div>
      )}

      <div className="actions split-actions">
        <button className="button button-ghost" onClick={onSkip} disabled={busy}>Continue without import</button>
        <button className="button button-primary" disabled={busy} onClick={() => void onConfirm(Object.entries(favorites).map(([appid, aspects]) => ({ appid: Number(appid), liked_aspects: aspects })))}>
          {busy ? "Processing library…" : "Confirm library and continue"}
        </button>
      </div>
    </section>
  );
}
