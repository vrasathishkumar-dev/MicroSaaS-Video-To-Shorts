/**
 * Ambient gradient-blob background for landing and auth pages.
 * Render once, absolutely positioned behind page content (`-z-10`).
 */
export function MeshBackground() {
  return (
    <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-background">
      <div className="absolute inset-0 bg-gradient-to-br from-gradient-from/10 via-background to-gradient-to/10" />
      <div className="absolute top-0 left-1/4 h-96 w-96 animate-pulse rounded-full bg-gradient-from/30 blur-3xl" />
      <div className="absolute bottom-0 right-1/4 h-96 w-96 animate-pulse rounded-full bg-gradient-to/30 blur-3xl" />
    </div>
  );
}
