import { Link } from 'react-router-dom';
import type { EventSummary } from '../../types';

interface EventCardProps {
  event: EventSummary;
}

export default function EventCard({ event }: EventCardProps) {
  const eventDate = new Date(event.date);
  const isUpcoming = eventDate >= new Date();

  return (
    <Link
      to={`/events/${event.id}`}
      className="block bg-gray-900 border border-gray-800 rounded-lg p-5 hover:border-gray-600 transition-colors"
    >
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-semibold text-white">{event.name}</h3>
          <p className="text-sm text-gray-400 mt-1">
            {eventDate.toLocaleDateString('en-US', {
              weekday: 'short',
              month: 'short',
              day: 'numeric',
              year: 'numeric',
            })}
          </p>
          {event.location && (
            <p className="text-xs text-gray-500 mt-0.5">{event.location}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {isUpcoming && (
            <span className="text-xs bg-red-500/20 text-red-400 px-2 py-0.5 rounded">
              Upcoming
            </span>
          )}
          <span className="text-xs text-gray-500">{event.fight_count} fights</span>
        </div>
      </div>
    </Link>
  );
}
