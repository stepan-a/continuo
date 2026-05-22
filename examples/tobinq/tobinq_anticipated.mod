// tobinq_anticipated.mod — an anticipated permanent change.
//
// At t = 0 the firm already knows that profitability will step permanently from
// 1 to 1.5 at t = 5. Because everything is known up front this is a single
// belief (one segment): the path is just a time-dependent function, revealed at
// t = 0. Tobin's q jumps *immediately* at t = 0, well before A increases, and
// the firm starts investing ahead of the change as it brings the news forward.
//
// Compare with tobinq_surprise.mod, which has the *same* eventual path but
// where the firm only learns about it at t = 5.

@#include "common.mod"

initval(steady);        // A = 1 at t = 0, so this anchors at the A = 1 SS
end;

shocks;
  var A;
  path = 1 + 0.5 * step(t, 5);   // known at t=0, takes effect at t=5
end;

simulate(T = 50, N = 300);
