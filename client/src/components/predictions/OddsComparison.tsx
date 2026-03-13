import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';
import type { Odds, Prediction } from '../../types';

interface OddsComparisonProps {
  odds: Odds;
  prediction: Prediction | undefined;
  fighter1Name: string;
  fighter2Name: string;
}

function formatAmerican(odds: number): string {
  return odds > 0 ? `+${odds}` : `${odds}`;
}

export default function OddsComparison({ odds, prediction, fighter1Name, fighter2Name }: OddsComparisonProps) {
  const f1Implied = Math.round(odds.fighter_1_implied * 100);
  const f2Implied = Math.round(odds.fighter_2_implied * 100);
  const f1Ai = prediction ? Math.round(prediction.fighter_1_win_prob * 100) : null;
  const f2Ai = prediction ? Math.round(prediction.fighter_2_win_prob * 100) : null;

  const f1Edge = f1Ai !== null ? f1Ai - f1Implied : null;
  const f2Edge = f2Ai !== null ? f2Ai - f2Implied : null;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium text-muted-foreground">AI vs Betting Odds</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <FighterOddsRow
          name={fighter1Name}
          nameColor="text-blue-400"
          barColor="bg-blue-500"
          american={odds.fighter_1_american}
          implied={f1Implied}
          ai={f1Ai}
          edge={f1Edge}
        />
        <FighterOddsRow
          name={fighter2Name}
          nameColor="text-red-400"
          barColor="bg-red-500"
          american={odds.fighter_2_american}
          implied={f2Implied}
          ai={f2Ai}
          edge={f2Edge}
        />

        <Separator />

        <div className="flex items-center justify-between text-[10px] text-muted-foreground">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1">
              <div className="h-1.5 w-3 rounded-full bg-muted-foreground/40" /> Odds
            </div>
            <div className="flex items-center gap-1">
              <div className="h-1.5 w-3 rounded-full bg-blue-500/80" /> AI
            </div>
          </div>
          <span className="text-green-400">+ = AI sees value</span>
        </div>

        <div className="text-[10px] text-muted-foreground/60">
          Source: {odds.source.replace('_', ' ')}
        </div>
      </CardContent>
    </Card>
  );
}

function FighterOddsRow({
  name,
  nameColor,
  barColor,
  american,
  implied,
  ai,
  edge,
}: {
  name: string;
  nameColor: string;
  barColor: string;
  american: number;
  implied: number;
  ai: number | null;
  edge: number | null;
}) {
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between">
        <span className={`text-sm font-medium ${nameColor}`}>{name}</span>
        <span className="text-xs tabular-nums text-muted-foreground">{formatAmerican(american)}</span>
      </div>
      <div className="flex items-center gap-2.5">
        <div className="flex-1">
          <div className="mb-1 flex justify-between text-[10px] text-muted-foreground">
            <span>Odds: {implied}%</span>
            {ai !== null && <span>AI: {ai}%</span>}
          </div>
          <div className="relative h-2 overflow-hidden rounded-full bg-muted">
            <div
              className="absolute h-full rounded-full bg-muted-foreground/30"
              style={{ width: `${implied}%` }}
            />
            {ai !== null && (
              <div
                className={`absolute h-full rounded-full ${barColor} opacity-80`}
                style={{ width: `${ai}%` }}
              />
            )}
          </div>
        </div>
        {edge !== null && (
          <span className={cn(
            'min-w-[2.5rem] text-right text-xs font-medium tabular-nums',
            edge > 3 ? 'text-green-400' : edge < -3 ? 'text-red-400' : 'text-muted-foreground'
          )}>
            {edge > 0 ? '+' : ''}{edge}%
          </span>
        )}
      </div>
    </div>
  );
}
