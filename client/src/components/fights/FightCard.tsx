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

  return (
    <Link to={`/fights/${fight.id}`}>
      <Card className="transition-colors hover:bg-accent/50">
        <CardContent className="p-4">
          {/* Top badges */}
          <div className="flex items-center gap-2 mb-2">
            {fight.is_title_bout && (
              <Badge variant="outline" className="border-yellow-500/50 text-yellow-500 text-[10px]">
                TITLE BOUT
              </Badge>
            )}
            {hasUpset && fight.upset_score! >= 30 && (
              <Badge
                variant="outline"
                className={cn(
                  'text-[10px]',
                  fight.upset_score! >= 60
                    ? 'border-red-500/50 text-red-400'
                    : 'border-yellow-500/50 text-yellow-400'
                )}
              >
                UPSET {Math.round(fight.upset_score!)}
              </Badge>
            )}
          </div>

          <div className="flex items-center">
            {/* Fighter 1 */}
            <div className="flex-1 text-right pr-3">
              <span className={`font-semibold ${hasPrediction && f1Favored ? 'text-foreground' : 'text-muted-foreground'}`}>
                {fight.fighter_1_name}
              </span>
              <div className="mt-0.5 flex items-center justify-end gap-2">
                {f1Pct !== null && (
                  <span className="text-xs text-blue-400 font-medium">{f1Pct}%</span>
                )}
                {hasOdds && (
                  <span className="text-[10px] text-muted-foreground/60 tabular-nums">
                    {fmtAmerican(fight.fighter_1_american!)}
                  </span>
                )}
              </div>
            </div>

            {/* VS divider */}
            <div className="shrink-0 rounded-full bg-muted px-2.5 py-1 text-[10px] font-bold text-muted-foreground">
              VS
            </div>

            {/* Fighter 2 */}
            <div className="flex-1 pl-3">
              <span className={`font-semibold ${hasPrediction && !f1Favored ? 'text-foreground' : 'text-muted-foreground'}`}>
                {fight.fighter_2_name}
              </span>
              <div className="mt-0.5 flex items-center gap-2">
                {f2Pct !== null && (
                  <span className="text-xs text-red-400 font-medium">{f2Pct}%</span>
                )}
                {hasOdds && (
                  <span className="text-[10px] text-muted-foreground/60 tabular-nums">
                    {fmtAmerican(fight.fighter_2_american!)}
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Probability bar */}
          {hasPrediction && (
            <div className="mt-3 flex h-1.5 overflow-hidden rounded-full bg-muted">
              <div
                className="bg-blue-500 transition-all"
                style={{ width: `${f1Pct}%` }}
              />
              <div
                className="bg-red-500 transition-all"
                style={{ width: `${f2Pct}%` }}
              />
            </div>
          )}

          {/* Bottom row: weight class, bet info, result */}
          <div className="mt-2 flex justify-between text-xs text-muted-foreground">
            <span>{fight.weight_class || 'Catchweight'}</span>

            <div className="flex items-center gap-3">
              {/* Value bet + P&L */}
              {hasBet && (() => {
                const won = fight.winner_name ? fight.bet_on === fight.winner_name : null;
                const payout = won !== null && fight.bet_decimal_odds
                  ? (won ? fight.bet_amount! * (fight.bet_decimal_odds - 1) : -fight.bet_amount!)
                  : null;
                return (
                  <span className="flex items-center gap-1.5">
                    <span className="text-muted-foreground/80">
                      ${fight.bet_amount} on {fight.bet_on}
                    </span>
                    {payout !== null && (
                      <span className={cn('font-medium', payout >= 0 ? 'text-green-400' : 'text-red-400')}>
                        {payout >= 0 ? '+' : '-'}${Math.abs(payout).toFixed(0)}
                      </span>
                    )}
                  </span>
                );
              })()}

              {/* AI/Vegas correct indicators for past fights */}
              {fight.winner_name && hasPrediction && (() => {
                const aiPick = fight.fighter_1_win_prob! >= 0.5 ? fight.fighter_1_name : fight.fighter_2_name;
                const aiRight = aiPick === fight.winner_name;
                const hasVegas = fight.vegas_fighter_1_implied != null && fight.vegas_fighter_2_implied != null;
                const vegasPick = hasVegas
                  ? (fight.vegas_fighter_1_implied! >= fight.vegas_fighter_2_implied! ? fight.fighter_1_name : fight.fighter_2_name)
                  : null;
                const vegasRight = vegasPick === fight.winner_name;
                return (
                  <>
                    <span className={aiRight ? 'text-green-400' : 'text-red-400'}>
                      AI {aiRight ? '\u2713' : '\u2717'}
                    </span>
                    {hasVegas && (
                      <span className={vegasRight ? 'text-green-400' : 'text-red-400'}>
                        Vegas {vegasRight ? '\u2713' : '\u2717'}
                      </span>
                    )}
                  </>
                );
              })()}

              {fight.winner_name && (
                <span>W: {fight.winner_name}</span>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
