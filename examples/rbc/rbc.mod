// rbc.mod — baseline scenario: a transitory productivity shock delivered
// through the *initial condition*.
//
// The economy starts on its steady state for capital, while productivity is
// displaced 5% above its mean at t = 0 (the realised innovation). There are
// no further innovations (e = 0 throughout), so productivity mean-reverts and
// capital and consumption follow the saddle path back to the steady state —
// the familiar hump-shaped response to a transitory technology shock.

@#include "common.mod"

initval;
  K = steady_state(K);   // capital at its (e = 0) steady state
  A = 1.05;              // productivity displaced +5% — the t = 0 innovation
end;

shocks;
  var e;
  path = 0;             // no further innovations: productivity just reverts
end;

simulate(T = 50, N = 250);
