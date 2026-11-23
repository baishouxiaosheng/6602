import { useEffect, useState } from "react";

import { getCatalogGame } from "../api/client";
import type { CatalogGame, GeneId, RecommendationItem, RecommendationRun } from "../api/types";

interface RecommendationsStepProps {
  recommendation: RecommendationRun;
  onRestart: () => void;
}

function titleCase(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function priceLabel(game: CatalogGame) {
  if (game.is_free) return "Free to play";
  if (game.price_usd_cents === null) return null;
  return `$${(game.price_usd_cents / 100).toFixed(2)}`;
}

/** Stored catalogue facts for the recommended games. A failed lookup only hides the extra detail. */
function useCatalogGames(appids: number[]) {
  const [games, setGames] = useState<Record<number, CatalogGame>>({});
  const key = appids.join(",");
  useEffect(() => {
    const controller = new AbortController();
    for (const appid of appids) {
      getCatalogGame(appid, controller.signal)
        .then((game) => setGames((current) => ({ ...current, [appid]: game })))
        .catch(() => undefined);
    }
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return games;
}

function EvidenceList({ item, game }: { item: RecommendationItem; game?: CatalogGame }) {
  const cited = new Set(item.evidence_ids);
  const rows = item.matched_gene_ids.map((geneId: GeneId) => {
    const gene = game?.genes.find((candidate) => candidate.gene_id === geneId);
    const evidence = gene?.evidence.find((entry) => cited.has(entry.evidence_id)) ?? gene?.evidence[0];
    return { geneId, level: gene?.level ?? null, quote: evidence?.quote_original ?? null };
  });
  return (
    <ul className="evidence-list">
      {rows.map((row) => (
        <li key={row.geneId}>
          <span className="evidence-gene">{titleCase(row.geneId)}{row.level !== null && <b>{row.level}/4</b>}</span>
          {row.quote ? <q>{row.quote}</q> : <span className="muted">Evidence stored for this gene</span>}
        </li>
      ))}
    </ul>
  );
}

function RecommendationCard({ item, game }: { item: RecommendationItem; game?: CatalogGame }) {
  const percent = Math.round(item.compatibility_score * 100);
  const level = percent >= 82 ? "high" : percent >= 72 ? "mid" : "low";
  const storeUrl = `https://store.steampowered.com/app/${item.appid}/`;
  const imageUrl = `https://cdn.akamai.steamstatic.com/steam/apps/${item.appid}/header.jpg`;
  const price = game ? priceLabel(game) : null;
  return (
    <article className="recommendation-card">
      <a className="capsule" href={storeUrl} target="_blank" rel="noopener noreferrer" aria-label={`${item.name} on Steam`}>
        <span className="capsule-name" aria-hidden="true">{item.name}</span>
        <span className="capsule-image" style={{ backgroundImage: `url("${imageUrl}")` }} />
        <span className="recommendation-rank" title="Order chosen by the AI ranker">#{item.ai_rank}</span>
      </a>
      <div className="recommendation-content">
        <div className="recommendation-title">
          <div>
            <h3>{item.name}</h3>
            <p className="game-meta">
              {game?.genres.map((genre) => <span className="tag" key={genre}>{titleCase(genre)}</span>)}
              {price && <span className="price">{price}</span>}
              <a className="store-link" href={storeUrl} target="_blank" rel="noopener noreferrer">View on Steam ↗</a>
            </p>
          </div>
          <div className={`compatibility ${level}`}><strong>{percent}%</strong><span>match</span></div>
        </div>
        <p className="ranking-reason">{item.ranking_reason}</p>
        <EvidenceList item={item} game={game} />
        {item.caution && <p className="caution"><span aria-hidden="true">!</span>{item.caution}</p>}
        <details><summary>Evidence IDs</summary><ul>{item.evidence_ids.map((evidence) => <li key={evidence}><code>{evidence}</code></li>)}</ul></details>
      </div>
    </article>
  );
}

function TrackSection({ title, subtitle, items, kind, games }: { title: string; subtitle: string; items: RecommendationItem[]; kind: "same" | "cross"; games: Record<number, CatalogGame> }) {
  return (
    <section className={`track-section track-${kind}`}>
      <div className="track-heading"><h2>{title}</h2><p>{subtitle}</p></div>
      {items.length ? <div className="recommendation-list">{items.map((item) => <RecommendationCard item={item} game={games[item.appid]} key={item.appid} />)}</div> : <div className="empty-state compact"><h3>No eligible match in this track</h3><p>Evidence or compatibility thresholds were not lowered to fill the list.</p></div>}
    </section>
  );
}

export function RecommendationsStep({ recommendation, onRestart }: RecommendationsStepProps) {
  const all = [...recommendation.same_track, ...recommendation.cross_track];
  const games = useCatalogGames(all.map((item) => item.appid));
  return (
    <section className="results-panel" aria-labelledby="recommendations-title">
      <div className="results-hero">
        <div><h1 id="recommendations-title">Your recommendations</h1><p>Scores come from verified game genes. The AI only orders the shortlisted games.</p></div>
        <div className="results-actions">
          {recommendation.status !== "ok" && <span className={`result-status status-${recommendation.status}`}>{titleCase(recommendation.status)}</span>}
          <button className="button button-ghost" onClick={onRestart}>Start a new profile</button>
        </div>
      </div>
      {recommendation.message && <div className="notice notice-info">{recommendation.message}</div>}
      <TrackSection title="Familiar territory" subtitle="Close to the genres you already play" items={recommendation.same_track} kind="same" games={games} />
      <TrackSection title="Cross-genre discoveries" subtitle="A different genre with a matching gene pattern" items={recommendation.cross_track} kind="cross" games={games} />
    </section>
  );
}
