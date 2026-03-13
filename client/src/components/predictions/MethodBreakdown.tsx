import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import type { Prediction } from '../../types';

interface MethodBreakdownProps {
  prediction: Prediction;
  fighter1Name?: string;
  fighter2Name?: string;
}

const METHOD_LABELS: Record<string, string> = {
  ko_tko: 'KO/TKO',
  submission: 'Submission',
  decision: 'Decision',
};

const METHOD_COLORS: Record<string, string> = {
  ko_tko: 'bg-red-500',
  submission: 'bg-blue-500',
  decision: 'bg-purple-500',
};

export default function MethodBreakdown({ prediction, fighter1Name, fighter2Name }: MethodBreakdownProps) {
  const methods = [
    { key: 'ko_tko', prob: prediction.ko_tko_prob ?? 0 },
    { key: 'submission', prob: prediction.submission_prob ?? 0 },
    { key: 'decision', prob: prediction.decision_prob ?? 0 },
  ];

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium text-muted-foreground">Method of Victory</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {methods.map(({ key, prob }) => (
          <div key={key} className="space-y-1">
            <div className="flex justify-between text-sm">
              <span className="font-medium">{METHOD_LABELS[key]}</span>
              <span className="tabular-nums text-muted-foreground">{Math.round(prob * 100)}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-muted">
              <div
                className={`h-full rounded-full ${METHOD_COLORS[key]} transition-all`}
                style={{ width: `${prob * 100}%` }}
              />
            </div>
          </div>
        ))}

        {prediction.method_by_fighter && (
          <>
            <Separator className="my-3" />
            <div className="grid grid-cols-2 gap-4">
              {['fighter_1', 'fighter_2'].map((fKey) => {
                const fighterMethods = prediction.method_by_fighter![fKey];
                if (!fighterMethods) return null;
                const name = fKey === 'fighter_1' ? (fighter1Name || 'Fighter 1') : (fighter2Name || 'Fighter 2');
                const color = fKey === 'fighter_1' ? 'text-blue-400' : 'text-red-400';

                return (
                  <div key={fKey}>
                    <div className={`mb-1.5 text-xs font-medium ${color}`}>{name}</div>
                    {Object.entries(fighterMethods).map(([m, p]) => (
                      <div key={m} className="flex justify-between text-xs text-muted-foreground">
                        <span>{METHOD_LABELS[m] || m}</span>
                        <span className="tabular-nums">{Math.round(p * 100)}%</span>
                      </div>
                    ))}
                  </div>
                );
              })}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
