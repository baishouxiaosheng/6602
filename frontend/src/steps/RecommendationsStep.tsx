import { useEffect, useState } from "react";

import { getCatalogGame } from "../api/client";
import type { CatalogGame, GeneId, PlayerProfile, RecommendationItem, RecommendationRun } from "../api/types";

type Targets = Partial<Record<GeneId, number>>;

interface RecommendationsStepProps {
  recommendation: RecommendationRun;
  profile?: PlayerProfile | null;
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

const LEVELS = [1, 2, 3, 4];

/** One tile per matched gene: the game's level as filled pips, the player's target as a marker. */
function GeneTiles({ item, game, targets }: { item: RecommendationItem; game?: CatalogGame; targets: Targets }) {
  return (
    <ul className="gene-tiles">
      {item.matched_gene_ids.map((geneId: GeneId) => {
        const level = game?.genes.find((candidate) => candidate.gene_id === geneId)?.level ?? null;
        const target = targets[geneId];
        return (
          <li key={geneId} title={target === undefined ? undefined : `You want ${target} of 4`}>
            <span className="gene-tile-name">{titleCase(geneId)}</span>
            <span className="pips" aria-label={level === null ? "evidence stored" : `game level ${level} of 4`}>
              {LEVELS.map((step) => <i key={step} className={`${level !== null && step <= level ? "on" : ""}${target !== undefined && step === Math.round(target) ? " you" : ""}`} />)}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

function EvidenceDetails({ item, game }: { item: RecommendationItem; game?: CatalogGame }) {
  const quotes = new Map<string, string>();
  for (const gene of game?.genes ?? []) for (const entry of gene.evidence) quotes.set(entry.evidence_id, entry.quote_original);
  return (
    <details className="evidence-details">
      <summary>Evidence ({item.evidence_ids.length})</summary>
      <ul>
        {item.evidence_ids.map((evidence) => (
          <li key={evidence}>{quotes.has(evidence) && <q>{quotes.get(evidence)}</q>}<code>{evidence}</code></li>
        ))}
      </ul>
    </details>
  );
}

function RecommendationCard({ item, game, targets }: { item: RecommendationItem; game?: CatalogGame; targets: Targets }) {
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
        <h3>{item.name}</h3>
        <p className="game-meta">
          {game?.genres.map((genre) => <span key={genre}>{titleCase(genre)}</span>)}
          {price && <span className="price">{price}</span>}
        </p>
        <p className="ranking-reason">{item.ranking_reason}</p>
        {item.caution && <p className="caution"><span aria-hidden="true">!</span>{item.caution}</p>}
        <EvidenceDetails item={item} game={game} />
      </div>
      <div className="recommendation-side">
        <div className={`compatibility ${level}`}><strong>{percent}%</strong><span>match</span></div>
        <GeneTiles item={item} game={game} targets={targets} />
      </div>
    </article>
  );
}

function TrackSection({ title, subtitle, items, kind, games, targets }: { title: string; subtitle: string; items: RecommendationItem[]; kind: "same" | "cross"; games: Record<number, CatalogGame>; targets: Targets }) {
  return (
    <section className={`track-section track-${kind}`}>
      <div className="track-heading"><h2>{title}</h2><p>{subtitle}</p></div>
      {items.length ? <div className="recommendation-list">{items.map((item) => <RecommendationCard item={item} game={games[item.appid]} targets={targets} key={item.appid} />)}</div> : <div className="empty-state compact"><h3>No eligible match in this track</h3><p>Evidence or compatibility thresholds were not lowered to fill the list.</p></div>}
    </section>
  );
}

export function RecommendationsStep({ recommendation, profile, onRestart }: RecommendationsStepProps) {
  const all = [...recommendation.same_track, ...recommendation.cross_track];
  const games = useCatalogGames(all.map((item) => item.appid));
  const targets: Targets = Object.fromEntries((profile?.gene_contributions ?? []).map((gene) => [gene.gene_id, gene.final_target]));
  return (
    <section className="results-panel" aria-labelledby="recommendations-title">
      <div className="results-hero">
        <h1 id="recommendations-title">Your recommendations</h1>
        <div className="results-actions">
          <span className="pip-legend"><span className="pips"><i className="on" /><i className="on" /><i className="on you" /><i /></span>game level · outline = your target</span>
          {recommendation.status !== "ok" && <span className={`result-status status-${recommendation.status}`}>{titleCase(recommendation.status)}</span>}
          <button className="button button-ghost" onClick={onRestart}>Start a new profile</button>
        </div>
      </div>
      {recommendation.message && <p className="results-note">{recommendation.message}</p>}
      <TrackSection title="Familiar territory" subtitle="Genres you already play" items={recommendation.same_track} kind="same" games={games} targets={targets} />
      <TrackSection title="Cross-genre discoveries" subtitle="New genre, matching genes" items={recommendation.cross_track} kind="cross" games={games} targets={targets} />
    </section>
  );
}
