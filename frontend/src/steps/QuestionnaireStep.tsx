import { useEffect, useMemo, useState } from "react";

import type {
  CanonicalGenre,
  GeneId,
  PreferenceParseResult,
  QuestionnaireDefinition,
  QuestionnaireSubmission,
} from "../api/types";

interface QuestionnaireStepProps {
  definition: QuestionnaireDefinition;
  busy: boolean;
  parsedPreferences: PreferenceParseResult | null;
  onSubmit: (submission: QuestionnaireSubmission) => Promise<void>;
  onConfirmPreferences: (constraints: string[]) => Promise<void>;
}

const rankWeights = [3, 2, 1];

function titleCase(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

export function QuestionnaireStep({
  definition,
  busy,
  parsedPreferences,
  onSubmit,
  onConfirmPreferences,
}: QuestionnaireStepProps) {
  const initialTargets = useMemo(
    () => Object.fromEntries(definition.genes.map((gene) => [gene.gene_id, 2])) as Record<GeneId, number>,
    [definition.genes],
  );
  const [displayName, setDisplayName] = useState("");
  const [targets, setTargets] = useState(initialTargets);
  const [important, setImportant] = useState<GeneId[]>([]);
  const [genres, setGenres] = useState<Array<CanonicalGenre | "">>(["rpg", "", ""]);
  const [platform, setPlatform] = useState("windows");
  const [budget, setBudget] = useState("");
  const [social, setSocial] = useState<"any" | "no_mandatory_multiplayer" | "multiplayer_required">("any");
  const [additionalPreferences, setAdditionalPreferences] = useState("");
  const [localError, setLocalError] = useState("");
  const [confirmedConstraints, setConfirmedConstraints] = useState<string[]>([]);

  useEffect(() => setConfirmedConstraints([]), [parsedPreferences]);

  function toggleImportant(geneId: GeneId) {
    setImportant((current) => {
      if (current.includes(geneId)) return current.filter((item) => item !== geneId);
      if (current.length >= definition.max_important_genes) return current;
      return [...current, geneId];
    });
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const selectedGenres = genres.filter(Boolean) as CanonicalGenre[];
    if (!displayName.trim()) {
      setLocalError("Please enter a display name.");
      return;
    }
    if (!selectedGenres.length || new Set(selectedGenres).size !== selectedGenres.length) {
      setLocalError("Choose at least one familiar genre without duplicates.");
      return;
    }
    const budgetDollars = budget === "" ? null : Number(budget);
    if (budgetDollars !== null && (!Number.isFinite(budgetDollars) || budgetDollars < 0)) {
      setLocalError("Budget must be a non-negative USD amount.");
      return;
    }
    setLocalError("");
    await onSubmit({
      display_name: displayName.trim(),
      gene_targets: targets,
      important_genes: important,
      familiar_genres: selectedGenres.map((genre, index) => ({
        genre,
        rank: index + 1,
        weight: rankWeights[index],
      })),
      hard_filters: {
        platforms: [platform],
        required_language: "english",
        max_price_usd_cents: budgetDollars === null ? null : Math.round(budgetDollars * 100),
        social_requirement: social,
        controller_required: false,
        exclude_owned: true,
      },
      additional_preferences: additionalPreferences.trim(),
    });
  }

  if (parsedPreferences) {
    return (
      <section className="panel" aria-labelledby="preference-review-title">
        <div className="section-heading">
          <p className="eyebrow">AI interpretation · confirmation required</p>
          <h2 id="preference-review-title">Review your free-text preferences</h2>
          <p>Qwen may suggest adjustments, but only you can confirm hard constraints.</p>
        </div>

        <div className="interpretation-grid">
          <article className="summary-card">
            <h3>Gene adjustments</h3>
            {Object.entries(parsedPreferences.gene_adjustments).length ? (
              <ul className="plain-list">
                {Object.entries(parsedPreferences.gene_adjustments).map(([gene, value]) => (
                  <li key={gene}><span>{titleCase(gene)}</span><strong>{Number(value) > 0 ? `+${value}` : value}</strong></li>
                ))}
              </ul>
            ) : <p className="muted">No gene adjustments detected.</p>}
          </article>
          <article className="summary-card">
            <h3>Soft preferences</h3>
            <div className="tag-row">
              {parsedPreferences.soft_descriptor_preferences.length
                ? parsedPreferences.soft_descriptor_preferences.map((item) => <span className="tag" key={item}>{titleCase(item)}</span>)
                : <span className="muted">None detected</span>}
            </div>
          </article>
        </div>

        {parsedPreferences.potential_hard_constraints.length > 0 && (
          <fieldset className="choice-box">
            <legend>Confirm suggested hard constraints</legend>
            {parsedPreferences.potential_hard_constraints.map((constraint) => (
              <label className="check-row" key={constraint}>
                <input
                  type="checkbox"
                  checked={confirmedConstraints.includes(constraint)}
                  onChange={() => setConfirmedConstraints((current) => current.includes(constraint)
                    ? current.filter((item) => item !== constraint)
                    : [...current, constraint])}
                />
                {titleCase(constraint)}
              </label>
            ))}
          </fieldset>
        )}

        {parsedPreferences.unsupported_requests.length > 0 && (
          <div className="notice notice-warning">
            <strong>Could not strictly verify:</strong> {parsedPreferences.unsupported_requests.join(", ")}
          </div>
        )}

        <div className="actions actions-end">
          <button className="button button-primary" disabled={busy} onClick={() => void onConfirmPreferences(confirmedConstraints)}>
            {busy ? "Saving…" : "Confirm and continue"}
          </button>
        </div>
      </section>
    );
  }

  return (
    <form className="panel" onSubmit={(event) => void submit(event)} aria-labelledby="questionnaire-title">
      <div className="section-heading">
        <p className="eyebrow">Step 1 · Initial profile</p>
        <h2 id="questionnaire-title">What kind of experience do you want?</h2>
        <p>Rate all nine game genes from 0 to 4. Mark up to three as especially important.</p>
      </div>

      {localError && <div className="notice notice-error" role="alert">{localError}</div>}

      <label className="field field-compact">
        <span>Display name</span>
        <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} maxLength={80} placeholder="Demo Player" />
      </label>

      <div className="gene-grid">
        {definition.genes.map((gene) => (
          <article className="gene-control" key={gene.gene_id}>
            <div className="gene-title-row">
              <div><h3>{gene.label}</h3><p>{gene.description}</p></div>
              <output aria-label={`${gene.label} value`}>{targets[gene.gene_id]}</output>
            </div>
            <input
              aria-label={gene.label}
              type="range"
              min="0"
              max="4"
              value={targets[gene.gene_id]}
              onChange={(event) => setTargets((current) => ({ ...current, [gene.gene_id]: Number(event.target.value) }))}
            />
            <label className="priority-toggle">
              <input type="checkbox" checked={important.includes(gene.gene_id)} onChange={() => toggleImportant(gene.gene_id)} />
              High priority
            </label>
          </article>
        ))}
      </div>

      <div className="form-grid">
        <fieldset className="choice-box">
          <legend>Familiar genres, in order</legend>
          {genres.map((genre, index) => (
            <label className="field" key={index}>
              <span>{index === 0 ? "Primary genre" : `Optional genre ${index + 1}`}</span>
              <select value={genre} onChange={(event) => setGenres((current) => current.map((item, itemIndex) => itemIndex === index ? event.target.value as CanonicalGenre | "" : item))}>
                {index > 0 && <option value="">None</option>}
                {definition.canonical_genres.map((item) => <option value={item} key={item}>{titleCase(item)}</option>)}
              </select>
            </label>
          ))}
        </fieldset>

        <fieldset className="choice-box">
          <legend>Hard filters</legend>
          <label className="field"><span>Platform</span><select value={platform} onChange={(event) => setPlatform(event.target.value)}><option value="windows">Windows</option><option value="mac">macOS</option><option value="linux">Linux</option></select></label>
          <label className="field"><span>Maximum price (USD, optional)</span><input type="number" min="0" step="1" value={budget} onChange={(event) => setBudget(event.target.value)} placeholder="No limit" /></label>
          <label className="field"><span>Social requirement</span><select value={social} onChange={(event) => setSocial(event.target.value as typeof social)}><option value="any">No hard requirement</option><option value="no_mandatory_multiplayer">No mandatory multiplayer</option><option value="multiplayer_required">Multiplayer required</option></select></label>
        </fieldset>
      </div>

      <label className="field">
        <span>Anything else? (optional)</span>
        <textarea rows={4} maxLength={2000} value={additionalPreferences} onChange={(event) => setAdditionalPreferences(event.target.value)} placeholder="For example: I want a calmer game with pixel art and controller support." />
        <small>Qwen interprets this text. You will confirm any proposed hard constraint.</small>
      </label>

      <div className="actions actions-end">
        <button className="button button-primary" type="submit" disabled={busy}>{busy ? "Building profile…" : "Build player profile"}</button>
      </div>
    </form>
  );
}
