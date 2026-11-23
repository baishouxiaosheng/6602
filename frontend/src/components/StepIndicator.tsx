const labels = [
  "Questionnaire",
  "Steam Library",
  "Profile Summary",
  "Recommendations",
];

interface StepIndicatorProps {
  current: number;
}

export function StepIndicator({ current }: StepIndicatorProps) {
  return (
    <nav aria-label="Recommendation workflow">
      <ol className="step-indicator">
        {labels.map((label, index) => {
          const step = index + 1;
          const state = step === current ? "current" : step < current ? "complete" : "upcoming";
          return (
            <li className={`step-${state}`} key={label} aria-current={step === current ? "step" : undefined}>
              <span>{step < current ? "✓" : step}</span>
              <small>{label}</small>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
