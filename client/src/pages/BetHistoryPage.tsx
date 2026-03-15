import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { getBetHistory } from '../api/predictions';
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

export default function BetHistoryPage() {
  const { data: bets, isLoading } = useQuery({
    queryKey: ['bet-history'],
    queryFn: getBetHistory,
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-16 w-full rounded-xl" />
        <Skeleton className="h-32 w-full rounded-xl" />
        <Skeleton className="h-64 w-full rounded-xl" />
      </div>
    );
  }

  if (!bets || bets.length === 0) {
    return (
      <div className="py-12 text-center text-muted-foreground">
        No bet history yet. Value bets will appear here once predictions and odds are available.
      </div>
    );
  }

  const settled = bets.filter((b) => b.won !== null);
  const wins = settled.filter((b) => b.won === true).length;
  const losses = settled.filter((b) => b.won === false).length;
  const totalWagered = bets.reduce((sum, b) => sum + b.bet_amount, 0);
  const totalPnl = settled.reduce((sum, b) => sum + (b.payout ?? 0), 0);
  const roi = totalWagered > 0 ? (totalPnl / totalWagered) * 100 : 0;
  const profitable = totalPnl >= 0;

  // Cumulative P&L for chart (chronological order = reversed since bets are newest first)
  const chronological = [...bets].reverse();
  const cumulativePnl: number[] = [];
  let running = 0;
  for (const b of chronological) {
    if (b.payout !== null) {
      running += b.payout;
    }
    cumulativePnl.push(running);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Bet History</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          All value bets placed by the AI model, with outcomes and P&L tracking.
        </p>
      </div>

      {/* Summary stats bar */}
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3 rounded-lg border border-border bg-card px-5 py-4 text-sm">
        <Stat label="Total Bets" value={bets.length} />
        <Stat
          label="Record"
          value={
            <span>
              <span className="text-green-400">{wins}</span>
              <span className="text-muted-foreground">-</span>
              <span className="text-red-400">{losses}</span>
              {bets.length - settled.length > 0 && (
                <span className="text-muted-foreground/50 ml-1 text-xs">
                  ({bets.length - settled.length} pending)
                </span>
              )}
            </span>
          }
        />
        <div className="h-5 w-px bg-border" />
        <Stat label="Total Wagered" value={`$${Math.round(totalWagered).toLocaleString()}`} />
        <Stat
          label="P&L"
          value={`${profitable ? '+' : '-'}$${Math.abs(Math.round(totalPnl)).toLocaleString()}`}
          color={profitable ? 'text-green-400' : 'text-red-400'}
        />
        <Stat
          label="ROI"
          value={`${roi >= 0 ? '+' : ''}${roi.toFixed(1)}%`}
          color={profitable ? 'text-green-400' : 'text-red-400'}
        />
      </div>

      {/* Cumulative P&L Chart */}
      {settled.length > 1 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Cumulative P&L
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="relative h-28 w-full overflow-hidden rounded-lg bg-muted/30">
              {(() => {
                const vals = [0, ...cumulativePnl];
                const min = Math.min(...vals);
                const max = Math.max(...vals);
                const range = max - min || 1;
                const points = vals
                  .map((v, i) => {
                    const x = (i / (vals.length - 1)) * 100;
                    const y = 100 - ((v - min) / range) * 80 - 10;
                    return `${x},${y}`;
                  })
                  .join(' ');
                const lastVal = vals[vals.length - 1];
                const color = lastVal >= 0 ? '#4ade80' : '#f87171';
                // Zero line
                const zeroY = 100 - ((0 - min) / range) * 80 - 10;
                return (
                  <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="h-full w-full">
                    <line
                      x1="0"
                      y1={zeroY}
                      x2="100"
                      y2={zeroY}
                      stroke="#666"
                      strokeWidth="0.5"
                      strokeDasharray="2,2"
                      vectorEffect="non-scaling-stroke"
                    />
                    <polyline
                      fill="none"
                      stroke={color}
                      strokeWidth="1.5"
                      vectorEffect="non-scaling-stroke"
                      points={points}
                    />
                  </svg>
                );
              })()}
            </div>
            <div className="mt-1 flex justify-between text-[10px] text-muted-foreground/60">
              <span>First bet</span>
              <span>Latest ({settled.length} settled)</span>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Bet Table */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            All Bets
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Fight</TableHead>
                <TableHead>Event</TableHead>
                <TableHead>Bet On</TableHead>
                <TableHead className="text-right">Odds</TableHead>
                <TableHead className="text-right">Edge</TableHead>
                <TableHead className="text-right">Bet</TableHead>
                <TableHead className="text-right">Result</TableHead>
                <TableHead className="text-right">P&L</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {bets.map((bet) => {
                const isPending = bet.won === null;
                return (
                  <TableRow key={bet.fight_id} className={cn(isPending && 'opacity-60')}>
                    <TableCell>
                      <Link
                        to={`/fights/${bet.fight_id}`}
                        className="font-medium transition-colors hover:text-blue-400"
                      >
                        {bet.fighter_1_name} vs {bet.fighter_2_name}
                      </Link>
                      {bet.weight_class && (
                        <span className="ml-1.5 text-[10px] text-muted-foreground/50">
                          {bet.weight_class}
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {bet.event_name}
                    </TableCell>
                    <TableCell className="text-sm">{bet.bet_on}</TableCell>
                    <TableCell className="text-right text-xs tabular-nums text-muted-foreground">
                      {bet.american_odds > 0 ? '+' : ''}
                      {bet.american_odds}
                    </TableCell>
                    <TableCell className="text-right">
                      <Badge
                        variant="outline"
                        className="text-[10px] tabular-nums border-blue-500/30 text-blue-400"
                      >
                        +{(bet.edge * 100).toFixed(1)}%
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right text-xs tabular-nums">
                      ${bet.bet_amount.toFixed(0)}
                    </TableCell>
                    <TableCell className="text-right">
                      {isPending ? (
                        <Badge
                          variant="outline"
                          className="text-[10px] border-muted-foreground/30 text-muted-foreground"
                        >
                          Pending
                        </Badge>
                      ) : bet.won ? (
                        <Badge className="bg-green-500/20 text-green-400 border-green-500/30 text-[10px]">
                          Won
                        </Badge>
                      ) : (
                        <Badge variant="destructive" className="text-[10px]">
                          Lost
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-right text-xs tabular-nums font-medium">
                      {isPending ? (
                        <span className="text-muted-foreground/40">--</span>
                      ) : (
                        <span className={bet.won ? 'text-green-400' : 'text-red-400'}>
                          {bet.payout! >= 0 ? '+' : '-'}${Math.abs(bet.payout!).toFixed(0)}
                        </span>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}

function Stat({
  label,
  value,
  color,
}: {
  label: string;
  value: string | number | React.ReactNode;
  color?: string;
}) {
  return (
    <div className="flex items-baseline gap-2">
      <span className="text-muted-foreground/60 text-xs">{label}</span>
      <span className={cn('text-base font-bold tabular-nums', color)}>{value}</span>
    </div>
  );
}
