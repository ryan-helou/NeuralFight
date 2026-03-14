import { Link } from 'react-router-dom';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { EventSummary } from '../../types';

interface EventCardProps {
  event: EventSummary;
}

export default function EventCard({ event }: EventCardProps) {
  const eventDate = new Date(event.date + 'T12:00:00');
  const isUpcoming = eventDate >= new Date(new Date().toDateString());

  return (
    <Link to={`/events/${event.id}`}>
      <Card className="transition-colors hover:bg-accent/50">
        <CardContent className="flex items-center justify-between p-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h3 className="truncate font-semibold">{event.name}</h3>
              {isUpcoming && (
                <Badge variant="destructive" className="shrink-0 text-[10px] px-1.5 py-0">
                  UPCOMING
                </Badge>
              )}
            </div>
            <p className="mt-0.5 text-sm text-muted-foreground">
              {eventDate.toLocaleDateString('en-US', {
                weekday: 'short',
                month: 'short',
                day: 'numeric',
                year: 'numeric',
              })}
              {event.location && (
                <span className="text-muted-foreground/60"> &middot; {event.location}</span>
              )}
            </p>
          </div>
          <span className="shrink-0 text-xs text-muted-foreground">
            {event.fight_count} fights
          </span>
        </CardContent>
      </Card>
    </Link>
  );
}
