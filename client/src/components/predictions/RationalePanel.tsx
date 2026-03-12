import type { Prediction } from '../../types';

interface RationalePanelProps {
  prediction: Prediction;
  fighter1Name?: string;
  fighter2Name?: string;
}

const FEATURE_SHORT_NAMES: Record<string, string> = {
  sig_strikes_per_min_diff: 'Sig. Strikes/min',
  sig_strike_accuracy_diff: 'Strike Accuracy',
  sig_strike_defense_diff: 'Strike Defense',
  takedowns_per_15min_diff: 'Takedowns/15min',
  takedown_defense_diff: 'Takedown Defense',
  knockdown_rate_diff: 'Knockdown Rate',
  finish_rate_ko_diff: 'KO Finish Rate',
  finish_rate_sub_diff: 'Sub Finish Rate',
  win_rate_diff: 'Win Rate',
  reach_diff: 'Reach',
  height_diff: 'Height',
  age_diff: 'Age',
  experience_diff: 'Experience',
  win_streak_diff: 'Win Streak',
  control_time_per_15min_diff: 'Control Time',
  avg_opp_win_rate_diff: 'Opponent Quality',
  avg_beaten_opp_win_rate_diff: 'Quality of Wins',
  avg_lost_to_opp_win_rate_diff: 'Quality of Losses',
  avg_win_dominance_diff: 'Win Dominance',
  avg_loss_dominance_diff: 'Loss Competitiveness',
  finish_speed_diff: 'Finish Speed',
  been_finished_rate_diff: 'Finish Vulnerability',
  layoff_diff: 'Ring Rust',
  strike_dropoff_diff: 'Cardio',
  late_round_win_rate_diff: 'Late-Fight Win Rate',
};

export default function RationalePanel({ prediction, fighter1Name, fighter2Name }: RationalePanelProps) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
      <h3 className="text-sm text-gray-400 mb-3">AI Rationale</h3>

      {prediction.rationale && (
        <p className="text-sm text-gray-300 leading-relaxed mb-4">
          {prediction.rationale}
        </p>
      )}

      {prediction.feature_importances && prediction.feature_importances.length > 0 && (
        <div>
          <h4 className="text-xs text-gray-500 mb-2">Top Factors</h4>
          <div className="space-y-1.5">
            {prediction.feature_importances.slice(0, 7).map((feat, i) => {
              const shortName = Object.entries(FEATURE_SHORT_NAMES).find(
                ([key]) => feat.name.includes(key)
              )?.[1] || feat.name;

              const isPositive = feat.shap_value > 0;

              return (
                <div key={i} className="flex items-center justify-between text-xs">
                  <span className="text-gray-400">{shortName}</span>
                  <span className={isPositive ? 'text-red-400' : 'text-blue-400'}>
                    {isPositive ? `Favors ${fighter2Name || 'F2'}` : `Favors ${fighter1Name || 'F1'}`}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
