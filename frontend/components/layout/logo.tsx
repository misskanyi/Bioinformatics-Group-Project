// Mark: the PET repeat unit's aromatic ring, cut by an ester bond (the bond PET hydrolases break).
export function LogoMark({ className = "size-8" }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={className} aria-hidden>
      <defs>
        <linearGradient id="lg-mark" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="var(--color-aqua)" />
          <stop offset="1" stopColor="var(--color-sky)" />
        </linearGradient>
      </defs>
      <rect x="1" y="1" width="38" height="38" rx="10" fill="var(--color-hero)" stroke="var(--color-line)" />
      <path d="M20 8.5 29.5 14v11L20 30.5 10.5 25V14Z" fill="none" stroke="url(#lg-mark)" strokeWidth="2" strokeLinejoin="round" />
      <circle cx="20" cy="19.5" r="4.4" fill="none" stroke="var(--color-aqua)" strokeOpacity=".55" strokeWidth="1.4" />
      <path d="M29.5 14 35 10.5M10.5 25 5 28.5" stroke="var(--color-mint)" strokeWidth="2" strokeLinecap="round" />
      <path d="M31.2 9.2 33.8 12.6" stroke="var(--color-amber)" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}
