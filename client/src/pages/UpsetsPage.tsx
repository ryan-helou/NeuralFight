import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { getUpsets } from '../api/predictions';

export default function UpsetsPage() {
  const { data: upsets, isLoading } = useQuery({
    queryKey: ['upsets', 0],
    queryFn: () => getUpsets(0),
  });

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-6">Upset Alerts</h1>
      <p className="text-gray-400 text-sm mb-8">
        Fights where the AI model disagrees with betting odds. Higher upset score = more upset potential.
      </p>

      {isLoading ? (
        <div className="text-gray-500 text-center py-12">Loading...</div>
      ) : !upsets || upsets.length === 0 ? (
        <div className="text-gray-500 text-center py-12">No upset alerts found.</div>
      ) : (
        <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-800">
                <th className="text-left text-xs text-gray-500 font-medium px-4 py-3">Fight</th>
                <th className="text-left text-xs text-gray-500 font-medium px-4 py-3">Event</th>
                <th className="text-right text-xs text-gray-500 font-medium px-4 py-3">AI Probs</th>
                <th className="text-right text-xs text-gray-500 font-medium px-4 py-3">Upset Score</th>
                <th className="text-right text-xs text-gray-500 font-medium px-4 py-3">Bet Confidence</th>
              </tr>
            </thead>
            <tbody>
              {upsets.map((upset) => {
                const severity = upset.upset_score >= 60 ? 'text-red-400' :
                  upset.upset_score >= 30 ? 'text-yellow-400' : 'text-gray-400';

                return (
                  <tr key={upset.fight_id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                    <td className="px-4 py-3">
                      <Link
                        to={`/fights/${upset.fight_id}`}
                        className="text-sm text-white hover:text-red-400 transition-colors"
                      >
                        {upset.fighter_1_name} vs {upset.fighter_2_name}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">{upset.event_name}</td>
                    <td className="px-4 py-3 text-right text-sm text-gray-400">
                      {Math.round(upset.fighter_1_win_prob * 100)}% / {Math.round(upset.fighter_2_win_prob * 100)}%
                    </td>
                    <td className={`px-4 py-3 text-right text-sm font-medium ${severity}`}>
                      {Math.round(upset.upset_score)}
                    </td>
                    <td className="px-4 py-3 text-right text-sm text-gray-400">
                      {upset.betting_confidence !== null ? Math.round(upset.betting_confidence) : '--'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
