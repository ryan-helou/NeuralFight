import { useMutation, useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getEvents } from '../api/events';
import { generateUpcomingPredictions, getValueBets } from '../api/predictions';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
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

  // Auto-generate predictions for all upcoming fights on page load
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
      {/* KPI Cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <KpiCard label="Total Events" value={allEvents?.length ?? '--'} />
        <KpiCard label="Total Fights" value={totalFights || '--'} />
        <KpiCard label="Upcoming Events" value={upcomingCount || '--'} accent />
        <KpiCard
          label="Value Bets"
          value={valueBets?.length ?? 0}
          accent={!!valueBets && valueBets.length > 0}
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Events list */}
        <div className="lg:col-span-2">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold">Events</h2>
            <Tabs
              value={showUpcoming ? 'upcoming' : 'all'}
              onValueChange={(v) => setShowUpcoming(v === 'upcoming')}
            >
              <TabsList>
                <TabsTrigger value="all">All</TabsTrigger>
                <TabsTrigger value="upcoming">Upcoming</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>

          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-[72px] w-full rounded-xl" />
              ))}
            </div>
          ) : (
            <EventList events={events || []} />
          )}
        </div>

        {/* Value Bets sidebar */}
        <div>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                Value Bets
                {valueBets && valueBets.length > 0 && (
                  <Badge variant="outline" className="text-[10px] px-1.5 border-green-500/50 text-green-400">
                    {valueBets.length}
                  </Badge>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {valueBets && valueBets.length > 0 ? (
                <div className="space-y-2">
                  {valueBets.slice(0, 8).map((bet: ValueBet) => (
                    <Link
                      key={bet.fight_id}
                      to={`/fights/${bet.fight_id}`}
                      className="block rounded-lg border border-border p-3 transition-colors hover:bg-accent/50"
                    >
                      <div className="text-sm font-medium">
                        {bet.fighter_1_name} vs {bet.fighter_2_name}
                      </div>
                      <div className="mt-0.5 text-xs text-muted-foreground">
                        {bet.event_name}
                      </div>
                      <div className="mt-2 flex justify-between text-xs">
                        <span className="text-green-400 font-medium">
                          ${Math.round(bet.bet_amount)} on {bet.bet_on}
                        </span>
                        <span className="text-green-400/70 tabular-nums">
                          +{(bet.edge * 100).toFixed(1)}% edge
                        </span>
                      </div>
                    </Link>
                  ))}
                  {valueBets.length > 8 && (
                    <Link
                      to="/upsets"
                      className="block pt-2 text-center text-xs text-muted-foreground hover:text-foreground transition-colors"
                    >
                      View all {valueBets.length} bets &rarr;
                    </Link>
                  )}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  No value bets right now. AI and Vegas agree.
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function KpiCard({
  label,
  value,
  accent = false,
}: {
  label: string;
  value: string | number;
  accent?: boolean;
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        <p className={`mt-1 text-2xl font-bold tabular-nums ${accent ? 'text-red-400' : ''}`}>
          {value}
        </p>
      </CardContent>
    </Card>
  );
}
