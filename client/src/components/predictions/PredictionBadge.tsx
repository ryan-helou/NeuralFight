import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface PredictionBadgeProps {
  fighter1Name: string;
  fighter2Name: string;
  fighter1Prob: number;
  fighter2Prob: number;
}

export default function PredictionBadge({
  fighter1Name,
  fighter2Name,
  fighter1Prob,
  fighter2Prob,
}: PredictionBadgeProps) {
  const f1Pct = Math.round(fighter1Prob * 100);
  const f2Pct = Math.round(fighter2Prob * 100);
  const favored = fighter1Prob >= 0.5 ? fighter1Name : fighter2Name;
  const favoredPct = Math.max(f1Pct, f2Pct);
  const favoredColor = fighter1Prob >= 0.5 ? 'text-blue-400' : 'text-red-400';

  return (
    <Card>
      <CardHeader className="pb-2 text-center">
        <CardTitle className="text-sm font-medium text-muted-foreground">Winner Prediction</CardTitle>
      </CardHeader>
      <CardContent className="text-center">
        <div className={`text-2xl font-bold ${favoredColor}`}>{favored}</div>
        <div className="mt-0.5 text-3xl font-black tabular-nums">{favoredPct}%</div>

        <div className="mt-6 flex items-center justify-center gap-8">
          <div className="text-center">
            <div className={`text-xl font-bold tabular-nums ${fighter1Prob >= 0.5 ? 'text-blue-400' : 'text-muted-foreground'}`}>
              {f1Pct}%
            </div>
            <div className="mt-0.5 text-xs text-muted-foreground">{fighter1Name}</div>
          </div>
          <div className="text-center">
            <div className={`text-xl font-bold tabular-nums ${fighter2Prob >= 0.5 ? 'text-red-400' : 'text-muted-foreground'}`}>
              {f2Pct}%
            </div>
            <div className="mt-0.5 text-xs text-muted-foreground">{fighter2Name}</div>
          </div>
        </div>

        <div className="mt-4 flex h-2.5 overflow-hidden rounded-full bg-muted">
          <div className="bg-blue-500 transition-all" style={{ width: `${f1Pct}%` }} />
          <div className="bg-red-500 transition-all" style={{ width: `${f2Pct}%` }} />
        </div>
      </CardContent>
    </Card>
  );
}
