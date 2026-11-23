import type { HardFilters, Job, PlayerProfile, QuestionnaireDefinition } from "../api/types";
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

function signed(value: number) {
  return `${value > 0 ? "+" : ""}${value}`;
}

/** Only the filters that actually restrict the result, in plain words. */
function filterLabels(filters: HardFilters, ownedCount: number) {
  const labels = [filters.platforms.map(titleCase).join(" / ")];
  if (filters.max_price_usd_cents !== null) labels.push(`Up to $${(filters.max_price_usd_cents / 100).toFixed(2)}`);
  if (filters.social_requirement === "no_mandatory_multiplayer") labels.push("No mandatory multiplayer");
  if (filters.social_requirement === "multiplayer_required") labels.push("Multiplayer required");
  if (filters.controller_required) labels.push("Controller required");
  if (ownedCount > 0) labels.push(`${ownedCount} owned games excluded`);
  return labels.filter(Boolean);
}

export function ProfileSummaryStep({ profile, definition, job, busy, onRecommend }: ProfileSummaryStepProps) {
  const labels = Object.fromEntries(definition.genes.map((gene) => [gene.gene_id, gene.label]));
  const adjusted = profile.gene_contributions.some((gene) => gene.library_adjustment !== 0 || gene.text_adjustment !== 0);
  return (
    <section className="panel" aria-labelledby="profile-summary-title">
      <div className="section-heading heading-with-stat">
        <div><p className="eyebrow">Step 3 · Review</p><h2 id="profile-summary-title">{profile.display_name}&apos;s game-gene profile</h2><p>{adjusted ? "Targets from your questionnaire, adjusted by your library and free text." : "Targets come straight from your questionnaire."}</p></div>
        <button className="button button-primary" disabled={busy} onClick={() => void onRecommend()}>{busy ? "Ranking candidates…" : "Generate recommendations"}</button>
      </div>

      {profile.warnings.map((warning) => <div className="notice notice-warning" key={warning}>{warning}</div>)}
      {job && <div className="job-progress" aria-live="polite"><div><strong>{titleCase(job.current_step)}</strong><span>{job.processed_items} / {job.total_items}</span></div><progress value={job.processed_items} max={Math.max(1, job.total_items)} /></div>}

      <div className="profile-layout">
        <aside className="radar-card">
          <GeneRadar points={profile.gene_contributions.map((gene) => ({ geneId: gene.gene_id, label: labels[gene.gene_id] ?? gene.gene_id, value: gene.final_target, priority: gene.weight === 2 }))} />
          <p className="radar-legend"><i />High-priority gene</p>
        </aside>

        <div className="profile-detail">
          <ul className="gene-rows">
            {profile.gene_contributions.map((gene) => (
              <li key={gene.gene_id} className={gene.weight === 2 ? "priority" : undefined}>
                <span className="gene-name">{labels[gene.gene_id]}{gene.weight === 2 && <em>Priority</em>}</span>
                <span className="gene-bar"><span style={{ width: `${gene.final_target * 25}%` }} /></span>
                <strong>{gene.final_target}</strong>
                <span className="gene-shift">
                  {gene.library_adjustment !== 0 && <span title="Adjustment from your Steam library">Library {signed(gene.library_adjustment)}</span>}
                  {gene.text_adjustment !== 0 && <span title="Adjustment from your free text">Text {signed(gene.text_adjustment)}</span>}
                </span>
              </li>
            ))}
          </ul>

          <dl className="profile-facts">
            <div><dt>Familiar genres</dt><dd className="tag-row">{profile.familiar_genres.map((item) => <span className="tag" key={item.genre}>{item.rank}. {titleCase(item.genre)}</span>)}</dd></div>
            <div><dt>Filters</dt><dd className="tag-row">{filterLabels(profile.hard_filters, profile.owned_appids.length).map((label) => <span className="tag tag-plain" key={label}>{label}</span>)}</dd></div>
            {profile.soft_descriptor_preferences.length > 0 && <div><dt>Also prefers</dt><dd className="tag-row">{profile.soft_descriptor_preferences.map((item) => <span className="tag" key={item}>{titleCase(item)}</span>)}</dd></div>}
          </dl>
        </div>
      </div>
    </section>
  );
}
