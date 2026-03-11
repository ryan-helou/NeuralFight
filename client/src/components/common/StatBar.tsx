interface StatBarProps {
  label: string;
  leftValue: number;
  rightValue: number;
  leftLabel?: string;
  rightLabel?: string;
  format?: (v: number) => string;
}

export default function StatBar({
  label,
  leftValue,
  rightValue,
  leftLabel,
  rightLabel,
  format = (v) => String(v),
}: StatBarProps) {
  const total = leftValue + rightValue || 1;
  const leftPct = (leftValue / total) * 100;

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-gray-400">
        <span>{leftLabel ?? format(leftValue)}</span>
        <span className="text-gray-500">{label}</span>
        <span>{rightLabel ?? format(rightValue)}</span>
      </div>
      <div className="flex h-2 rounded-full overflow-hidden bg-gray-800">
        <div
          className="bg-blue-500 transition-all"
          style={{ width: `${leftPct}%` }}
        />
        <div
          className="bg-red-500 transition-all"
          style={{ width: `${100 - leftPct}%` }}
        />
      </div>
    </div>
  );
}
