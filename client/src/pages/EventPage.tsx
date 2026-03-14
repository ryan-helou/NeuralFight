import { useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { getEvent } from '../api/events';
import { generateEventPredictions } from '../api/predictions';
import { Badge } from '@/components/ui/badge';
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

  // AI vs Vegas accuracy
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
      ? f.fighter_1_name : f.fighter_2_name;
    return vegasPick === f.winner_name;
  }).length;

  const showAccuracy = !isUpcoming && completedWithPredictions.length > 0;

  // Betting
  const allBets = event.fights.filter(
    (f) => f.bet_on && f.bet_amount && f.bet_decimal_odds
  );
  const settledBets = allBets.filter((f) => f.winner_name);

  let moneySpent = 0;
  let moneyMade = 0;
  let eventWins = 0;

  if (!isUpcoming && settledBets.length > 0) {
    for (const f of settledBets) {
      moneySpent += f.bet_amount!;
      if (f.bet_on === f.winner_name) {
        moneyMade += f.bet_amount! * (f.bet_decimal_odds! - 1);
        eventWins++;
      }
    }
  } else {
    for (const f of allBets) {
      moneySpent += f.bet_amount!;
      moneyMade += f.bet_amount! * (f.bet_decimal_odds! - 1);
    }
  }

  return (
    <div>
      <Link
        to="/"
        className="mb-4 inline-flex items-center gap-1 text-xs text-muted-foreground/60 transition-colors hover:text-foreground"
      >
        &larr; All Events
      </Link>

      {/* Header */}
      <div className="mb-5">
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-bold">{event.name}</h1>
          {isUpcoming && (
            <Badge variant="outline" className="border-green-500/40 text-green-400 text-[10px]">
              UPCOMING
            </Badge>
          )}
        </div>
        <p className="mt-0.5 text-sm text-muted-foreground/70">
          {eventDate.toLocaleDateString('en-US', {
            weekday: 'long',
            month: 'long',
            day: 'numeric',
            year: 'numeric',
          })}
          {event.location && <> &middot; {event.location}</>}
        </p>
      </div>

      {/* Generating banner */}
      {batchGenerate.isPending && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-border bg-accent/30 px-4 py-2.5 text-sm text-muted-foreground">
          <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-muted-foreground border-t-foreground" />
          Generating predictions...
        </div>
      )}

      {/* Compact stats bar */}
      <div className="mb-5 flex flex-wrap items-center gap-x-5 gap-y-2 rounded-lg border border-border bg-card px-4 py-3 text-xs">
        <Stat label="Fights" value={event.fights.length} />
        {titleBouts > 0 && <Stat label="Title" value={titleBouts} color="text-yellow-400" />}
        <Stat label="Predicted" value={`${predictedFights}/${event.fights.length}`} />

        {showAccuracy && (
          <>
            <div className="h-4 w-px bg-border" />
            <Stat
              label="AI"
              value={`${aiCorrect}/${completedWithPredictions.length}`}
              sub={`${Math.round((aiCorrect / completedWithPredictions.length) * 100)}%`}
              color="text-blue-400"
            />
            {completedWithOdds.length > 0 && (
              <Stat
                label="Vegas"
                value={`${vegasCorrect}/${completedWithOdds.length}`}
                sub={`${Math.round((vegasCorrect / completedWithOdds.length) * 100)}%`}
              />
            )}
          </>
        )}

        {allBets.length > 0 && (
          <>
            <div className="h-4 w-px bg-border" />
            <Stat
              label={isUpcoming ? 'Spend' : 'Spent'}
              value={`$${Math.round(moneySpent)}`}
              sub={`${allBets.length} bet${allBets.length !== 1 ? 's' : ''}${!isUpcoming && settledBets.length > 0 ? ` (${eventWins}-${settledBets.length - eventWins})` : ''}`}
            />
            <Stat
              label={isUpcoming ? 'Potential' : 'P&L'}
              value={
                isUpcoming
                  ? `+$${Math.round(moneyMade)}`
                  : `${moneyMade - moneySpent >= 0 ? '+' : '-'}$${Math.abs(Math.round(moneyMade - moneySpent))}`
              }
              sub={
                isUpcoming
                  ? `${moneySpent > 0 ? `+${Math.round((moneyMade / moneySpent) * 100)}%` : '0%'} if all win`
                  : `${moneySpent > 0 ? `${moneyMade - moneySpent >= 0 ? '+' : ''}${Math.round(((moneyMade - moneySpent) / moneySpent) * 100)}%` : '0%'} ROI`
              }
              color={
                isUpcoming
                  ? 'text-green-400'
                  : moneyMade - moneySpent >= 0 ? 'text-green-400' : 'text-red-400'
              }
            />
          </>
        )}
      </div>

      {/* Fight list */}
      <div className="space-y-1.5">
        {event.fights.map((fight) => (
          <FightCard key={fight.id} fight={fight} />
        ))}
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: string | number;
  sub?: string;
  color?: string;
}) {
  return (
    <div className="flex items-baseline gap-1.5">
      <span className="text-muted-foreground/60">{label}</span>
      <span className={cn('font-semibold tabular-nums', color)}>{value}</span>
      {sub && <span className="text-[10px] text-muted-foreground/50">{sub}</span>}
    </div>
  );
}
