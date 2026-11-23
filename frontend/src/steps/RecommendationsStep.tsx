import type { RecommendationItem, RecommendationRun } from "../api/types";

interface RecommendationsStepProps {
  recommendation: RecommendationRun;
  onRestart: () => void;
}

function titleCase(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function RecommendationCard({ item }: { item: RecommendationItem }) {
  const percent = Math.round(item.compatibility_score * 100);
  const level = percent >= 82 ? "high" : percent >= 72 ? "mid" : "low";
  const storeUrl = `https://store.steampowered.com/app/${item.appid}/`;
  const imageUrl = `https://cdn.akamai.steamstatic.com/steam/apps/${item.appid}/header.jpg`;
  return (
    <article className="recommendation-card">
      <div className="capsule">
        <span className="capsule-name" aria-hidden="true">{item.name}</span>
        <div className="capsule-image" style={{ backgroundImage: `url("${imageUrl}")` }} />
        <div className="recommendation-rank"><span>AI rank</span><strong>#{item.ai_rank}</strong></div>
        <div className="capsule-foot"><a className="store-link" href={storeUrl} target="_blank" rel="noopener noreferrer">View on Steam ↗</a></div>
      </div>
      <div className="recommendation-content">
        <div className="recommendation-title"><div><h3>{item.name}</h3><p>Steam AppID {item.appid}</p></div><div className={`compatibility ${level}`}><strong>{percent}%</strong><span>Gene compatibility</span></div></div>
        <p className="ranking-reason">{item.ranking_reason}</p>
        <div className="tag-row">{item.matched_gene_ids.map((gene) => <span className="tag tag-match" key={gene}>{titleCase(gene)}</span>)}</div>
        {item.caution && <div className="caution"><strong>Keep in mind</strong><p>{item.caution}</p></div>}
        <details><summary>Evidence references ({item.evidence_ids.length})</summary><ul>{item.evidence_ids.map((evidence) => <li key={evidence}><code>{evidence}</code></li>)}</ul></details>
      </div>
    </article>
  );
}

function TrackSection({ title, subtitle, items, kind }: { title: string; subtitle: string; items: RecommendationItem[]; kind: "same" | "cross" }) {
  return (
    <section className={`track-section track-${kind}`}>
      <div className="track-heading"><div><h2>{title}</h2><p>{subtitle}</p></div><span>{items.length} result{items.length === 1 ? "" : "s"}</span></div>
      {items.length ? <div className="recommendation-list">{items.map((item) => <RecommendationCard item={item} key={item.appid} />)}</div> : <div className="empty-state compact"><h3>No eligible match in this track</h3><p>Evidence or compatibility thresholds were not lowered to fill the list.</p></div>}
    </section>
  );
}

export function RecommendationsStep({ recommendation, onRestart }: RecommendationsStepProps) {
  return (
    <section className="results-panel" aria-labelledby="recommendations-title">
      <div className="results-hero"><p className="eyebrow">Step 4 · Evidence-grounded result</p><h1 id="recommendations-title">Your recommendations</h1><p>Qwen ranked only the program-supplied candidates. Compatibility is calculated deterministically from verified game genes.</p><div className={`result-status status-${recommendation.status}`}>{titleCase(recommendation.status)}</div></div>
      {recommendation.message && <div className="notice notice-info">{recommendation.message}</div>}
      <TrackSection title="Familiar territory" subtitle="Games that overlap with your familiar Steam genres." items={recommendation.same_track} kind="same" />
      <TrackSection title="Cross-genre discoveries" subtitle="Different surface genres with a compatible game-gene pattern." items={recommendation.cross_track} kind="cross" />
      <div className="actions actions-end"><button className="button button-ghost" onClick={onRestart}>Start a new profile</button></div>
    </section>
  );
}
