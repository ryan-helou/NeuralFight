import { useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { generatePrediction, getFight, getOdds, getPrediction } from '../api/predictions';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import FighterComparison from '../components/fights/FighterComparison';
import MethodBreakdown from '../components/predictions/MethodBreakdown';
import PredictionBadge from '../components/predictions/PredictionBadge';
import OddsComparison from '../components/predictions/OddsComparison';
import RationalePanel from '../components/predictions/RationalePanel';

import ValueBet from '../components/predictions/UpsetAlert';

export default function FightPage() {
  const { id } = useParams<{ id: string }>();
  const fightId = Number(id);
  const queryClient = useQueryClient();

  const { data: fight, isLoading: fightLoading } = useQuery({
    queryKey: ['fight', fightId],
    queryFn: () => getFight(fightId),
    enabled: !isNaN(fightId),
  });

  const { data: odds } = useQuery({
    queryKey: ['odds', fightId],
    queryFn: () => getOdds(fightId),
    enabled: !isNaN(fightId),
    retry: false,
  });

  const { data: prediction, isError: predictionError } = useQuery({
    queryKey: ['prediction', fightId],
    queryFn: () => getPrediction(fightId),
    enabled: !isNaN(fightId),
    retry: false,
  });

  const generate = useMutation({
    mutationFn: () => generatePrediction(fightId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['prediction', fightId] }),
  });

  // Auto-generate prediction for upcoming fights (no result yet)
  useEffect(() => {
    if (
      fight &&
      !fight.winner_name &&
      predictionError &&
      !prediction &&
      !generate.isPending &&
      !generate.isError
    ) {
      generate.mutate();
    }
  }, [fight, prediction, predictionError, generate]);

  if (fightLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-10 w-96 mx-auto" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-8">
          <Skeleton className="h-64" />
          <Skeleton className="h-64" />
          <Skeleton className="h-64" />
        </div>
      </div>
    );
  }

  if (!fight) {
    return <div className="py-12 text-center text-muted-foreground">Fight not found.</div>;
  }

  return (
    <div>
      <Link
        to="/"
        className="mb-6 inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <span>&larr;</span> Back
      </Link>

      {/* Header */}
      <div className="mb-6 text-center">
        {fight.is_title_bout && (
          <Badge variant="outline" className="mb-2 border-yellow-500/50 text-yellow-500">
            TITLE BOUT
          </Badge>
        )}
        <h1 className="mt-1 text-2xl font-bold sm:text-3xl">
          <span className="text-blue-400">{fight.fighter_1.name}</span>
          <span className="mx-2 text-muted-foreground">vs</span>
          <span className="text-red-400">{fight.fighter_2.name}</span>
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {fight.event_name}
          <span className="mx-1.5 text-muted-foreground/40">&middot;</span>
          {fight.weight_class || 'Catchweight'}
        </p>
        {fight.winner_name && (
          <p className="mt-1 text-xs text-muted-foreground/70">
            Result: {fight.winner_name} by {fight.method} (R{fight.finish_round}, {fight.finish_time})
          </p>
        )}
      </div>

      {/* KPI Row */}
      {prediction ? (
        <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-3">
          <Card>
            <CardContent className="p-4 text-center">
              <p className="text-xs font-medium text-muted-foreground">Favored</p>
              <p className={`mt-1 text-lg font-bold ${prediction.fighter_1_win_prob >= 0.5 ? 'text-blue-400' : 'text-red-400'}`}>
                {prediction.fighter_1_win_prob >= 0.5 ? fight.fighter_1.name : fight.fighter_2.name}
              </p>
              <p className="text-2xl font-black tabular-nums">
                {Math.round(Math.max(prediction.fighter_1_win_prob, prediction.fighter_2_win_prob) * 100)}%
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4 text-center">
              <p className="text-xs font-medium text-muted-foreground">Predicted Method</p>
              <p className="mt-1 text-lg font-bold">
                {prediction.ko_tko_prob !== null && prediction.submission_prob !== null && prediction.decision_prob !== null
                  ? prediction.ko_tko_prob >= prediction.submission_prob && prediction.ko_tko_prob >= prediction.decision_prob
                    ? 'KO/TKO'
                    : prediction.submission_prob >= prediction.decision_prob
                      ? 'Submission'
                      : 'Decision'
                  : '--'}
              </p>
              <p className="text-sm tabular-nums text-muted-foreground">
                {prediction.ko_tko_prob !== null && prediction.submission_prob !== null && prediction.decision_prob !== null
                  ? `${Math.round(Math.max(prediction.ko_tko_prob, prediction.submission_prob, prediction.decision_prob) * 100)}%`
                  : ''}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4 text-center">
              <p className="text-xs font-medium text-muted-foreground">Value Bet</p>
              {(() => {
                if (!odds) return <p className="mt-1 text-sm text-muted-foreground">No odds</p>;
                const edgeF1 = prediction.fighter_1_win_prob - odds.fighter_1_implied;
                const edgeF2 = prediction.fighter_2_win_prob - odds.fighter_2_implied;
                const best = Math.max(edgeF1, edgeF2);
                if (best < 0.03) return <p className="mt-1 text-sm text-muted-foreground">No edge</p>;
                const betOn = edgeF1 > edgeF2 ? fight.fighter_1.name : fight.fighter_2.name;
                const amount = Math.min(100 * (best / 0.05), 500);
                return (
                  <>
                    <p className="mt-1 text-sm font-bold text-green-400">{betOn}</p>
                    <p className="text-lg font-black tabular-nums">${Math.round(amount)}</p>
                  </>
                );
              })()}
            </CardContent>
          </Card>
        </div>
      ) : (
        <div className="mb-6">
          <Card>
            <CardContent className="py-8 text-center">
              {generate.isPending ? (
                <>
                  <div className="mx-auto mb-3 h-6 w-6 animate-spin rounded-full border-2 border-muted-foreground border-t-foreground" />
                  <p className="text-muted-foreground">Generating prediction...</p>
                </>
              ) : generate.isError ? (
                <>
                  <p className="text-muted-foreground">Could not generate prediction.</p>
                  <p className="mt-1 text-xs text-muted-foreground/70">Fighter history may be insufficient.</p>
                  <Button
                    onClick={() => generate.mutate()}
                    className="mt-4"
                    variant="outline"
                    size="sm"
                  >
                    Retry
                  </Button>
                </>
              ) : (
                <>
                  <p className="text-muted-foreground">No prediction available for this fight.</p>
                  <Button
                    onClick={() => generate.mutate()}
                    className="mt-4"
                    variant="default"
                  >
                    Generate Prediction
                  </Button>
                </>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left: Fighter Comparison */}
        <div>
          <FighterComparison fight={fight} />
        </div>

        {/* Center: Predictions */}
        <div className="space-y-4">
          {prediction && (
            <>
              <PredictionBadge
                fighter1Name={fight.fighter_1.name}
                fighter2Name={fight.fighter_2.name}
                fighter1Prob={prediction.fighter_1_win_prob}
                fighter2Prob={prediction.fighter_2_win_prob}
              />
              <MethodBreakdown
                prediction={prediction}
                fighter1Name={fight.fighter_1.name}
                fighter2Name={fight.fighter_2.name}
              />
            </>
          )}
        </div>

        {/* Right: Odds & Rationale */}
        <div className="space-y-4">
          {odds && (
            <OddsComparison
              odds={odds}
              prediction={prediction}
              fighter1Name={fight.fighter_1.name}
              fighter2Name={fight.fighter_2.name}
            />
          )}
          {prediction && (
            <>
              <ValueBet
                prediction={prediction}
                odds={odds ?? null}
                fighter1Name={fight.fighter_1.name}
                fighter2Name={fight.fighter_2.name}
                winnerName={fight.winner_name}
              />
              <RationalePanel
                prediction={prediction}
                fighter1Name={fight.fighter_1.name}
                fighter2Name={fight.fighter_2.name}
              />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
