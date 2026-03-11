import type { Prediction } from '../../types';

interface UpsetAlertProps {
  prediction: Prediction;
}

export default function UpsetAlert({ prediction }: UpsetAlertProps) {
  const score = prediction.upset_score;
  const confidence = prediction.betting_confidence;

  if (score === null || score === undefined) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
        <h3 className="text-sm text-gray-400 mb-2">Betting Analysis</h3>
        <p className="text-gray-500 text-sm">No betting odds available for this fight.</p>
      </div>
    );
  }

  const severity = score >= 60 ? 'high' : score >= 30 ? 'medium' : 'low';
  const colors = {
    high: 'border-red-500 bg-red-500/10',
    medium: 'border-yellow-500 bg-yellow-500/10',
    low: 'border-gray-700 bg-gray-900',
  };

  return (
    <div className={`border rounded-lg p-6 ${colors[severity]}`}>
      <h3 className="text-sm text-gray-400 mb-3">Betting Analysis</h3>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="text-xs text-gray-500">Upset Score</div>
          <div className={`text-2xl font-bold ${
            severity === 'high' ? 'text-red-400' :
            severity === 'medium' ? 'text-yellow-400' : 'text-gray-400'
          }`}>
            {Math.round(score)}
          </div>
          <div className="text-xs text-gray-500 mt-0.5">
            {severity === 'high' ? 'High upset potential' :
             severity === 'medium' ? 'Moderate upset potential' :
             'Low upset potential'}
          </div>
        </div>

        {confidence !== null && confidence !== undefined && (
          <div>
            <div className="text-xs text-gray-500">Betting Confidence</div>
            <div className="text-2xl font-bold text-white">
              {Math.round(confidence)}
            </div>
            <div className="text-xs text-gray-500 mt-0.5">
              {confidence >= 70 ? 'Strong bet' :
               confidence >= 40 ? 'Moderate edge' :
               'Weak / avoid'}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
