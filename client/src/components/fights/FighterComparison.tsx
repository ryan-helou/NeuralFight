import type { FightDetail } from '../../types';
import StatBar from '../common/StatBar';

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

  // Aggregate round stats
  const f1Total = aggregateRounds(fight.fighter_1_rounds);
  const f2Total = aggregateRounds(fight.fighter_2_rounds);

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
      {/* Fighter names header */}
      <div className="flex justify-between items-center mb-6">
        <div className="text-center flex-1">
          <h3 className="text-lg font-bold text-blue-400">{f1.name}</h3>
          {f1.nickname && <p className="text-xs text-gray-500">"{f1.nickname}"</p>}
        </div>
        <div className="text-gray-600 text-sm px-4">vs</div>
        <div className="text-center flex-1">
          <h3 className="text-lg font-bold text-red-400">{f2.name}</h3>
          {f2.nickname && <p className="text-xs text-gray-500">"{f2.nickname}"</p>}
        </div>
      </div>

      {/* Physical stats */}
      <div className="space-y-2 mb-6">
        {stats.map((s) => (
          <div key={s.label} className="flex justify-between text-sm">
            <span className="text-gray-300">{s.left}</span>
            <span className="text-gray-500">{s.label}</span>
            <span className="text-gray-300">{s.right}</span>
          </div>
        ))}
      </div>

      {/* Fight stats bars */}
      {f1Total && f2Total && (
        <div className="space-y-3">
          <h4 className="text-sm text-gray-400 font-medium">Fight Stats</h4>
          <StatBar label="Sig. Strikes" leftValue={f1Total.sig_strikes_landed} rightValue={f2Total.sig_strikes_landed} />
          <StatBar label="Total Strikes" leftValue={f1Total.total_strikes_landed} rightValue={f2Total.total_strikes_landed} />
          <StatBar label="Takedowns" leftValue={f1Total.takedowns_landed} rightValue={f2Total.takedowns_landed} />
          <StatBar label="Knockdowns" leftValue={f1Total.knockdowns} rightValue={f2Total.knockdowns} />
          <StatBar
            label="Control Time"
            leftValue={f1Total.control_time_seconds}
            rightValue={f2Total.control_time_seconds}
            format={(v) => `${Math.floor(v / 60)}:${String(v % 60).padStart(2, '0')}`}
          />
          <StatBar label="Sub. Attempts" leftValue={f1Total.submissions_attempted} rightValue={f2Total.submissions_attempted} />
        </div>
      )}
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
