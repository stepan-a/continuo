// nk_trap.mod — a liquidity trap: the demand shock drives the ZLB to bind.
//
// The natural rate falls from rho = 0.02 to RLOW = -0.04 over [0, 2), then
// returns to rho. The negative natural rate is large enough that the Taylor
// rule wants a negative policy rate; the max(0, .) clamp holds i at zero (the
// ZLB binds). With monetary policy stuck at the floor the economy cannot offset
// the shock: output falls (x_min ~ -0.11) and inflation turns negative
// (pi_min ~ -0.03) — a recession with deflation. The whole trap is known at
// t = 0 (a single belief / one segment).

@#include "common.mod"

shocks;
  var rnat;
  path = 0.02 + (-0.04 - 0.02) * pulse(t, 0, 2);   // rnat: -0.04 on [0,2), else 0.02
end;

simulate(T = 25, N = 500);
