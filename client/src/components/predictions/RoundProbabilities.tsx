import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { Prediction } from '../../types';

interface RoundProbabilitiesProps {
  prediction: Prediction;
}

export default function RoundProbabilities({ prediction }: RoundProbabilitiesProps) {
  if (!prediction.round_probabilities) return null;

  const data = Object.entries(prediction.round_probabilities)
    .map(([round, prob]) => ({
      round: round === 'decision' ? 'DEC' : `R${round}`,
      prob,
    }))
    .sort((a, b) => {
      if (a.round === 'DEC') return 1;
      if (b.round === 'DEC') return -1;
      return a.round.localeCompare(b.round);
    });

  const maxProb = Math.max(...data.map((d) => d.prob));

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium text-muted-foreground">Round of Finish</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-end gap-1.5" style={{ height: 120 }}>
          {data.map(({ round, prob }) => {
            const height = maxProb > 0 ? (prob / maxProb) * 100 : 0;
            const pct = Math.round(prob * 100);

            return (
              <div key={round} className="flex flex-1 flex-col items-center gap-1">
                <span className="text-[10px] tabular-nums text-muted-foreground">{pct}%</span>
                <div className="w-full flex-1 flex items-end">
                  <div
                    className="w-full rounded-t-sm bg-red-500/80 transition-all"
                    style={{ height: `${height}%`, minHeight: pct > 0 ? 4 : 0 }}
                  />
                </div>
                <span className="text-[10px] font-medium text-muted-foreground">{round}</span>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
