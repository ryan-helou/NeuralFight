import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell } from 'recharts';
import type { Prediction } from '../../types';

interface MethodBreakdownProps {
  prediction: Prediction;
  fighter1Name?: string;
  fighter2Name?: string;
}

const METHOD_COLORS: Record<string, string> = {
  ko_tko: '#ef4444',
  submission: '#3b82f6',
  decision: '#a855f7',
};

const METHOD_LABELS: Record<string, string> = {
  ko_tko: 'KO/TKO',
  submission: 'Submission',
  decision: 'Decision',
};

export default function MethodBreakdown({ prediction, fighter1Name, fighter2Name }: MethodBreakdownProps) {
  const data = [
    { method: 'KO/TKO', prob: (prediction.ko_tko_prob ?? 0) * 100, fill: METHOD_COLORS.ko_tko },
    { method: 'Submission', prob: (prediction.submission_prob ?? 0) * 100, fill: METHOD_COLORS.submission },
    { method: 'Decision', prob: (prediction.decision_prob ?? 0) * 100, fill: METHOD_COLORS.decision },
  ];

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
      <h3 className="text-sm text-gray-400 mb-4">Method of Victory</h3>
      <ResponsiveContainer width="100%" height={120}>
        <BarChart data={data} layout="vertical" margin={{ left: 70, right: 30 }}>
          <XAxis type="number" domain={[0, 100]} tick={{ fill: '#6b7280', fontSize: 12 }} />
          <YAxis
            type="category"
            dataKey="method"
            tick={{ fill: '#d1d5db', fontSize: 13 }}
            width={70}
          />
          <Bar dataKey="prob" radius={[0, 4, 4, 0]}>
            {data.map((entry, i) => (
              <Cell key={i} fill={entry.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* Per-fighter breakdown */}
      {prediction.method_by_fighter && (
        <div className="grid grid-cols-2 gap-4 mt-4 text-xs">
          {['fighter_1', 'fighter_2'].map((fKey) => {
            const methods = prediction.method_by_fighter![fKey];
            if (!methods) return null;
            return (
              <div key={fKey}>
                <div className="text-gray-500 mb-1">
                  {fKey === 'fighter_1' ? (fighter1Name || 'Fighter 1') : (fighter2Name || 'Fighter 2')}
                </div>
                {Object.entries(methods).map(([m, p]) => (
                  <div key={m} className="flex justify-between text-gray-400">
                    <span>{METHOD_LABELS[m] || m}</span>
                    <span>{Math.round(p * 100)}%</span>
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
