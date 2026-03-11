import { Link } from 'react-router-dom';
import type { FightSummary } from '../../types';

interface FightCardProps {
  fight: FightSummary;
}

export default function FightCard({ fight }: FightCardProps) {
  const hasPrediction = fight.fighter_1_win_prob !== null;
  const f1Favored = hasPrediction && fight.fighter_1_win_prob! >= 0.5;

  return (
    <Link
      to={`/fights/${fight.id}`}
      className="block bg-gray-900 border border-gray-800 rounded-lg p-4 hover:border-gray-600 transition-colors"
    >
      {fight.is_title_bout && (
        <div className="text-xs text-yellow-500 font-medium mb-2">TITLE BOUT</div>
      )}

      <div className="flex items-center justify-between">
        {/* Fighter 1 */}
        <div className="flex-1 text-right pr-4">
          <span
            className={`font-medium ${
              hasPrediction && f1Favored ? 'text-white' : 'text-gray-300'
            }`}
          >
            {fight.fighter_1_name}
          </span>
          {hasPrediction && (
            <div className="text-xs text-gray-500 mt-0.5">
              {Math.round(fight.fighter_1_win_prob! * 100)}%
            </div>
          )}
        </div>

        {/* VS */}
        <div className="text-xs text-gray-600 font-medium px-3">VS</div>

        {/* Fighter 2 */}
        <div className="flex-1 pl-4">
          <span
            className={`font-medium ${
              hasPrediction && !f1Favored ? 'text-white' : 'text-gray-300'
            }`}
          >
            {fight.fighter_2_name}
          </span>
          {hasPrediction && (
            <div className="text-xs text-gray-500 mt-0.5">
              {Math.round(fight.fighter_2_win_prob! * 100)}%
            </div>
          )}
        </div>
      </div>

      {/* Probability bar */}
      {hasPrediction && (
        <div className="flex h-1.5 rounded-full overflow-hidden mt-3 bg-gray-800">
          <div
            className="bg-blue-500 transition-all"
            style={{ width: `${fight.fighter_1_win_prob! * 100}%` }}
          />
          <div
            className="bg-red-500 transition-all"
            style={{ width: `${fight.fighter_2_win_prob! * 100}%` }}
          />
        </div>
      )}

      {/* Weight class and result */}
      <div className="flex justify-between mt-2 text-xs text-gray-500">
        <span>{fight.weight_class || 'Catchweight'}</span>
        {fight.winner_name && (
          <span>
            W: {fight.winner_name} ({fight.method})
          </span>
        )}
      </div>
    </Link>
  );
}
