import api from './client';
import type { EventDetail, EventSummary } from '../types';

export async function getEvents(upcoming = false, limit = 20, offset = 0) {
  const { data } = await api.get<EventSummary[]>('/events', {
    params: { upcoming, limit, offset },
  });
  return data;
}

export async function getEvent(id: number) {
  const { data } = await api.get<EventDetail>(`/events/${id}`);
  return data;
}
