// goodwin.mod — baseline growth cycle (moderate amplitude).
//
// The economy starts at the bottom of its employment swing (v below its
// long-run value v* = 0.72, with the wage share at u* = 0.70) and traces a
// closed Lotka–Volterra orbit: booms (rising employment) pull the wage share
// up, which squeezes profits and investment, cooling employment, which lets
// the wage share fall, which restores profits — and the cycle repeats. There
// is no shock and no terminal condition; the path is fully determined by the
// initial condition below.

@#include "common.mod"

initval;
  v = 0.58;     // employment rate, below v* = 0.72 (start of the upswing)
  u = 0.70;     // wage share at its long-run value u* (a turning point of v)
end;

simulate(T = 120, N = 2400);
