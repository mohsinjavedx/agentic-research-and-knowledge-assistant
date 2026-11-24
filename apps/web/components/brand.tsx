export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <span className={`brand${compact ? " compact" : ""}`}>
      <svg
        className="brand-mark"
        width="30"
        height="32"
        viewBox="0 0 30 32"
        fill="none"
        aria-hidden="true"
      >
        <path d="M5 5.5 15 2l10 3.5v19L15 30 5 24.5z" stroke="currentColor" strokeWidth="1.5" />
        <path
          d="m5 5.5 10 5 10-5M15 11v19M5 15l10 5 10-5"
          stroke="currentColor"
          strokeWidth="1.5"
        />
        <circle cx="15" cy="11" r="2.5" fill="currentColor" />
      </svg>
      {!compact && (
        <span>
          Research
          <span className="brand-second">
            Assistant<span className="brand-dot">.</span>
          </span>
        </span>
      )}
    </span>
  );
}
