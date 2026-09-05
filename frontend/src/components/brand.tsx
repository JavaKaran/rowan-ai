import Link from "next/link";
export function Brand() {
  return (
    <Link href="/" className="brand" aria-label="Rowan home">
      <span className="brand-mark">
        <i />
        <i />
        <i />
      </span>
      rowan<span className="brand-period">.</span>
    </Link>
  );
}
