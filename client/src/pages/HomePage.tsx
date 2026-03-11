import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { getEvents } from '../api/events';
import { getUpsets } from '../api/predictions';
import EventList from '../components/events/EventList';
import type { Upset } from '../types';
import { Link } from 'react-router-dom';

export default function HomePage() {
  const [showUpcoming, setShowUpcoming] = useState(false);

  const { data: events, isLoading } = useQuery({
    queryKey: ['events', showUpcoming],
    queryFn: () => getEvents(showUpcoming, 30),
  });

  const { data: upsets } = useQuery({
    queryKey: ['upsets'],
    queryFn: () => getUpsets(30),
  });

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
      {/* Events */}
      <div className="lg:col-span-2">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-white">UFC Events</h1>
          <div className="flex bg-gray-900 rounded-lg p-1 border border-gray-800">
            <button
              onClick={() => setShowUpcoming(false)}
              className={`px-3 py-1 text-sm rounded ${
                !showUpcoming ? 'bg-gray-700 text-white' : 'text-gray-400'
              }`}
            >
              All
            </button>
            <button
              onClick={() => setShowUpcoming(true)}
              className={`px-3 py-1 text-sm rounded ${
                showUpcoming ? 'bg-gray-700 text-white' : 'text-gray-400'
              }`}
            >
              Upcoming
            </button>
          </div>
        </div>

        {isLoading ? (
          <div className="text-gray-500 text-center py-12">Loading events...</div>
        ) : (
          <EventList events={events || []} />
        )}
      </div>

      {/* Upset Alerts Sidebar */}
      <div>
        <h2 className="text-lg font-bold text-white mb-4">Upset Alerts</h2>
        {upsets && upsets.length > 0 ? (
          <div className="space-y-3">
            {upsets.slice(0, 8).map((upset: Upset) => (
              <Link
                key={upset.fight_id}
                to={`/fights/${upset.fight_id}`}
                className="block bg-gray-900 border border-yellow-500/30 rounded-lg p-4 hover:border-yellow-500/60 transition-colors"
              >
                <div className="text-sm font-medium text-white">
                  {upset.fighter_1_name} vs {upset.fighter_2_name}
                </div>
                <div className="text-xs text-gray-500 mt-0.5">{upset.event_name}</div>
                <div className="flex justify-between mt-2 text-xs">
                  <span className="text-yellow-400">
                    Upset Score: {Math.round(upset.upset_score)}
                  </span>
                  <span className="text-gray-400">
                    {Math.round(upset.fighter_1_win_prob * 100)}% / {Math.round(upset.fighter_2_win_prob * 100)}%
                  </span>
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <div className="text-gray-500 text-sm bg-gray-900 border border-gray-800 rounded-lg p-4">
            No upset alerts at the moment.
          </div>
        )}
      </div>
    </div>
  );
}
