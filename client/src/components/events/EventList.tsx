import type { EventSummary } from '../../types';
import EventCard from './EventCard';

interface EventListProps {
  events: EventSummary[];
}

export default function EventList({ events }: EventListProps) {
  if (events.length === 0) {
    return (
      <div className="py-12 text-center text-muted-foreground">
        No events found.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {events.map((event) => (
        <EventCard key={event.id} event={event} />
      ))}
    </div>
  );
}
