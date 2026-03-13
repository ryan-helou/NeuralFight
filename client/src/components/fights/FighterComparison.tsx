import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import type { FightDetail } from '../../types';

interface FighterComparisonProps {
  fight: FightDetail;
}

export default function FighterComparison({ fight }: FighterComparisonProps) {
  const { fighter_1: f1, fighter_2: f2 } = fight;

  const formatHeight = (inches: number | null) => {
    if (!inches) return '--';
    const ft = Math.floor(inches / 12);
    const remain = inches % 12;
    return `${ft}'${remain}"`;
  };

  const stats = [
    { label: 'Height', left: formatHeight(f1.height_inches), right: formatHeight(f2.height_inches) },
    { label: 'Reach', left: f1.reach_inches ? `${f1.reach_inches}"` : '--', right: f2.reach_inches ? `${f2.reach_inches}"` : '--' },
    { label: 'Stance', left: f1.stance || '--', right: f2.stance || '--' },
  ];

  const f1Total = aggregateRounds(fight.fighter_1_rounds);
  const f2Total = aggregateRounds(fight.fighter_2_rounds);

  return (
    <Card>
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between">
          <div className="text-center flex-1">
            <CardTitle className="text-blue-400">{f1.name}</CardTitle>
            {f1.nickname && <p className="mt-0.5 text-xs text-muted-foreground">"{f1.nickname}"</p>}
          </div>
          <span className="text-xs font-medium text-muted-foreground px-3">vs</span>
          <div className="text-center flex-1">
            <CardTitle className="text-red-400">{f2.name}</CardTitle>
            {f2.nickname && <p className="mt-0.5 text-xs text-muted-foreground">"{f2.nickname}"</p>}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Physical stats */}
        <div className="space-y-2">
          {stats.map((s) => (
            <div key={s.label} className="flex justify-between text-sm">
              <span className="font-medium">{s.left}</span>
              <span className="text-muted-foreground text-xs">{s.label}</span>
              <span className="font-medium">{s.right}</span>
            </div>
          ))}
        </div>

        {/* Fight stats */}
        {f1Total && f2Total && (
          <>
            <Separator />
            <div className="space-y-3">
              <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Fight Stats</h4>
              <StatRow label="Sig. Strikes" left={f1Total.sig_strikes_landed} right={f2Total.sig_strikes_landed} />
              <StatRow label="Total Strikes" left={f1Total.total_strikes_landed} right={f2Total.total_strikes_landed} />
              <StatRow label="Takedowns" left={f1Total.takedowns_landed} right={f2Total.takedowns_landed} />
              <StatRow label="Knockdowns" left={f1Total.knockdowns} right={f2Total.knockdowns} />
              <StatRow
                label="Control Time"
                left={f1Total.control_time_seconds}
                right={f2Total.control_time_seconds}
                format={(v) => `${Math.floor(v / 60)}:${String(v % 60).padStart(2, '0')}`}
              />
              <StatRow label="Sub. Attempts" left={f1Total.submissions_attempted} right={f2Total.submissions_attempted} />
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function StatRow({
  label,
  left,
  right,
  format = (v: number) => String(v),
}: {
  label: string;
  left: number;
  right: number;
  format?: (v: number) => string;
}) {
  const total = left + right || 1;
  const leftPct = (left / total) * 100;

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="font-medium">{format(left)}</span>
        <span className="text-muted-foreground">{label}</span>
        <span className="font-medium">{format(right)}</span>
      </div>
      <div className="flex h-1.5 overflow-hidden rounded-full bg-muted">
        <div className="bg-blue-500 transition-all" style={{ width: `${leftPct}%` }} />
        <div className="bg-red-500 transition-all" style={{ width: `${100 - leftPct}%` }} />
      </div>
    </div>
  );
}

function aggregateRounds(rounds: FightDetail['fighter_1_rounds']) {
  if (rounds.length === 0) return null;
  return {
    sig_strikes_landed: rounds.reduce((s, r) => s + r.sig_strikes_landed, 0),
    total_strikes_landed: rounds.reduce((s, r) => s + r.total_strikes_landed, 0),
    takedowns_landed: rounds.reduce((s, r) => s + r.takedowns_landed, 0),
    knockdowns: rounds.reduce((s, r) => s + r.knockdowns, 0),
    control_time_seconds: rounds.reduce((s, r) => s + r.control_time_seconds, 0),
    submissions_attempted: rounds.reduce((s, r) => s + r.submissions_attempted, 0),
  };
}
