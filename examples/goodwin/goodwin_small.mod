// goodwin_small.mod — a small-amplitude cycle.
//
// Starting close to the fixed point (v = 0.66 vs v* = 0.72) gives a small,
// nearly elliptical orbit — the linearised limit, where employment and the
// wage share trace gentle harmonic oscillations a quarter-cycle out of phase.

@#include "common.mod"

initval;
  v = 0.66;     // just below v* = 0.72: a small orbit
  u = 0.70;
end;

simulate(T = 120, N = 2400);
