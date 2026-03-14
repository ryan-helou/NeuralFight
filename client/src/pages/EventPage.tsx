import { useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { getEvent } from '../api/events';
import { generateEventPredictions } from '../api/predictions';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import FightCard from '../components/fights/FightCard';

export default function EventPage() {
  const { id } = useParams<{ id: string }>();
  const eventId = Number(id);
  const queryClient = useQueryClient();

  const { data: event, isLoading } = useQuery({
    queryKey: ['event', eventId],
    queryFn: () => getEvent(eventId),
    enabled: !isNaN(eventId),
  });

  const batchGenerate = useMutation({
    mutationFn: () => generateEventPredictions(eventId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['event', eventId] }),
  });

  // Auto-generate predictions for any event with missing predictions
  const hasMissing = event ? event.fights.some((f) => f.fighter_1_win_prob === null) : false;

  useEffect(() => {
    if (hasMissing && !batchGenerate.isPending && !batchGenerate.isSuccess) {
      batchGenerate.mutate();
    }
  }, [hasMissing, batchGenerate.isPending, batchGenerate.isSuccess]);

  if (isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-64" />
        <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-[72px] rounded-xl" />
          ))}
        </div>
        <div className="mt-6 space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-20 w-full rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  if (!event) {
    return <div className="py-12 text-center text-muted-foreground">Event not found.</div>;
  }

  const eventDate = new Date(event.date + 'T23:59:59');
  const hasNoResults = event.fights.every((f) => !f.winner_name);
  const isUpcoming = eventDate >= new Date() || hasNoResults;
  const titleBouts = event.fights.filter((f) => f.is_title_bout).length;
  const predictedFights = event.fights.filter((f) => f.fighter_1_win_prob !== null).length;

  // Compute AI vs Vegas accuracy for past events
  const completedWithPredictions = event.fights.filter(
    (f) => f.winner_name && f.fighter_1_win_prob !== null
  );
  const completedWithOdds = completedWithPredictions.filter(
    (f) => f.vegas_fighter_1_implied !== null
  );

  const aiCorrect = completedWithPredictions.filter((f) => {
    const aiPick = f.fighter_1_win_prob! >= 0.5 ? f.fighter_1_name : f.fighter_2_name;
    return aiPick === f.winner_name;
  }).length;

  const vegasCorrect = completedWithOdds.filter((f) => {
    const vegasPick = f.vegas_fighter_1_implied! >= f.vegas_fighter_2_implied!
      ? f.fighter_1_name
      : f.fighter_2_name;
    return vegasPick === f.winner_name;
  }).length;

  const showAccuracy = !isUpcoming && completedWithPredictions.length > 0;

  // All fights with value bets (past and upcoming)
  const allBets = event.fights.filter(
    (f) => f.bet_on && f.bet_amount && f.bet_decimal_odds
  );
  // Past bets with results
  const settledBets = allBets.filter((f) => f.winner_name);

  let moneySpent = 0;
  let moneyMade = 0;
  let eventWins = 0;

  if (!isUpcoming && settledBets.length > 0) {
    // Past event: actual P&L
    for (const f of settledBets) {
      moneySpent += f.bet_amount!;
      if (f.bet_on === f.winner_name) {
        moneyMade += f.bet_amount! * (f.bet_decimal_odds! - 1);
        eventWins++;
      }
    }
  } else {
    // Upcoming event: projected
    for (const f of allBets) {
      moneySpent += f.bet_amount!;
      moneyMade += f.bet_amount! * (f.bet_decimal_odds! - 1);
    }
  }

  const showBetting = allBets.length > 0;

  return (
    <div>
      <Link
        to="/"
        className="mb-6 inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <span>&larr;</span> All Events
      </Link>

      <div className="mb-6">
        <h1 className="text-2xl font-bold">{event.name}</h1>
        <div className="mt-1 flex items-center gap-2 text-sm text-muted-foreground">
          <span>
            {eventDate.toLocaleDateString('en-US', {
              weekday: 'long',
              month: 'long',
              day: 'numeric',
              year: 'numeric',
            })}
          </span>
          {event.location && (
            <>
              <span className="text-muted-foreground/40">&middot;</span>
              <span>{event.location}</span>
            </>
          )}
          {isUpcoming && (
            <Badge variant="outline" className="ml-1 border-green-500/50 text-green-400 text-[10px]">
              UPCOMING
            </Badge>
          )}
        </div>
      </div>

      {/* Generating banner */}
      {batchGenerate.isPending && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-border bg-accent/30 px-4 py-3 text-sm text-muted-foreground">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-muted-foreground border-t-foreground" />
          Generating predictions for all fights...
        </div>
      )}

      {/* KPI Cards */}
      <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        <Card>
          <CardContent className="p-4">
            <p className="text-xs font-medium text-muted-foreground">Fights</p>
            <p className="mt-1 text-2xl font-bold tabular-nums">{event.fights.length}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-xs font-medium text-muted-foreground">Title Bouts</p>
            <p className={`mt-1 text-2xl font-bold tabular-nums ${titleBouts > 0 ? 'text-yellow-400' : ''}`}>
              {titleBouts}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-xs font-medium text-muted-foreground">Predictions</p>
            <p className="mt-1 text-2xl font-bold tabular-nums">{predictedFights}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-xs font-medium text-muted-foreground">Coverage</p>
            <p className={`mt-1 text-2xl font-bold tabular-nums ${predictedFights === event.fights.length ? 'text-green-400' : ''}`}>
              {event.fights.length > 0 ? Math.round((predictedFights / event.fights.length) * 100) : 0}%
            </p>
          </CardContent>
        </Card>
        {showAccuracy && (
          <>
            <Card>
              <CardContent className="p-4">
                <p className="text-xs font-medium text-muted-foreground">AI Accuracy</p>
                <p className="mt-1 text-2xl font-bold tabular-nums text-blue-400">
                  {aiCorrect}/{completedWithPredictions.length}
                </p>
                <p className="text-[10px] text-muted-foreground/60">
                  {Math.round((aiCorrect / completedWithPredictions.length) * 100)}%
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <p className="text-xs font-medium text-muted-foreground">Vegas Accuracy</p>
                {completedWithOdds.length > 0 ? (
                  <>
                    <p className="mt-1 text-2xl font-bold tabular-nums text-muted-foreground">
                      {vegasCorrect}/{completedWithOdds.length}
                    </p>
                    <p className="text-[10px] text-muted-foreground/60">
                      {Math.round((vegasCorrect / completedWithOdds.length) * 100)}%
                    </p>
                  </>
                ) : (
                  <p className="mt-1 text-sm text-muted-foreground">No odds</p>
                )}
              </CardContent>
            </Card>
          </>
        )}
        {showBetting && (
          <>
            <Card>
              <CardContent className="p-4">
                <p className="text-xs font-medium text-muted-foreground">
                  {isUpcoming ? 'Projected Spend' : 'Money Spent'}
                </p>
                <p className="mt-1 text-2xl font-bold tabular-nums">
                  ${Math.round(moneySpent)}
                </p>
                <p className="text-[10px] text-muted-foreground/60">
                  {allBets.length} value bet{allBets.length !== 1 ? 's' : ''}
                  {!isUpcoming && settledBets.length > 0 && (
                    <> &middot; {eventWins}-{settledBets.length - eventWins} record</>
                  )}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <p className="text-xs font-medium text-muted-foreground">
                  {isUpcoming ? 'Potential Return' : 'Money Made'}
                </p>
                <p className={cn(
                  'mt-1 text-2xl font-bold tabular-nums',
                  isUpcoming
                    ? 'text-green-400'
                    : moneyMade - moneySpent >= 0 ? 'text-green-400' : 'text-red-400'
                )}>
                  {isUpcoming ? (
                    <>+${Math.round(moneyMade)}</>
                  ) : (
                    <>{moneyMade - moneySpent >= 0 ? '+' : '-'}${Math.abs(Math.round(moneyMade - moneySpent))}</>
                  )}
                </p>
                <p className="text-[10px] text-muted-foreground/60">
                  {isUpcoming
                    ? `(${moneySpent > 0 ? `+${Math.round((moneyMade / moneySpent) * 100)}%` : '0%'} if all win)`
                    : `(${moneySpent > 0 ? `${moneyMade - moneySpent >= 0 ? '+' : ''}${Math.round(((moneyMade - moneySpent) / moneySpent) * 100)}%` : '0%'} ROI)`
                  }
                </p>
              </CardContent>
            </Card>
          </>
        )}
      </div>

      <div className="space-y-2">
        {event.fights.map((fight) => (
          <FightCard key={fight.id} fight={fight} />
        ))}
      </div>
    </div>
  );
}
