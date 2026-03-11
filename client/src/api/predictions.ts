import api from './client';
import type { FightDetail, Prediction, Upset } from '../types';

export async function getPrediction(fightId: number) {
  const { data } = await api.get<Prediction>(`/predictions/fight/${fightId}`);
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
