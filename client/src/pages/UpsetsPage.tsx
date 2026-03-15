import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { getValueBets } from '../api/predictions';
import { Card, CardContent } from '@/components/ui/card';
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

function fmtAmerican(odds: number) {
  return odds > 0 ? `+${odds}` : `${odds}`;
}

export default function UpsetsPage() {
  const { data: bets, isLoading, isError, error } = useQuery({
    queryKey: ['value-bets'],
    queryFn: getValueBets,
  });

  const totalWagered = bets?.reduce((s, b) => s + b.bet_amount, 0) ?? 0;
  const totalPotential = bets?.reduce((s, b) => s + b.bet_amount * (b.decimal_odds - 1), 0) ?? 0;

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Value Bets</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Fights where the AI sees edge over Vegas. Bet size scales with edge — bigger disagreement = bigger bet.
        </p>
      </div>

      {/* Summary cards */}
      {bets && bets.length > 0 && (
        <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Card>
            <CardContent className="p-4">
              <p className="text-xs font-medium text-muted-foreground">Value Bets</p>
              <p className="mt-1 text-2xl font-bold tabular-nums">{bets.length}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <p className="text-xs font-medium text-muted-foreground">Total Wagered</p>
              <p className="mt-1 text-2xl font-bold tabular-nums">${Math.round(totalWagered).toLocaleString()}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <p className="text-xs font-medium text-muted-foreground">Avg Edge</p>
              <p className="mt-1 text-2xl font-bold tabular-nums text-green-400">
                +{(bets.reduce((s, b) => s + b.edge, 0) / bets.length * 100).toFixed(1)}%
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <p className="text-xs font-medium text-muted-foreground">Max Potential</p>
              <p className="mt-1 text-2xl font-bold tabular-nums text-green-400">
                +${Math.round(totalPotential).toLocaleString()}
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      ) : isError ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-sm text-red-400">Failed to load value bets.</p>
            <p className="mt-1 text-xs text-muted-foreground/60">
              {error instanceof Error ? error.message : 'Unknown error'}
            </p>
          </CardContent>
        </Card>
      ) : !bets || bets.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            No value bets right now. Check back when upcoming fights have predictions and odds.
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Fight</TableHead>
                  <TableHead>Event</TableHead>
                  <TableHead className="text-right">Bet On</TableHead>
                  <TableHead className="text-right">Odds</TableHead>
                  <TableHead className="text-right">Edge</TableHead>
                  <TableHead className="text-right">Bet</TableHead>
                  <TableHead className="text-right">Potential</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {bets.map((bet) => {
                  const potential = bet.bet_amount * (bet.decimal_odds - 1);
                  return (
                    <TableRow key={bet.fight_id}>
                      <TableCell>
                        <Link
                          to={`/fights/${bet.fight_id}`}
                          className="font-medium transition-colors hover:text-blue-400"
                        >
                          {bet.fighter_1_name} vs {bet.fighter_2_name}
                        </Link>
                      </TableCell>
                      <TableCell className="text-muted-foreground text-xs">
                        {bet.event_name}
                      </TableCell>
                      <TableCell className="text-right">
                        <span className="font-medium text-green-400">{bet.bet_on}</span>
                      </TableCell>
                      <TableCell className="text-right tabular-nums text-muted-foreground">
                        {fmtAmerican(bet.american_odds)}
                      </TableCell>
                      <TableCell className="text-right">
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
                          +{(bet.edge * 100).toFixed(1)}%
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right tabular-nums font-medium">
                        ${Math.round(bet.bet_amount)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums text-green-400/70">
                        +${Math.round(potential)}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
