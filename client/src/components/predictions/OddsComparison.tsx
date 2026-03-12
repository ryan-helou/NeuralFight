import type { Odds, Prediction } from '../../types';

interface OddsComparisonProps {
  odds: Odds;
  prediction: Prediction | undefined;
  fighter1Name: string;
  fighter2Name: string;
}

function formatAmerican(odds: number): string {
  return odds > 0 ? `+${odds}` : `${odds}`;
}

export default function OddsComparison({ odds, prediction, fighter1Name, fighter2Name }: OddsComparisonProps) {
  const f1Implied = Math.round(odds.fighter_1_implied * 100);
  const f2Implied = Math.round(odds.fighter_2_implied * 100);
  const f1Ai = prediction ? Math.round(prediction.fighter_1_win_prob * 100) : null;
  const f2Ai = prediction ? Math.round(prediction.fighter_2_win_prob * 100) : null;

  // Edge = AI prob - implied prob (positive = AI sees value)
  const f1Edge = f1Ai !== null ? f1Ai - f1Implied : null;
  const f2Edge = f2Ai !== null ? f2Ai - f2Implied : null;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
      <h3 className="text-sm text-gray-400 mb-4">AI vs Betting Odds</h3>

      <div className="space-y-4">
        {/* Fighter 1 */}
        <div>
          <div className="flex justify-between items-baseline mb-1">
            <span className="text-sm font-medium text-blue-400">{fighter1Name}</span>
            <span className="text-xs text-gray-500">{formatAmerican(odds.fighter_1_american)}</span>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex-1">
              <div className="flex justify-between text-xs text-gray-500 mb-1">
                <span>Odds: {f1Implied}%</span>
                {f1Ai !== null && <span>AI: {f1Ai}%</span>}
              </div>
              <div className="relative h-2 bg-gray-800 rounded-full overflow-hidden">
                <div className="absolute h-full bg-gray-600 rounded-full" style={{ width: `${f1Implied}%` }} />
                {f1Ai !== null && (
                  <div
                    className="absolute h-full bg-blue-500 rounded-full opacity-80"
                    style={{ width: `${f1Ai}%` }}
                  />
                )}
              </div>
            </div>
            {f1Edge !== null && (
              <span className={`text-xs font-medium min-w-[3rem] text-right ${
                f1Edge > 3 ? 'text-green-400' : f1Edge < -3 ? 'text-red-400' : 'text-gray-500'
              }`}>
                {f1Edge > 0 ? '+' : ''}{f1Edge}%
              </span>
            )}
          </div>
        </div>

        {/* Fighter 2 */}
        <div>
          <div className="flex justify-between items-baseline mb-1">
            <span className="text-sm font-medium text-red-400">{fighter2Name}</span>
            <span className="text-xs text-gray-500">{formatAmerican(odds.fighter_2_american)}</span>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex-1">
              <div className="flex justify-between text-xs text-gray-500 mb-1">
                <span>Odds: {f2Implied}%</span>
                {f2Ai !== null && <span>AI: {f2Ai}%</span>}
              </div>
              <div className="relative h-2 bg-gray-800 rounded-full overflow-hidden">
                <div className="absolute h-full bg-gray-600 rounded-full" style={{ width: `${f2Implied}%` }} />
                {f2Ai !== null && (
                  <div
                    className="absolute h-full bg-red-500 rounded-full opacity-80"
                    style={{ width: `${f2Ai}%` }}
                  />
                )}
              </div>
            </div>
            {f2Edge !== null && (
              <span className={`text-xs font-medium min-w-[3rem] text-right ${
                f2Edge > 3 ? 'text-green-400' : f2Edge < -3 ? 'text-red-400' : 'text-gray-500'
              }`}>
                {f2Edge > 0 ? '+' : ''}{f2Edge}%
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 mt-4 pt-3 border-t border-gray-800 text-xs text-gray-500">
        <div className="flex items-center gap-1">
          <div className="w-3 h-1.5 bg-gray-600 rounded-full" /> Odds
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-1.5 bg-blue-500 rounded-full opacity-80" /> AI Model
        </div>
        <span className="text-green-400 ml-auto">+ = AI sees value</span>
      </div>

      <div className="text-xs text-gray-600 mt-2">
        Source: {odds.source.replace('_', ' ')}
      </div>
    </div>
  );
}
