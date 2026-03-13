import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import api from '../api/client';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { cn } from '@/lib/utils';

interface BucketStat {
  bucket: string;
  count: number;
  accuracy: number;
  avg_confidence: number;
}

interface MethodStat {
  method: string;
  count: number;
  accuracy: number;
}

interface BetInfo {
  bet_on: string;
  bet_amount: number;
  decimal_odds: number;
  edge: number;
  won: boolean;
  payout: number;
}

interface FightResult {
  fight_id: number;
  fighter_1_name: string;
  fighter_2_name: string;
  event_name: string;
  fighter_1_prob: number;
  fighter_2_prob: number;
  predicted_winner: string;
  actual_winner: string | null;
  correct: boolean;
  confidence: number;
  method: string;
  vegas_pick: string | null;
  vegas_correct: boolean | null;
  bet: BetInfo | null;
}

interface BettingStats {
  starting_bankroll: number;
  final_bankroll: number;
  total_profit: number;
  total_wagered: number;
  roi: number | null;
  bets_placed: number;
  bets_won: number;
  bets_lost: number;
  win_rate: number | null;
  history: { fight_id: number; bankroll: number; profit: number }[];
}

interface PerformanceData {
  test_size: number;
  accuracy: number;
  vegas_baseline: number | null;
  vegas_sample_size: number;
  bucket_stats: BucketStat[];
  method_stats: MethodStat[];
  recent_fights: FightResult[];
  betting: BettingStats;
}

async function getPerformance() {
  const { data } = await api.get<PerformanceData>('/performance');
  return data;
}

export default function PerformancePage() {
  const { data, isLoading } = useQuery({
    queryKey: ['performance'],
    queryFn: getPerformance,
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-[88px] rounded-xl" />
          ))}
        </div>
        <Skeleton className="h-64 rounded-xl" />
      </div>
    );
  }

  if (!data) {
    return <div className="py-12 text-center text-muted-foreground">Could not load performance data.</div>;
  }

  const hasVegas = data.vegas_baseline !== null;
  const edgeVsVegas = hasVegas ? ((data.accuracy - data.vegas_baseline!) * 100).toFixed(1) : null;
  const isBeatingVegas = hasVegas && data.accuracy > data.vegas_baseline!;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Model Performance</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Evaluated on {data.test_size} held-out test fights (most recent 15% of the dataset, never seen during training).
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Card>
          <CardContent className="p-4">
            <p className="text-xs font-medium text-muted-foreground">AI Accuracy</p>
            <p className="mt-1 text-3xl font-black tabular-nums text-blue-400">
              {(data.accuracy * 100).toFixed(1)}%
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-xs font-medium text-muted-foreground">Vegas Accuracy</p>
            {hasVegas ? (
              <>
                <p className="mt-1 text-3xl font-black tabular-nums text-muted-foreground">
                  {(data.vegas_baseline! * 100).toFixed(1)}%
                </p>
                <p className="text-[10px] text-muted-foreground/60">
                  {data.vegas_sample_size} fights with odds
                </p>
              </>
            ) : (
              <p className="mt-1 text-sm text-muted-foreground">No odds data</p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-xs font-medium text-muted-foreground">Edge vs Vegas</p>
            {hasVegas ? (
              <p className={cn(
                'mt-1 text-3xl font-black tabular-nums',
                isBeatingVegas ? 'text-green-400' : 'text-red-400'
              )}>
                {isBeatingVegas ? '+' : ''}{edgeVsVegas}%
              </p>
            ) : (
              <p className="mt-1 text-sm text-muted-foreground">--</p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-xs font-medium text-muted-foreground">Test Fights</p>
            <p className="mt-1 text-3xl font-black tabular-nums">{data.test_size}</p>
          </CardContent>
        </Card>
      </div>

      {/* Betting Simulation */}
      {data.betting.bets_placed > 0 && (() => {
        const b = data.betting;
        const profitable = b.total_profit > 0;
        return (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Value Betting Simulation
              </CardTitle>
              <p className="text-[10px] text-muted-foreground/60">
                Starting with ${b.starting_bankroll.toLocaleString()} bankroll. Bets sized by edge — bigger edge = bigger bet. Only bets when AI sees 3%+ edge over Vegas odds.
              </p>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
                <div>
                  <p className="text-[10px] font-medium text-muted-foreground">P&L</p>
                  <p className={cn(
                    'text-2xl font-black tabular-nums',
                    profitable ? 'text-green-400' : 'text-red-400'
                  )}>
                    {profitable ? '+' : ''}{b.total_profit < 0 ? '-' : ''}${Math.abs(b.total_profit).toLocaleString()}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] font-medium text-muted-foreground">ROI</p>
                  <p className={cn(
                    'text-2xl font-black tabular-nums',
                    profitable ? 'text-green-400' : 'text-red-400'
                  )}>
                    {b.roi !== null ? `${profitable ? '+' : ''}${b.roi}%` : '--'}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] font-medium text-muted-foreground">Final Bankroll</p>
                  <p className="text-2xl font-black tabular-nums">
                    ${b.final_bankroll.toLocaleString()}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] font-medium text-muted-foreground">Record</p>
                  <p className="text-2xl font-black tabular-nums">
                    <span className="text-green-400">{b.bets_won}</span>
                    <span className="text-muted-foreground">-</span>
                    <span className="text-red-400">{b.bets_lost}</span>
                  </p>
                </div>
                <div>
                  <p className="text-[10px] font-medium text-muted-foreground">Total Wagered</p>
                  <p className="text-2xl font-black tabular-nums text-muted-foreground">
                    ${b.total_wagered.toLocaleString()}
                  </p>
                </div>
              </div>

              {/* Bankroll curve */}
              {b.history.length > 1 && (
                <div className="mt-4">
                  <p className="mb-2 text-[10px] font-medium text-muted-foreground">Bankroll Over Time</p>
                  <div className="relative h-24 w-full overflow-hidden rounded-lg bg-muted/30">
                    {(() => {
                      const vals = [b.starting_bankroll, ...b.history.map(h => h.bankroll)];
                      const min = Math.min(...vals);
                      const max = Math.max(...vals);
                      const range = max - min || 1;
                      const points = vals.map((v, i) => {
                        const x = (i / (vals.length - 1)) * 100;
                        const y = 100 - ((v - min) / range) * 80 - 10;
                        return `${x},${y}`;
                      }).join(' ');
                      const lastVal = vals[vals.length - 1];
                      const color = lastVal >= b.starting_bankroll ? '#4ade80' : '#f87171';
                      return (
                        <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="h-full w-full">
                          <polyline
                            fill="none"
                            stroke={color}
                            strokeWidth="1.5"
                            vectorEffect="non-scaling-stroke"
                            points={points}
                          />
                          {/* Starting line */}
                          <line
                            x1="0"
                            y1={100 - ((b.starting_bankroll - min) / range) * 80 - 10}
                            x2="100"
                            y2={100 - ((b.starting_bankroll - min) / range) * 80 - 10}
                            stroke="#666"
                            strokeWidth="0.5"
                            strokeDasharray="2,2"
                            vectorEffect="non-scaling-stroke"
                          />
                        </svg>
                      );
                    })()}
                  </div>
                  <div className="mt-1 flex justify-between text-[10px] text-muted-foreground/60">
                    <span>First bet</span>
                    <span>Latest bet ({b.bets_placed} bets)</span>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        );
      })()}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Accuracy by Confidence */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Accuracy by Confidence Level
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {data.bucket_stats.map((bucket) => {
                const pct = Math.round(bucket.accuracy * 100);
                return (
                  <div key={bucket.bucket} className="space-y-1">
                    <div className="flex justify-between text-sm">
                      <span className="font-medium">{bucket.bucket}</span>
                      <span className="tabular-nums text-muted-foreground">
                        {pct}% ({bucket.count} fights)
                      </span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-muted">
                      <div
                        className={cn(
                          'h-full rounded-full transition-all',
                          pct >= 65 ? 'bg-green-500' : pct >= 55 ? 'bg-blue-500' : 'bg-yellow-500'
                        )}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
            <p className="mt-4 text-[10px] text-muted-foreground/60">
              A well-calibrated model should be more accurate when it's more confident.
            </p>
          </CardContent>
        </Card>

        {/* Accuracy by Method */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Accuracy by Fight Outcome
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {data.method_stats.map((method) => {
                const pct = Math.round(method.accuracy * 100);
                const colors: Record<string, string> = {
                  'KO/TKO': 'bg-red-500',
                  'Submission': 'bg-blue-500',
                  'Decision': 'bg-purple-500',
                };
                return (
                  <div key={method.method} className="space-y-1">
                    <div className="flex justify-between text-sm">
                      <span className="font-medium">{method.method}</span>
                      <span className="tabular-nums text-muted-foreground">
                        {pct}% ({method.count} fights)
                      </span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-muted">
                      <div
                        className={`h-full rounded-full transition-all ${colors[method.method] || 'bg-muted-foreground'}`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
            <p className="mt-4 text-[10px] text-muted-foreground/60">
              KO/TKO fights are hardest to predict due to the inherent randomness of knockouts.
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Recent Fight Results */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            Recent Test Set Predictions
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Fight</TableHead>
                <TableHead>Event</TableHead>
                <TableHead className="text-right">AI Pick</TableHead>
                <TableHead className="text-right">AI</TableHead>
                <TableHead className="text-right">Vegas</TableHead>
                <TableHead className="text-right">Bet</TableHead>
                <TableHead className="text-right">P&L</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.recent_fights.map((fight) => (
                <TableRow key={fight.fight_id}>
                  <TableCell>
                    <Link
                      to={`/fights/${fight.fight_id}`}
                      className="font-medium transition-colors hover:text-blue-400"
                    >
                      {fight.fighter_1_name} vs {fight.fighter_2_name}
                    </Link>
                  </TableCell>
                  <TableCell className="text-muted-foreground text-xs">
                    {fight.event_name}
                  </TableCell>
                  <TableCell className="text-right text-sm">
                    {fight.predicted_winner}
                  </TableCell>
                  <TableCell className="text-right">
                    <Badge
                      variant={fight.correct ? 'default' : 'destructive'}
                      className={cn(
                        'text-[10px]',
                        fight.correct && 'bg-green-500/20 text-green-400 border-green-500/30'
                      )}
                    >
                      {fight.correct ? '\u2713' : '\u2717'}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    {fight.vegas_correct !== null ? (
                      <Badge
                        variant={fight.vegas_correct ? 'default' : 'destructive'}
                        className={cn(
                          'text-[10px]',
                          fight.vegas_correct && 'bg-green-500/20 text-green-400 border-green-500/30'
                        )}
                      >
                        {fight.vegas_correct ? '\u2713' : '\u2717'}
                      </Badge>
                    ) : (
                      <span className="text-[10px] text-muted-foreground">--</span>
                    )}
                  </TableCell>
                  <TableCell className="text-right text-xs tabular-nums">
                    {fight.bet ? (
                      <span className="text-muted-foreground">
                        ${fight.bet.bet_amount} @ {fight.bet.decimal_odds}x
                      </span>
                    ) : (
                      <span className="text-muted-foreground/40">--</span>
                    )}
                  </TableCell>
                  <TableCell className="text-right text-xs tabular-nums font-medium">
                    {fight.bet ? (
                      <span className={fight.bet.won ? 'text-green-400' : 'text-red-400'}>
                        {fight.bet.payout >= 0 ? '+' : ''}{fight.bet.payout < 0 ? '-' : ''}${Math.abs(fight.bet.payout).toFixed(0)}
                      </span>
                    ) : (
                      <span className="text-muted-foreground/40">--</span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
