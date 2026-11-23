import type { Job, PlayerProfile, QuestionnaireDefinition } from "../api/types";
import { GeneRadar } from "../components/GeneRadar";

interface ProfileSummaryStepProps {
  profile: PlayerProfile;
  definition: QuestionnaireDefinition;
  job: Job | null;
  busy: boolean;
  onRecommend: () => Promise<void>;
}

function titleCase(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

export function ProfileSummaryStep({ profile, definition, job, busy, onRecommend }: ProfileSummaryStepProps) {
  const labels = Object.fromEntries(definition.genes.map((gene) => [gene.gene_id, gene.label]));
  return (
    <section className="panel" aria-labelledby="profile-summary-title">
      <div className="section-heading heading-with-stat">
        <div><p className="eyebrow">Step 3 · Transparent fusion</p><h2 id="profile-summary-title">{profile.display_name}&apos;s game-gene profile</h2><p>Every target shows its questionnaire, library, and free-text contribution.</p></div>
        <div className="metric"><strong>{profile.owned_appids.length}</strong><span>owned excluded</span></div>
      </div>

      {profile.warnings.map((warning) => <div className="notice notice-warning" key={warning}>{warning}</div>)}

      <div className="profile-layout">
        <aside className="radar-card">
          <h3>Fused gene targets</h3>
          <GeneRadar points={profile.gene_contributions.map((gene) => ({ geneId: gene.gene_id, label: labels[gene.gene_id] ?? gene.gene_id, value: gene.final_target, priority: gene.weight === 2 }))} />
          <p className="radar-legend"><i />High-priority gene</p>
        </aside>
        <div className="profile-gene-grid">
          {profile.gene_contributions.map((gene) => (
            <article className="profile-gene" key={gene.gene_id}>
              <div className="profile-gene-heading"><div><h3>{labels[gene.gene_id]}</h3><span>{gene.weight === 2 ? "High priority" : "Standard priority"}</span></div><strong>{gene.final_target}</strong></div>
              <div className="gene-bar"><span style={{ width: `${gene.final_target * 25}%` }} /></div>
              <dl><div><dt>Questionnaire</dt><dd>{gene.questionnaire_target}</dd></div><div><dt>Library</dt><dd>{gene.library_adjustment > 0 ? "+" : ""}{gene.library_adjustment}</dd></div><div><dt>Free text</dt><dd>{gene.text_adjustment > 0 ? "+" : ""}{gene.text_adjustment}</dd></div></dl>
            </article>
          ))}
        </div>
      </div>

      <div className="summary-columns">
        <article className="summary-card"><h3>Familiar genres</h3><ol className="ranked-list">{profile.familiar_genres.map((item) => <li key={item.genre}>{titleCase(item.genre)} <span>weight {item.weight}</span></li>)}</ol></article>
        <article className="summary-card"><h3>Hard filters</h3><ul className="bullet-list"><li>{profile.hard_filters.platforms.map(titleCase).join(", ")}</li><li>{titleCase(profile.hard_filters.required_language)}</li><li>{titleCase(profile.hard_filters.social_requirement)}</li><li>{profile.hard_filters.max_price_usd_cents === null ? "No price limit" : `Up to $${(profile.hard_filters.max_price_usd_cents / 100).toFixed(2)}`}</li>{profile.hard_filters.controller_required && <li>Controller required</li>}</ul></article>
        <article className="summary-card"><h3>Soft preferences</h3><div className="tag-row">{profile.soft_descriptor_preferences.length ? profile.soft_descriptor_preferences.map((item) => <span className="tag" key={item}>{titleCase(item)}</span>) : <span className="muted">None</span>}</div></article>
      </div>

      {job && <div className="job-progress" aria-live="polite"><div><strong>{titleCase(job.current_step)}</strong><span>{job.processed_items} / {job.total_items}</span></div><progress value={job.processed_items} max={Math.max(1, job.total_items)} /></div>}

      <div className="actions actions-end"><button className="button button-primary" disabled={busy} onClick={() => void onRecommend()}>{busy ? "Ranking candidates…" : "Generate recommendations"}</button></div>
    </section>
  );
}
