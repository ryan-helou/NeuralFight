import { useMutation, useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getEvents } from '../api/events';
import { generateUpcomingPredictions, getValueBets } from '../api/predictions';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';
import EventList from '../components/events/EventList';
import type { ValueBet } from '../types';

export default function HomePage() {
  const [showUpcoming, setShowUpcoming] = useState(false);

  const { data: events, isLoading } = useQuery({
    queryKey: ['events', showUpcoming],
    queryFn: () => getEvents(showUpcoming, 50),
  });

  const { data: allEvents } = useQuery({
    queryKey: ['events', false],
    queryFn: () => getEvents(false, 999),
  });

  const { data: valueBets } = useQuery({
    queryKey: ['value-bets'],
    queryFn: getValueBets,
  });

  const batchGenerate = useMutation({
    mutationFn: generateUpcomingPredictions,
  });

  useEffect(() => {
    if (!batchGenerate.isPending && !batchGenerate.isSuccess && !batchGenerate.isError) {
      batchGenerate.mutate();
    }
  }, []);

  const upcomingCount = allEvents?.filter(
    (e) => new Date(e.date + 'T23:59:59') >= new Date()
  ).length ?? 0;
  const totalFights = allEvents?.reduce((s, e) => s + e.fight_count, 0) ?? 0;

  return (
    <div className="space-y-6">
      {/* Compact KPI bar */}
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-lg border border-border bg-card px-5 py-3 text-sm">
        <div className="flex items-baseline gap-1.5">
          <span className="text-muted-foreground/60 text-xs">Events</span>
          <span className="font-bold tabular-nums">{allEvents?.length ?? '--'}</span>
        </div>
        <div className="flex items-baseline gap-1.5">
          <span className="text-muted-foreground/60 text-xs">Fights</span>
          <span className="font-bold tabular-nums">{totalFights || '--'}</span>
        </div>
        <div className="flex items-baseline gap-1.5">
          <span className="text-muted-foreground/60 text-xs">Upcoming</span>
          <span className="font-bold tabular-nums text-green-400">{upcomingCount || '--'}</span>
        </div>
        <div className="flex items-baseline gap-1.5">
          <span className="text-muted-foreground/60 text-xs">Value Bets</span>
          <span className={cn('font-bold tabular-nums', valueBets && valueBets.length > 0 && 'text-green-400')}>
            {valueBets?.length ?? 0}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Events list */}
        <div className="lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Events</h2>
            <Tabs
              value={showUpcoming ? 'upcoming' : 'all'}
              onValueChange={(v) => setShowUpcoming(v === 'upcoming')}
            >
              <TabsList className="h-7">
                <TabsTrigger value="all" className="text-xs px-2.5 py-1">All</TabsTrigger>
                <TabsTrigger value="upcoming" className="text-xs px-2.5 py-1">Upcoming</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>

          {isLoading ? (
            <div className="space-y-1.5">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-[60px] w-full rounded-xl" />
              ))}
            </div>
          ) : (
            <EventList events={events || []} />
          )}
        </div>

        {/* Value Bets sidebar */}
        <div>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                Value Bets
                {valueBets && valueBets.length > 0 && (
                  <Badge variant="outline" className="text-[10px] px-1.5 py-0 border-green-500/40 text-green-400 normal-case">
                    {valueBets.length}
                  </Badge>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {valueBets && valueBets.length > 0 ? (
                <div className="space-y-1">
                  {valueBets.slice(0, 8).map((bet: ValueBet) => (
                    <Link
                      key={bet.fight_id}
                      to={`/fights/${bet.fight_id}`}
                      className="block rounded-md px-2.5 py-2 transition-colors hover:bg-accent/50 -mx-1"
                    >
                      <div className="flex items-center justify-between">
                        <div className="min-w-0">
                          <div className="text-xs font-medium truncate">
                            {bet.fighter_1_name} vs {bet.fighter_2_name}
                          </div>
                          <div className="text-[10px] text-muted-foreground/50 truncate">
                            {bet.event_name}
                          </div>
                        </div>
                        <div className="shrink-0 text-right ml-3">
                          <div className="text-xs font-semibold text-green-400 tabular-nums">
                            +{(bet.edge * 100).toFixed(1)}%
                          </div>
                          <div className="text-[10px] text-muted-foreground/60 tabular-nums">
                            ${Math.round(bet.bet_amount)} on {bet.bet_on.split(' ').pop()}
                          </div>
                        </div>
                      </div>
                    </Link>
                  ))}
                  {valueBets.length > 8 && (
                    <Link
                      to="/upsets"
                      className="block pt-1.5 text-center text-[11px] text-muted-foreground/50 hover:text-foreground transition-colors"
                    >
                      View all {valueBets.length} bets &rarr;
                    </Link>
                  )}
                </div>
              ) : (
                <p className="text-xs text-muted-foreground/60">
                  No value bets right now.
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
