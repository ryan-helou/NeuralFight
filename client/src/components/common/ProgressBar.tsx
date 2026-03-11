interface ProgressBarProps {
  value: number; // 0-1
  color?: string;
  label?: string;
}

export default function ProgressBar({
  value,
  color = 'bg-red-500',
  label,
}: ProgressBarProps) {
  const pct = Math.round(value * 100);

  return (
    <div className="space-y-1">
      {label && (
        <div className="flex justify-between text-xs">
          <span className="text-gray-400">{label}</span>
          <span className="text-white font-medium">{pct}%</span>
        </div>
      )}
      <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
