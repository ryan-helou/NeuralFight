import api from './client';
import type { FightDetail, Odds, Prediction, Upset, ValueBet } from '../types';

export async function getPrediction(fightId: number) {
  const { data } = await api.get<Prediction>(`/predictions/fight/${fightId}`);
  return data;
}

export async function generatePrediction(fightId: number) {
  const { data } = await api.post<Prediction>(`/predictions/fight/${fightId}`);
  return data;
}

export async function generateEventPredictions(eventId: number) {
  const { data } = await api.post<{ generated: number; total: number }>(`/predictions/event/${eventId}`);
  return data;
}

export async function generateUpcomingPredictions() {
  const { data } = await api.post<{ generated: number; total: number; already_done?: boolean }>('/predictions/generate-upcoming');
  return data;
}

export async function getUpcomingPredictions() {
  const { data } = await api.get<Prediction[]>('/predictions/upcoming');
  return data;
}

export async function getUpsets(minScore = 30) {
  const { data } = await api.get<Upset[]>('/predictions/upsets', {
    params: { min_score: minScore },
  });
  return data;
}

export async function getFight(id: number) {
  const { data } = await api.get<FightDetail>(`/fights/${id}`);
  return data;
}

export async function getOdds(fightId: number) {
  const { data } = await api.get<Odds | null>(`/odds/fight/${fightId}`);
  return data;
}

export async function getValueBets() {
  const { data } = await api.get<ValueBet[]>('/predictions/value-bets');
  return data;
}
