interface PredictionBadgeProps {
  fighter1Name: string;
  fighter2Name: string;
  fighter1Prob: number;
  fighter2Prob: number;
}

export default function PredictionBadge({
  fighter1Name,
  fighter2Name,
  fighter1Prob,
  fighter2Prob,
}: PredictionBadgeProps) {
  const f1Pct = Math.round(fighter1Prob * 100);
  const f2Pct = Math.round(fighter2Prob * 100);
  const favored = fighter1Prob >= 0.5 ? fighter1Name : fighter2Name;
  const favoredPct = Math.max(f1Pct, f2Pct);

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 text-center">
      <h3 className="text-sm text-gray-400 mb-3">Winner Prediction</h3>
      <div className="text-3xl font-bold text-white mb-1">{favored}</div>
      <div className="text-xl text-red-400 font-semibold">{favoredPct}%</div>

      {/* Donut-style probability display */}
      <div className="flex items-center justify-center gap-8 mt-6">
        <div className="text-center">
          <div className={`text-2xl font-bold ${fighter1Prob >= 0.5 ? 'text-blue-400' : 'text-gray-500'}`}>
            {f1Pct}%
          </div>
          <div className="text-xs text-gray-400 mt-1">{fighter1Name}</div>
        </div>
        <div className="text-center">
          <div className={`text-2xl font-bold ${fighter2Prob >= 0.5 ? 'text-red-400' : 'text-gray-500'}`}>
            {f2Pct}%
          </div>
          <div className="text-xs text-gray-400 mt-1">{fighter2Name}</div>
        </div>
      </div>

      {/* Probability bar */}
      <div className="flex h-3 rounded-full overflow-hidden mt-4 bg-gray-800">
        <div className="bg-blue-500 transition-all" style={{ width: `${f1Pct}%` }} />
        <div className="bg-red-500 transition-all" style={{ width: `${f2Pct}%` }} />
      </div>
    </div>
  );
}
