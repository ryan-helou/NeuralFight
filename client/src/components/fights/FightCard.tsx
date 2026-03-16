import { Link } from 'react-router-dom';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { FightSummary } from '../../types';

function fmtAmerican(odds: number) {
  return odds > 0 ? `+${odds}` : `${odds}`;
}

interface FightCardProps {
  fight: FightSummary;
}

export default function FightCard({ fight }: FightCardProps) {
  const hasPrediction = fight.fighter_1_win_prob !== null;
  const f1Pct = hasPrediction ? Math.round(fight.fighter_1_win_prob! * 100) : null;
  const f2Pct = hasPrediction ? Math.round(fight.fighter_2_win_prob! * 100) : null;
  const f1Favored = hasPrediction && fight.fighter_1_win_prob! >= 0.5;

  const hasOdds = fight.fighter_1_american != null && fight.fighter_2_american != null;
  const hasUpset = fight.upset_score != null && fight.upset_score > 0;
  const hasBet = fight.bet_amount != null && fight.bet_on != null;

  // AI/Vegas correctness for past fights
  const isComplete = !!fight.winner_name;
  let aiRight: boolean | null = null;
  let vegasRight: boolean | null = null;
  if (isComplete && hasPrediction) {
    const aiPick = fight.fighter_1_win_prob! >= 0.5 ? fight.fighter_1_name : fight.fighter_2_name;
    aiRight = aiPick === fight.winner_name;
    if (fight.vegas_fighter_1_implied != null && fight.vegas_fighter_2_implied != null) {
      const vegasPick = fight.vegas_fighter_1_implied! >= fight.vegas_fighter_2_implied!
        ? fight.fighter_1_name : fight.fighter_2_name;
      vegasRight = vegasPick === fight.winner_name;
    }
  }

  // P&L
  let payout: number | null = null;
  if (hasBet && isComplete && fight.bet_decimal_odds) {
    const won = fight.bet_on === fight.winner_name;
    payout = won ? fight.bet_amount! * (fight.bet_decimal_odds - 1) : -fight.bet_amount!;
  }

  return (
    <Link to={`/fights/${fight.id}`}>
      <Card className="group transition-all hover:bg-accent/40 hover:border-border/80">
        <CardContent className="px-4 py-3">
          {/* Badges row */}
          {(fight.is_title_bout || (hasUpset && fight.upset_score! >= 30)) && (
            <div className="flex items-center gap-1.5 mb-2">
              {fight.is_title_bout && (
                <Badge variant="outline" className="border-yellow-500/40 text-yellow-500 text-[10px] px-1.5 py-0">
                  TITLE
                </Badge>
              )}
              {hasUpset && fight.upset_score! >= 30 && (
                <Badge
                  variant="outline"
                  className={cn(
                    'text-[10px] px-1.5 py-0',
                    fight.upset_score! >= 60
                      ? 'border-red-500/40 text-red-400'
                      : 'border-yellow-500/40 text-yellow-400'
                  )}
                >
                  UPSET {Math.round(fight.upset_score!)}
                </Badge>
              )}
            </div>
          )}

          {/* Result banner for completed fights */}
          {isComplete && (
            <div className="mb-2 flex items-center justify-between rounded-md bg-muted/50 px-2.5 py-1.5">
              <span className="text-xs text-muted-foreground">
                <span className="font-semibold text-foreground">{fight.winner_name}</span> wins
                {fight.method && <> by <span className="text-muted-foreground/80">{fight.method}</span></>}
              </span>
              <div className="flex items-center gap-2 text-[11px]">
                {aiRight !== null && (
                  <span className={cn('font-medium', aiRight ? 'text-green-400' : 'text-red-400')}>
                    AI {aiRight ? '\u2713' : '\u2717'}
                  </span>
                )}
                {vegasRight !== null && (
                  <span className={cn('font-medium', vegasRight ? 'text-green-400' : 'text-red-400')}>
                    Vegas {vegasRight ? '\u2713' : '\u2717'}
                  </span>
                )}
                {payout !== null && (
                  <span className={cn('font-semibold tabular-nums', payout >= 0 ? 'text-green-400' : 'text-red-400')}>
                    {payout >= 0 ? '+' : ''}${Math.abs(payout).toFixed(0)}
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Main matchup row */}
          <div className="flex items-center gap-3">
            {/* Fighter 1 */}
            <div className="flex-1 text-right">
              <div className={cn(
                'text-sm font-semibold leading-tight',
                isComplete && fight.winner_name === fight.fighter_1_name ? 'text-green-400' :
                isComplete ? 'text-muted-foreground/50' :
                hasPrediction && f1Favored ? 'text-foreground' : 'text-muted-foreground'
              )}>
                {fight.fighter_1_name}
              </div>
              {(f1Pct !== null || hasOdds) && (
                <div className="mt-1 flex items-center justify-end gap-2">
                  {f1Pct !== null && (
                    <span className="text-xs tabular-nums font-semibold text-blue-400">{f1Pct}%</span>
                  )}
                  {hasOdds && (
                    <span className="text-[10px] tabular-nums text-muted-foreground/50">
                      {fmtAmerican(fight.fighter_1_american!)}
                    </span>
                  )}
                </div>
              )}
            </div>

            {/* VS */}
            <div className="shrink-0 text-[10px] font-bold text-muted-foreground/40 uppercase">
              vs
            </div>

            {/* Fighter 2 */}
            <div className="flex-1">
              <div className={cn(
                'text-sm font-semibold leading-tight',
                isComplete && fight.winner_name === fight.fighter_2_name ? 'text-green-400' :
                isComplete ? 'text-muted-foreground/50' :
                hasPrediction && !f1Favored ? 'text-foreground' : 'text-muted-foreground'
              )}>
                {fight.fighter_2_name}
              </div>
              {(f2Pct !== null || hasOdds) && (
                <div className="mt-1 flex items-center gap-2">
                  {f2Pct !== null && (
                    <span className="text-xs tabular-nums font-semibold text-red-400">{f2Pct}%</span>
                  )}
                  {hasOdds && (
                    <span className="text-[10px] tabular-nums text-muted-foreground/50">
                      {fmtAmerican(fight.fighter_2_american!)}
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Probability bar */}
          {hasPrediction && (
            <div className="mt-2.5 flex h-1 overflow-hidden rounded-full bg-muted/50">
              <div className="bg-blue-500/80 transition-all" style={{ width: `${f1Pct}%` }} />
              <div className="bg-red-500/80 transition-all" style={{ width: `${f2Pct}%` }} />
            </div>
          )}

          {/* Footer row */}
          <div className="mt-2 flex items-center justify-between">
            <span className="text-[11px] text-muted-foreground/60">
              {fight.weight_class || 'Catchweight'}
            </span>

            <div className="flex items-center gap-2.5 text-[11px]">
              {hasBet && !isComplete && (
                <span className="text-muted-foreground/60">
                  ${fight.bet_amount} on {fight.bet_on}
                </span>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
