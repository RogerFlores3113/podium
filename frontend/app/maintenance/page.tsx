export const metadata = {
  title: "Podium — Temporarily Offline",
};

export default function MaintenancePage() {
  return (
    <main
      className="flex min-h-screen flex-col items-center justify-center px-6 text-center"
      style={{ backgroundColor: "var(--bg-base)", color: "var(--text-primary)" }}
    >
      <div className="max-w-md">
        <h1 className="text-2xl font-semibold mb-4">Podium is offline for now</h1>
        <p className="mb-3" style={{ color: "var(--text-muted)" }}>
          This is a portfolio project, and running it on AWS costs real money
          around the clock. I&apos;ve paused the live deployment to keep costs
          down while it&apos;s not actively being reviewed.
        </p>
        <p className="mb-6" style={{ color: "var(--text-muted)" }}>
          The code, infrastructure, and architecture are all intact and
          documented — nothing was lost, it&apos;s just switched off.
        </p>
        <a
          href="https://github.com/RogerFlores3113/podium"
          className="inline-block rounded-md px-4 py-2 font-medium"
          style={{ backgroundColor: "var(--accent-warm)", color: "var(--bg-base)" }}
        >
          View the source on GitHub
        </a>
      </div>
    </main>
  );
}
