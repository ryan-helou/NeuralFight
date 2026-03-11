import type { EventSummary } from '../../types';
import EventCard from './EventCard';

interface EventListProps {
  events: EventSummary[];
}

export default function EventList({ events }: EventListProps) {
  if (events.length === 0) {
    return (
      <div className="text-center text-gray-500 py-12">
        No events found.
      </div>
    );
  }

  return (
    <div className="grid gap-3">
      {events.map((event) => (
        <EventCard key={event.id} event={event} />
      ))}
    </div>
  );
}
