// goodwin_large.mod — a large-amplitude cycle.
//
// Starting far from the fixed point (v = 0.54 vs v* = 0.72) gives a big,
// markedly non-elliptical orbit: long depressions with low employment punctuated
// by sharp booms. The period is essentially unchanged from the small cycle
// (a Lotka–Volterra centre is isochronous only near the fixed point; here the
// shape distorts but the period stays close), and the wage share swings nearly
// to its full range — the amplitude is set entirely by the initial condition.

@#include "common.mod"

initval;
  v = 0.54;     // well below v* = 0.72: a large orbit
  u = 0.70;
end;

simulate(T = 120, N = 2400);
