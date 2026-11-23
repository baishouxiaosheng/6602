import type { GeneId } from "../api/types";

export interface RadarPoint {
  geneId: GeneId;
  label: string;
  value: number; // 0–4
  priority: boolean;
}

const CENTER_X = 190;
const CENTER_Y = 150;
const RADIUS = 100;
const MAX_LEVEL = 4;

function point(index: number, count: number, radius: number): [number, number] {
  const angle = -Math.PI / 2 + (2 * Math.PI * index) / count;
  return [CENTER_X + radius * Math.cos(angle), CENTER_Y + radius * Math.sin(angle)];
}

function polygon(count: number, radiusAt: (index: number) => number) {
  return Array.from({ length: count }, (_, index) => point(index, count, radiusAt(index)))
    .map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`)
    .join(" ");
}

/** Nine-axis radar of the fused gene targets. Decorative: the same numbers are in the cards beside it. */
export function GeneRadar({ points }: { points: RadarPoint[] }) {
  const count = points.length;
  if (count < 3) return null;
  return (
    <svg className="gene-radar" viewBox="0 0 380 300" role="img" aria-label="Game-gene radar chart">
      {[1, 2, 3, 4].map((level) => (
        <polygon className="grid" key={level} points={polygon(count, () => (RADIUS * level) / MAX_LEVEL)} />
      ))}
      {points.map((item, index) => {
        const [x, y] = point(index, count, RADIUS);
        const [labelX, labelY] = point(index, count, RADIUS + 16);
        const anchor = Math.abs(labelX - CENTER_X) < 12 ? "middle" : labelX > CENTER_X ? "start" : "end";
        return (
          <g key={item.geneId}>
            <line className="axis" x1={CENTER_X} y1={CENTER_Y} x2={x} y2={y} />
            <text x={labelX} y={labelY + 4} textAnchor={anchor}>{item.label.split(" ")[0]}</text>
          </g>
        );
      })}
      <polygon className="area" points={polygon(count, (index) => (RADIUS * points[index].value) / MAX_LEVEL)} />
      {points.map((item, index) => {
        const [x, y] = point(index, count, (RADIUS * item.value) / MAX_LEVEL);
        return <circle className={item.priority ? "dot priority" : "dot"} key={item.geneId} cx={x} cy={y} r={3.2} />;
      })}
    </svg>
  );
}
