import { useQuery } from '@tanstack/react-query';
import { useState, useMemo } from 'react';
import { getValueBets } from '../api/predictions';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import type { ValueBet } from '../types';

function fmtAmerican(odds: number) {
  return odds > 0 ? `+${odds}` : `${odds}`;
}

function decimalToAmerican(decimal: number): number {
  if (decimal >= 2) return Math.round((decimal - 1) * 100);
  return Math.round(-100 / (decimal - 1));
}

export default function ParlayPage() {
  const { data: bets, isLoading } = useQuery({
    queryKey: ['value-bets'],
    queryFn: getValueBets,
  });

  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [stake, setStake] = useState(10);

  const toggle = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const legs = useMemo(
    () => (bets ?? []).filter((b) => selectedIds.has(b.fight_id)),
    [bets, selectedIds]
  );

  const parlayDecimalOdds = legs.reduce((acc, leg) => acc * leg.decimal_odds, 1);
  const parlayAmerican = legs.length >= 2 ? decimalToAmerican(parlayDecimalOdds) : 0;
  const payout = stake * parlayDecimalOdds;
  const profit = payout - stake;

  // Combined AI probability = product of individual AI probs
  const aiCombinedProb = legs.reduce((acc, leg) => acc * leg.ai_prob, 1);
  // Combined vegas implied = product of individual vegas implied
  const vegasCombinedProb = legs.reduce((acc, leg) => acc * leg.vegas_implied, 1);
  const parlayEdge = aiCombinedProb - (1 / parlayDecimalOdds);

  // Group bets by event
  const betsByEvent = useMemo(() => {
    if (!bets) return [];
    const map = new Map<string, ValueBet[]>();
    for (const bet of bets) {
      const key = bet.event_name;
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(bet);
    }
    return Array.from(map.entries());
  }, [bets]);

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Parlay Builder</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Combine value bets into parlays. Select 2+ fights to see combined odds and AI edge.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Fight picker */}
        <div className="lg:col-span-2 space-y-6">
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-16 w-full rounded-xl" />
              ))}
            </div>
          ) : !bets || bets.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center text-muted-foreground">
                No value bets available to build parlays from.
              </CardContent>
            </Card>
          ) : (
            betsByEvent.map(([eventName, eventBets]) => (
              <div key={eventName}>
                <h3 className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  {eventName}
                </h3>
                <div className="space-y-2">
                  {eventBets.map((bet) => {
                    const selected = selectedIds.has(bet.fight_id);
                    return (
                      <button
                        key={bet.fight_id}
                        onClick={() => toggle(bet.fight_id)}
                        className={cn(
                          'w-full rounded-lg border p-3 text-left transition-all',
                          selected
                            ? 'border-green-500/50 bg-green-500/10 ring-1 ring-green-500/20'
                            : 'border-border hover:border-border/80 hover:bg-accent/30'
                        )}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <div
                              className={cn(
                                'flex h-5 w-5 shrink-0 items-center justify-center rounded border transition-colors',
                                selected
                                  ? 'border-green-500 bg-green-500 text-black'
                                  : 'border-muted-foreground/30'
                              )}
                            >
                              {selected && (
                                <svg className="h-3 w-3" viewBox="0 0 12 12" fill="none">
                                  <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                                </svg>
                              )}
                            </div>
                            <div>
                              <div className="text-sm font-medium">
                                {bet.fighter_1_name} vs {bet.fighter_2_name}
                              </div>
                              <div className="mt-0.5 text-xs text-muted-foreground">
                                Bet on <span className="text-green-400 font-medium">{bet.bet_on}</span>
                                {' '}at {fmtAmerican(bet.american_odds)}
                              </div>
                            </div>
                          </div>
                          <div className="text-right">
                            <Badge
                              variant="outline"
                              className={cn(
                                'tabular-nums',
                                bet.edge >= 0.15
                                  ? 'border-green-500/50 text-green-400'
                                  : bet.edge >= 0.08
                                    ? 'border-green-500/30 text-green-400/70'
                                    : 'text-muted-foreground'
                              )}
                            >
                              +{(bet.edge * 100).toFixed(1)}% edge
                            </Badge>
                            <div className="mt-1 text-xs tabular-nums text-muted-foreground">
                              AI: {(bet.ai_prob * 100).toFixed(0)}% &middot; Vegas: {(bet.vegas_implied * 100).toFixed(0)}%
                            </div>
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Parlay slip */}
        <div>
          <div className="sticky top-20 space-y-4">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center justify-between text-base">
                  Parlay Slip
                  {legs.length > 0 && (
                    <Badge variant="outline" className="text-[10px] px-1.5">
                      {legs.length} leg{legs.length !== 1 ? 's' : ''}
                    </Badge>
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {legs.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    Select 2 or more fights to build a parlay.
                  </p>
                ) : (
                  <>
                    {/* Legs */}
                    <div className="space-y-2">
                      {legs.map((leg) => (
                        <div
                          key={leg.fight_id}
                          className="flex items-center justify-between rounded-md border border-border px-3 py-2"
                        >
                          <div>
                            <div className="text-xs font-medium">{leg.bet_on}</div>
                            <div className="text-[10px] text-muted-foreground">
                              vs {leg.bet_on === leg.fighter_1_name ? leg.fighter_2_name : leg.fighter_1_name}
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs tabular-nums text-muted-foreground">
                              {fmtAmerican(leg.american_odds)}
                            </span>
                            <button
                              onClick={() => toggle(leg.fight_id)}
                              className="text-muted-foreground hover:text-foreground transition-colors"
                            >
                              <svg className="h-3.5 w-3.5" viewBox="0 0 14 14" fill="none">
                                <path d="M3 3l8 8M11 3l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                              </svg>
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* Stake input */}
                    <div>
                      <label className="text-xs font-medium text-muted-foreground">Stake</label>
                      <div className="mt-1 flex items-center gap-2">
                        <span className="text-sm text-muted-foreground">$</span>
                        <input
                          type="number"
                          min={1}
                          value={stake}
                          onChange={(e) => setStake(Math.max(1, Number(e.target.value)))}
                          className="w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm tabular-nums outline-none focus:ring-1 focus:ring-ring"
                        />
                      </div>
                      <div className="mt-2 flex gap-1.5">
                        {[5, 10, 25, 50, 100].map((amount) => (
                          <button
                            key={amount}
                            onClick={() => setStake(amount)}
                            className={cn(
                              'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
                              stake === amount
                                ? 'bg-accent text-accent-foreground'
                                : 'text-muted-foreground hover:text-foreground hover:bg-accent/50'
                            )}
                          >
                            ${amount}
                          </button>
                        ))}
                      </div>
                    </div>

                    {legs.length >= 2 && (
                      <>
                        {/* Odds breakdown */}
                        <div className="space-y-2 border-t border-border pt-4">
                          <div className="flex justify-between text-xs">
                            <span className="text-muted-foreground">Parlay Odds</span>
                            <span className="font-medium tabular-nums">
                              {fmtAmerican(parlayAmerican)} ({parlayDecimalOdds.toFixed(2)}x)
                            </span>
                          </div>
                          <div className="flex justify-between text-xs">
                            <span className="text-muted-foreground">AI Win Prob</span>
                            <span className="font-medium tabular-nums">
                              {(aiCombinedProb * 100).toFixed(1)}%
                            </span>
                          </div>
                          <div className="flex justify-between text-xs">
                            <span className="text-muted-foreground">Vegas Implied</span>
                            <span className="font-medium tabular-nums">
                              {(vegasCombinedProb * 100).toFixed(1)}%
                            </span>
                          </div>
                          <div className="flex justify-between text-xs">
                            <span className="text-muted-foreground">Parlay Edge</span>
                            <span
                              className={cn(
                                'font-medium tabular-nums',
                                parlayEdge > 0 ? 'text-green-400' : 'text-red-400'
                              )}
                            >
                              {parlayEdge > 0 ? '+' : ''}{(parlayEdge * 100).toFixed(1)}%
                            </span>
                          </div>
                        </div>

                        {/* Payout */}
                        <div className="rounded-lg bg-accent/50 p-3 space-y-1">
                          <div className="flex justify-between text-xs text-muted-foreground">
                            <span>Stake</span>
                            <span className="tabular-nums">${stake.toFixed(2)}</span>
                          </div>
                          <div className="flex justify-between text-sm font-bold">
                            <span>Payout</span>
                            <span className="tabular-nums text-green-400">
                              ${payout.toFixed(2)}
                            </span>
                          </div>
                          <div className="flex justify-between text-xs text-green-400/70">
                            <span>Profit</span>
                            <span className="tabular-nums">+${profit.toFixed(2)}</span>
                          </div>
                        </div>

                        {parlayEdge > 0 && (
                          <p className="text-[10px] text-green-400/60 text-center">
                            AI sees +{(parlayEdge * 100).toFixed(1)}% edge on this parlay
                          </p>
                        )}
                        {parlayEdge <= 0 && (
                          <p className="text-[10px] text-red-400/60 text-center">
                            AI sees negative edge — individual legs have value but combined probability is low
                          </p>
                        )}
                      </>
                    )}

                    {legs.length === 1 && (
                      <p className="text-xs text-muted-foreground text-center pt-2">
                        Add at least one more fight for a parlay.
                      </p>
                    )}
                  </>
                )}
              </CardContent>
            </Card>

            {/* Quick actions */}
            {bets && bets.length >= 2 && (
              <div className="flex gap-2">
                <button
                  onClick={() => setSelectedIds(new Set(bets.map((b) => b.fight_id)))}
                  className="flex-1 rounded-md border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
                >
                  Select All
                </button>
                <button
                  onClick={() => setSelectedIds(new Set())}
                  className="flex-1 rounded-md border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
                >
                  Clear All
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
