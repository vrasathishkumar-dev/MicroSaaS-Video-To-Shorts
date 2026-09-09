/**
 * Dark ambient background for landing and auth pages.
 * Restream-inspired: deep navy with a subtle blue glow at the top.
 */
export function MeshBackground() {
  return (
    <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-background">
      {/* Radial glow top-center — subtle blue haze */}
      <div
        className="absolute -top-[20%] left-1/2 -translate-x-1/2 h-[600px] w-[900px] rounded-full opacity-30"
        style={{
          background:
            'radial-gradient(ellipse at center, oklch(0.60 0.20 264 / 40%) 0%, transparent 70%)',
        }}
      />
      {/* Bottom-right small accent glow */}
      <div
        className="absolute -bottom-24 -right-24 h-80 w-80 rounded-full opacity-20"
        style={{
          background:
            'radial-gradient(circle, oklch(0.70 0.16 264 / 30%) 0%, transparent 70%)',
        }}
      />
      {/* Subtle noise/grain texture overlay */}
      <div
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='1'/%3E%3C/svg%3E")`,
          backgroundSize: '256px 256px',
        }}
      />
    </div>
  );
}
