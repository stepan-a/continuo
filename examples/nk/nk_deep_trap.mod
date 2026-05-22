// nk_deep_trap.mod — a longer *expected* trap, and a much deeper recession.
//
// Identical demand shock to nk_trap.mod (rnat falls to RLOW = -0.04), but the
// trap is expected to last twice as long: DUR = 4 instead of 2. Because x and
// pi are forward-looking, the longer expected duration of the ZLB episode feeds
// back into today's decisions: the recession is far deeper on impact
// (x_min ~ -0.36) than under the shorter trap. This is the hallmark
// forward-looking result of the liquidity-trap literature — a longer *expected*
// trap causes a deeper recession TODAY. The whole path is known at t = 0.

@#include "common.mod"

shocks;
  var rnat;
  path = 0.02 + (-0.04 - 0.02) * pulse(t, 0, 4);   // rnat: -0.04 on [0,4), else 0.02
end;

simulate(T = 25, N = 500);
