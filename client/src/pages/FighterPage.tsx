import { useQuery } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { getFighterProfile } from '../api/predictions';
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

function formatHeight(inches: number | null) {
  if (!inches) return '--';
  return `${Math.floor(inches / 12)}'${inches % 12}"`;
}

function calcAge(dob: string | null) {
  if (!dob) return null;
  const birth = new Date(dob);
  const today = new Date();
  let age = today.getFullYear() - birth.getFullYear();
  if (today.getMonth() < birth.getMonth() ||
    (today.getMonth() === birth.getMonth() && today.getDate() < birth.getDate())) {
    age--;
  }
  return age;
}

function formatControlTime(seconds: number) {
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}

export default function FighterPage() {
  const { id } = useParams<{ id: string }>();
  const fighterId = Number(id);

  const { data: fighter, isLoading } = useQuery({
    queryKey: ['fighter-profile', fighterId],
    queryFn: () => getFighterProfile(fighterId),
    enabled: !isNaN(fighterId),
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-6 w-48" />
        <div className="grid grid-cols-3 gap-4 mt-6">
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
        </div>
        <Skeleton className="h-64 mt-6" />
      </div>
    );
  }

  if (!fighter) {
    return <div className="py-12 text-center text-muted-foreground">Fighter not found.</div>;
  }

  const age = calcAge(fighter.dob);
  const totalFights = fighter.wins + fighter.losses + fighter.draws;

  return (
    <div>
      <Link
        to="/"
        className="mb-4 inline-flex items-center gap-1 text-xs text-muted-foreground/60 transition-colors hover:text-foreground"
      >
        &larr; Back
      </Link>

      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold">{fighter.name}</h1>
        {fighter.nickname && (
          <p className="mt-0.5 text-sm text-muted-foreground/60">"{fighter.nickname}"</p>
        )}
      </div>

      {/* Physical stats + Record */}
      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* Record */}
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-[10px] font-medium text-muted-foreground/60 uppercase tracking-wider">Record</p>
            <p className="mt-1 text-2xl font-black tabular-nums">
              <span className="text-green-400">{fighter.wins}</span>
              <span className="text-muted-foreground/40">-</span>
              <span className="text-red-400">{fighter.losses}</span>
              {fighter.draws > 0 && (
                <>
                  <span className="text-muted-foreground/40">-</span>
                  <span className="text-muted-foreground">{fighter.draws}</span>
                </>
              )}
            </p>
            <div className="mt-2 flex justify-center gap-3 text-[10px] text-muted-foreground/60">
              <span>KO {fighter.ko_wins}</span>
              <span>SUB {fighter.sub_wins}</span>
              <span>DEC {fighter.dec_wins}</span>
            </div>
          </CardContent>
        </Card>

        {/* Physical */}
        <Card>
          <CardContent className="p-4">
            <p className="text-[10px] font-medium text-muted-foreground/60 uppercase tracking-wider mb-2">Physical</p>
            <div className="space-y-1.5 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground/60 text-xs">Height</span>
                <span className="font-medium tabular-nums">{formatHeight(fighter.height_inches)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground/60 text-xs">Reach</span>
                <span className="font-medium tabular-nums">{fighter.reach_inches ? `${fighter.reach_inches}"` : '--'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground/60 text-xs">Age</span>
                <span className="font-medium tabular-nums">{age ?? '--'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground/60 text-xs">Stance</span>
                <span className="font-medium">{fighter.stance || '--'}</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Career averages */}
        <Card className="sm:col-span-2">
          <CardContent className="p-4">
            <p className="text-[10px] font-medium text-muted-foreground/60 uppercase tracking-wider mb-2">
              Per Fight Averages ({totalFights} fights)
            </p>
            <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground/60 text-xs">Sig. Strikes</span>
                <span className="font-medium tabular-nums">{fighter.avg_sig_strikes}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground/60 text-xs">Takedowns</span>
                <span className="font-medium tabular-nums">{fighter.avg_takedowns}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground/60 text-xs">Knockdowns</span>
                <span className="font-medium tabular-nums">{fighter.avg_knockdowns}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground/60 text-xs">Sub. Attempts</span>
                <span className="font-medium tabular-nums">{fighter.avg_sub_attempts}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground/60 text-xs">Control Time</span>
                <span className="font-medium tabular-nums">{formatControlTime(fighter.avg_control_time)}</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Upcoming fights */}
      {fighter.upcoming_fights.length > 0 && (
        <div className="mb-6">
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-2">
            Upcoming
          </h2>
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableBody>
                  {fighter.upcoming_fights.map((f) => (
                    <TableRow key={f.fight_id}>
                      <TableCell>
                        <Link
                          to={`/fights/${f.fight_id}`}
                          className="font-medium text-sm transition-colors hover:text-blue-400"
                        >
                          vs {f.opponent_name}
                        </Link>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">{f.event_name}</TableCell>
                      <TableCell className="text-xs text-muted-foreground tabular-nums">
                        {new Date(f.event_date + 'T12:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">{f.weight_class}</TableCell>
                      <TableCell className="text-right">
                        <Badge variant="outline" className="text-[10px] border-green-500/40 text-green-400">
                          Scheduled
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Fight history */}
      <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-2">
        Recent Fights
      </h2>
      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">Result</TableHead>
                <TableHead>Opponent</TableHead>
                <TableHead>Event</TableHead>
                <TableHead>Method</TableHead>
                <TableHead>Weight</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {fighter.recent_fights.map((f) => (
                <TableRow key={f.fight_id}>
                  <TableCell>
                    <span className={cn(
                      'text-xs font-bold',
                      f.result === 'W' ? 'text-green-400' :
                      f.result === 'L' ? 'text-red-400' :
                      'text-muted-foreground'
                    )}>
                      {f.result}
                    </span>
                  </TableCell>
                  <TableCell>
                    <Link
                      to={`/fights/${f.fight_id}`}
                      className="text-sm font-medium transition-colors hover:text-blue-400"
                    >
                      {f.opponent_name}
                    </Link>
                    {f.is_title_bout && (
                      <Badge variant="outline" className="ml-1.5 text-[9px] px-1 py-0 border-yellow-500/40 text-yellow-500">
                        TITLE
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="text-xs text-muted-foreground">{f.event_name}</div>
                    <div className="text-[10px] text-muted-foreground/50 tabular-nums">
                      {new Date(f.event_date + 'T12:00:00').toLocaleDateString('en-US', {
                        month: 'short', day: 'numeric', year: 'numeric',
                      })}
                    </div>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {f.method || '--'}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {f.weight_class || '--'}
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
