import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import type { Odds, Prediction } from '../../types';

interface ValueBetProps {
  prediction: Prediction;
  odds: Odds | null | undefined;
  fighter1Name: string;
  fighter2Name: string;
  winnerName?: string | null;
}

export default function ValueBet({ prediction, odds, fighter1Name, fighter2Name, winnerName }: ValueBetProps) {
  if (!odds) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">Value Bet</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">No betting odds available for this fight.</p>
        </CardContent>
      </Card>
    );
  }

  const impliedF1 = odds.fighter_1_implied;
  const impliedF2 = odds.fighter_2_implied;
  const aiF1 = prediction.fighter_1_win_prob;
  const aiF2 = prediction.fighter_2_win_prob;

  const edgeF1 = aiF1 - impliedF1;
  const edgeF2 = aiF2 - impliedF2;
  const bestEdge = Math.max(edgeF1, edgeF2);

  const hasBet = bestEdge >= 0.03;

  let betOn: string | null = null;
  let betEdge = 0;
  let betOddsAmerican = 0;
  let betOddsDecimal = 0;
  let betAmount = 0;
  let aiProb = 0;
  let vegasImplied = 0;

  if (hasBet) {
    if (edgeF1 > edgeF2) {
      betOn = fighter1Name;
      betEdge = edgeF1;
      betOddsAmerican = odds.fighter_1_american;
      betOddsDecimal = odds.fighter_1_decimal;
      aiProb = aiF1;
      vegasImplied = impliedF1;
    } else {
      betOn = fighter2Name;
      betEdge = edgeF2;
      betOddsAmerican = odds.fighter_2_american;
      betOddsDecimal = odds.fighter_2_decimal;
      aiProb = aiF2;
      vegasImplied = impliedF2;
    }
    betAmount = Math.min(100 * (betEdge / 0.05), 500);
  }

  const fmtAmerican = (o: number) => (o > 0 ? `+${o}` : `${o}`);

  // P&L for completed fights
  const isComplete = winnerName != null;
  const won = isComplete && hasBet ? betOn === winnerName : null;
  const payout = won !== null && hasBet
    ? (won ? betAmount * (betOddsDecimal - 1) : -betAmount)
    : null;

  return (
    <Card className={cn(hasBet && 'border-green-500/30')}>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">Value Bet</CardTitle>
      </CardHeader>
      <CardContent>
        {hasBet ? (
          <div className="space-y-3">
            <div>
              <p className="text-lg font-bold text-green-400">{betOn}</p>
              <p className="text-xs text-muted-foreground">
                {fmtAmerican(betOddsAmerican)} ({betOddsDecimal.toFixed(2)}x)
              </p>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div>
                <p className="text-[10px] text-muted-foreground">Edge</p>
                <p className="text-lg font-bold tabular-nums text-green-400">
                  +{(betEdge * 100).toFixed(1)}%
                </p>
              </div>
              <div>
                <p className="text-[10px] text-muted-foreground">Bet Size</p>
                <p className="text-lg font-bold tabular-nums">
                  ${Math.round(betAmount)}
                </p>
              </div>
              <div>
                <p className="text-[10px] text-muted-foreground">
                  {isComplete ? 'P&L' : 'Potential'}
                </p>
                {payout !== null ? (
                  <p className={cn(
                    'text-lg font-bold tabular-nums',
                    payout >= 0 ? 'text-green-400' : 'text-red-400'
                  )}>
                    {payout >= 0 ? '+' : '-'}${Math.abs(payout).toFixed(0)}
                  </p>
                ) : (
                  <p className="text-lg font-bold tabular-nums text-muted-foreground">
                    +${Math.round(betAmount * (betOddsDecimal - 1))}
                  </p>
                )}
              </div>
            </div>

            <div className="flex items-center gap-4 text-[10px] text-muted-foreground/60">
              <span>AI: {(aiProb * 100).toFixed(0)}%</span>
              <span>Vegas: {(vegasImplied * 100).toFixed(0)}%</span>
            </div>
          </div>
        ) : (
          <div>
            <p className="text-sm text-muted-foreground">No value bet on this fight.</p>
            <p className="mt-1 text-[10px] text-muted-foreground/60">
              AI and Vegas odds are too close (edge &lt; 3%).
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
