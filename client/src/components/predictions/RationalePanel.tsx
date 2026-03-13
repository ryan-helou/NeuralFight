import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import type { Prediction } from '../../types';

interface RationalePanelProps {
  prediction: Prediction;
  fighter1Name?: string;
  fighter2Name?: string;
}

const SECTION_ICONS: Record<string, string> = {
  'On the feet': '👊',
  'In the grappling department': '🤼',
  'Finishing ability': '💥',
  'Experience and record': '📊',
  'Physical and conditioning': '🏋️',
  'Fight dominance': '⚡',
};

const FEATURE_SHORT_NAMES: Record<string, string> = {
  sig_strikes_per_min_diff: 'Sig. Strikes/min',
  sig_strike_accuracy_diff: 'Strike Accuracy',
  sig_strike_defense_diff: 'Strike Defense',
  takedowns_per_15min_diff: 'Takedowns/15min',
  takedown_defense_diff: 'Takedown Defense',
  knockdown_rate_diff: 'Knockdown Rate',
  finish_rate_ko_diff: 'KO Finish Rate',
  finish_rate_sub_diff: 'Sub Finish Rate',
  win_rate_diff: 'Win Rate',
  reach_diff: 'Reach',
  height_diff: 'Height',
  age_diff: 'Age',
  experience_diff: 'Experience',
  win_streak_diff: 'Win Streak',
  control_time_per_15min_diff: 'Control Time',
  avg_opp_win_rate_diff: 'Opponent Quality',
  avg_beaten_opp_win_rate_diff: 'Quality of Wins',
  avg_lost_to_opp_win_rate_diff: 'Quality of Losses',
  avg_win_dominance_diff: 'Win Dominance',
  avg_loss_dominance_diff: 'Loss Competitiveness',
  finish_speed_diff: 'Finish Speed',
  been_finished_rate_diff: 'Finish Vulnerability',
  layoff_diff: 'Ring Rust',
  strike_dropoff_diff: 'Cardio',
  late_round_win_rate_diff: 'Late-Fight Win Rate',
};

function parseRationale(text: string) {
  const sectionKeys = Object.keys(SECTION_ICONS);

  // Split into headline (first sentence) and sections
  const firstDot = text.indexOf('. ');
  const headline = firstDot >= 0 ? text.slice(0, firstDot + 1) : text;
  const rest = firstDot >= 0 ? text.slice(firstDot + 2) : '';

  if (!rest) return { headline, sections: [], closing: '' };

  // Find section boundaries
  const sections: { title: string; icon: string; bullets: string[] }[] = [];
  let remaining = rest;

  // Try to split by known section prefixes
  const sectionRegex = new RegExp(
    `(${sectionKeys.map((k) => k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')}):?\\s*`,
    'g'
  );

  const parts: { title: string; content: string }[] = [];
  let lastIndex = 0;
  let lastTitle = '';
  let match;

  while ((match = sectionRegex.exec(remaining)) !== null) {
    if (lastTitle) {
      parts.push({ title: lastTitle, content: remaining.slice(lastIndex, match.index).trim() });
    }
    lastTitle = match[1];
    lastIndex = match.index + match[0].length;
  }
  if (lastTitle) {
    parts.push({ title: lastTitle, content: remaining.slice(lastIndex).trim() });
  }

  let closing = '';
  for (const part of parts) {
    // Check if this is a closing statement (no section icon)
    const icon = SECTION_ICONS[part.title];
    if (!icon) {
      closing = part.content;
      continue;
    }

    // Split content into individual sentences as bullets
    const bullets = part.content
      .split(/\.(?:\s|$)/)
      .map((s) => s.trim())
      .filter((s) => s.length > 0)
      .map((s) => (s.endsWith('.') ? s : s + '.'));

    if (bullets.length > 0) {
      sections.push({ title: part.title, icon, bullets });
    }
  }

  // Check for closing statement at the end (not in a section)
  if (!closing && parts.length === 0) {
    closing = rest;
  }

  return { headline, sections, closing };
}

export default function RationalePanel({ prediction, fighter1Name, fighter2Name }: RationalePanelProps) {
  const parsed = prediction.rationale ? parseRationale(prediction.rationale) : null;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium text-muted-foreground">AI Rationale</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {parsed && (
          <>
            <p className="text-sm font-medium">{parsed.headline}</p>

            {parsed.sections.map((section, i) => (
              <div key={i} className="space-y-1.5">
                <div className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  <span>{section.icon}</span>
                  <span>{section.title}</span>
                </div>
                <ul className="space-y-1 pl-5">
                  {section.bullets.map((bullet, j) => (
                    <li key={j} className="text-xs leading-relaxed text-muted-foreground list-disc">
                      {bullet}
                    </li>
                  ))}
                </ul>
              </div>
            ))}

            {parsed.closing && (
              <p className="text-xs italic text-muted-foreground/80">{parsed.closing}</p>
            )}
          </>
        )}

        {prediction.feature_importances && prediction.feature_importances.length > 0 && (
          <>
            <Separator />
            <div>
              <h4 className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Top Factors
              </h4>
              <div className="space-y-1.5">
                {prediction.feature_importances.slice(0, 7).map((feat, i) => {
                  const shortName =
                    Object.entries(FEATURE_SHORT_NAMES).find(([key]) =>
                      feat.name.includes(key)
                    )?.[1] || feat.name;

                  const isPositive = feat.shap_value > 0;
                  const favorName = isPositive
                    ? (fighter2Name || 'F2')
                    : (fighter1Name || 'F1');
                  const favorColor = isPositive ? 'text-red-400' : 'text-blue-400';

                  return (
                    <div key={i} className="flex items-center justify-between text-xs">
                      <span className="text-muted-foreground">{shortName}</span>
                      <span className={`font-medium ${favorColor}`}>
                        Favors {favorName}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
