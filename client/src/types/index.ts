export interface Fighter {
  id: number;
  name: string;
  nickname: string | null;
  height_inches: number | null;
  reach_inches: number | null;
  dob: string | null;
  stance: string | null;
}

export interface EventSummary {
  id: number;
  name: string;
  date: string;
  location: string | null;
  fight_count: number;
}

export interface FightSummary {
  id: number;
  fighter_1_name: string;
  fighter_2_name: string;
  weight_class: string | null;
  is_title_bout: boolean;
  method: string | null;
  result: string | null;
  winner_name: string | null;
  fighter_1_win_prob: number | null;
  fighter_2_win_prob: number | null;
}

export interface EventDetail {
  id: number;
  name: string;
  date: string;
  location: string | null;
  fights: FightSummary[];
}

export interface RoundStats {
  round_number: number;
  knockdowns: number;
  sig_strikes_landed: number;
  sig_strikes_attempted: number;
  total_strikes_landed: number;
  total_strikes_attempted: number;
  takedowns_landed: number;
  takedowns_attempted: number;
  submissions_attempted: number;
  reversals: number;
  control_time_seconds: number;
  head_strikes_landed: number;
  head_strikes_attempted: number;
  body_strikes_landed: number;
  body_strikes_attempted: number;
  leg_strikes_landed: number;
  leg_strikes_attempted: number;
  distance_strikes_landed: number;
  distance_strikes_attempted: number;
  clinch_strikes_landed: number;
  clinch_strikes_attempted: number;
  ground_strikes_landed: number;
  ground_strikes_attempted: number;
}

export interface FightDetail {
  id: number;
  event_name: string;
  fighter_1: Fighter;
  fighter_2: Fighter;
  winner_name: string | null;
  weight_class: string | null;
  is_title_bout: boolean;
  method: string | null;
  method_category: string | null;
  finish_round: number | null;
  finish_time: string | null;
  total_rounds: number | null;
  referee: string | null;
  result: string | null;
  fighter_1_rounds: RoundStats[];
  fighter_2_rounds: RoundStats[];
}

export interface Prediction {
  fight_id: number;
  model_version: string;
  fighter_1_win_prob: number;
  fighter_2_win_prob: number;
  ko_tko_prob: number | null;
  submission_prob: number | null;
  decision_prob: number | null;
  predicted_round: number | null;
  round_probabilities: Record<string, number> | null;
  method_by_fighter: Record<string, Record<string, number>> | null;
  upset_score: number | null;
  betting_confidence: number | null;
  rationale: string | null;
  feature_importances: Array<{ name: string; shap_value: number }> | null;
}

export interface Odds {
  fight_id: number;
  source: string;
  fighter_1_name: string;
  fighter_2_name: string;
  fighter_1_decimal: number;
  fighter_2_decimal: number;
  fighter_1_american: number;
  fighter_2_american: number;
  fighter_1_implied: number;
  fighter_2_implied: number;
  retrieved_at: string;
}

export interface Upset {
  fight_id: number;
  fighter_1_name: string;
  fighter_2_name: string;
  event_name: string;
  fighter_1_win_prob: number;
  fighter_2_win_prob: number;
  upset_score: number;
  betting_confidence: number | null;
}
