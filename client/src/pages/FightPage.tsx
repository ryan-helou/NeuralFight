import { useQuery } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { getFight, getPrediction } from '../api/predictions';
import FighterComparison from '../components/fights/FighterComparison';
import MethodBreakdown from '../components/predictions/MethodBreakdown';
import PredictionBadge from '../components/predictions/PredictionBadge';
import RationalePanel from '../components/predictions/RationalePanel';
import RoundProbabilities from '../components/predictions/RoundProbabilities';
import UpsetAlert from '../components/predictions/UpsetAlert';

export default function FightPage() {
  const { id } = useParams<{ id: string }>();
  const fightId = Number(id);

  const { data: fight, isLoading: fightLoading } = useQuery({
    queryKey: ['fight', fightId],
    queryFn: () => getFight(fightId),
    enabled: !isNaN(fightId),
  });

  const { data: prediction } = useQuery({
    queryKey: ['prediction', fightId],
    queryFn: () => getPrediction(fightId),
    enabled: !isNaN(fightId),
    retry: false,
  });

  if (fightLoading) {
    return <div className="text-gray-500 text-center py-12">Loading fight...</div>;
  }

  if (!fight) {
    return <div className="text-gray-500 text-center py-12">Fight not found.</div>;
  }

  return (
    <div>
      <Link to="/" className="text-sm text-gray-500 hover:text-gray-300 mb-4 inline-block">
        &larr; Back
      </Link>

      {/* Header */}
      <div className="text-center mb-8">
        {fight.is_title_bout && (
          <span className="text-xs bg-yellow-500/20 text-yellow-400 px-3 py-1 rounded-full">
            TITLE BOUT
          </span>
        )}
        <h1 className="text-2xl font-bold text-white mt-2">
          {fight.fighter_1.name} vs {fight.fighter_2.name}
        </h1>
        <p className="text-gray-400 text-sm mt-1">
          {fight.event_name} &middot; {fight.weight_class || 'Catchweight'}
        </p>
        {fight.winner_name && (
          <p className="text-gray-500 text-sm mt-1">
            Result: {fight.winner_name} by {fight.method} (R{fight.finish_round}, {fight.finish_time})
          </p>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Fighter Comparison */}
        <div>
          <FighterComparison fight={fight} />
        </div>

        {/* Center: Predictions */}
        <div className="space-y-6">
          {prediction ? (
            <>
              <PredictionBadge
                fighter1Name={fight.fighter_1.name}
                fighter2Name={fight.fighter_2.name}
                fighter1Prob={prediction.fighter_1_win_prob}
                fighter2Prob={prediction.fighter_2_win_prob}
              />
              <MethodBreakdown prediction={prediction} />
              <RoundProbabilities prediction={prediction} />
            </>
          ) : (
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 text-center">
              <p className="text-gray-500">No prediction available for this fight.</p>
              <p className="text-gray-600 text-xs mt-1">Predictions are generated after model training.</p>
            </div>
          )}
        </div>

        {/* Right: Rationale & Betting */}
        <div className="space-y-6">
          {prediction && (
            <>
              <UpsetAlert prediction={prediction} />
              <RationalePanel prediction={prediction} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
