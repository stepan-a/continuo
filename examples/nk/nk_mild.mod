// nk_mild.mod — a small demand shock, with the ZLB slack throughout.
//
// The natural rate falls from rho = 0.02 to RLOW = 0.01 over [0, 2), then
// returns to rho. The drop is small enough that the Taylor rule keeps the
// policy rate strictly positive (i_min > 0): the max(0, .) constraint never
// binds, so the model behaves like its linear counterpart and the recession is
// mild. Contrast with nk_trap.mod, where a deeper fall in rnat sends i to the
// floor.

@#include "common.mod"

shocks;
  var rnat;
  path = 0.02 + (0.01 - 0.02) * pulse(t, 0, 2);   // rnat: 0.01 on [0,2), else 0.02
end;

simulate(T = 25, N = 500);
