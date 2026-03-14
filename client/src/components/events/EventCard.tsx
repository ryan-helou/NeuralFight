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
      <Card className="group transition-all hover:bg-accent/40 hover:border-border/80">
        <CardContent className="flex items-center justify-between px-4 py-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h3 className="truncate text-sm font-semibold">{event.name}</h3>
              {isUpcoming && (
                <Badge variant="outline" className="shrink-0 text-[10px] px-1.5 py-0 border-green-500/40 text-green-400">
                  UPCOMING
                </Badge>
              )}
            </div>
            <p className="mt-0.5 text-xs text-muted-foreground/70">
              {eventDate.toLocaleDateString('en-US', {
                weekday: 'short',
                month: 'short',
                day: 'numeric',
                year: 'numeric',
              })}
              {event.location && (
                <span className="text-muted-foreground/40"> &middot; {event.location}</span>
              )}
            </p>
          </div>
          <Badge variant="secondary" className="shrink-0 text-[11px] tabular-nums">
            {event.fight_count}
          </Badge>
        </CardContent>
      </Card>
    </Link>
  );
}
