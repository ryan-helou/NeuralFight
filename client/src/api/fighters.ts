import api from './client';
import type { Fighter } from '../types';

export async function searchFighters(q: string) {
  const { data } = await api.get<Fighter[]>('/fighters', { params: { q } });
  return data;
}

export async function getFighter(id: number) {
  const { data } = await api.get<Fighter>(`/fighters/${id}`);
  return data;
}
