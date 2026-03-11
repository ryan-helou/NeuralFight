import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip } from 'recharts';
import type { Prediction } from '../../types';

interface RoundProbabilitiesProps {
  prediction: Prediction;
}

export default function RoundProbabilities({ prediction }: RoundProbabilitiesProps) {
  if (!prediction.round_probabilities) return null;

  const data = Object.entries(prediction.round_probabilities)
    .map(([round, prob]) => ({
      round: round === 'decision' ? 'DEC' : `R${round}`,
      prob: Math.round(prob * 100),
    }))
    .sort((a, b) => {
      if (a.round === 'DEC') return 1;
      if (b.round === 'DEC') return -1;
      return a.round.localeCompare(b.round);
    });

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
      <h3 className="text-sm text-gray-400 mb-4">Round of Finish</h3>
      <ResponsiveContainer width="100%" height={160}>
        <BarChart data={data} margin={{ bottom: 0 }}>
          <XAxis dataKey="round" tick={{ fill: '#d1d5db', fontSize: 12 }} />
          <YAxis tick={{ fill: '#6b7280', fontSize: 12 }} domain={[0, 'auto']} />
          <Tooltip
            contentStyle={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 8 }}
            labelStyle={{ color: '#d1d5db' }}
            formatter={(value: number) => [`${value}%`, 'Probability']}
          />
          <Bar dataKey="prob" fill="#ef4444" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
