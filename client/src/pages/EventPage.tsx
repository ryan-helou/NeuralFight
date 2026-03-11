import { useQuery } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { getEvent } from '../api/events';
import FightCard from '../components/fights/FightCard';

export default function EventPage() {
  const { id } = useParams<{ id: string }>();
  const eventId = Number(id);

  const { data: event, isLoading } = useQuery({
    queryKey: ['event', eventId],
    queryFn: () => getEvent(eventId),
    enabled: !isNaN(eventId),
  });

  if (isLoading) {
    return <div className="text-gray-500 text-center py-12">Loading event...</div>;
  }

  if (!event) {
    return <div className="text-gray-500 text-center py-12">Event not found.</div>;
  }

  const eventDate = new Date(event.date);

  return (
    <div>
      <Link to="/" className="text-sm text-gray-500 hover:text-gray-300 mb-4 inline-block">
        &larr; All Events
      </Link>

      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">{event.name}</h1>
        <div className="text-gray-400 mt-1">
          {eventDate.toLocaleDateString('en-US', {
            weekday: 'long',
            month: 'long',
            day: 'numeric',
            year: 'numeric',
          })}
          {event.location && <span className="text-gray-500"> &middot; {event.location}</span>}
        </div>
      </div>

      <div className="grid gap-3">
        {event.fights.map((fight) => (
          <FightCard key={fight.id} fight={fight} />
        ))}
      </div>
    </div>
  );
}
