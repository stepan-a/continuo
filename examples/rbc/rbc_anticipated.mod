// rbc_anticipated.mod — an anticipated permanent change.
//
// At t = 0 agents already know that the innovation will step permanently from
// 0 to 0.05 at t = 10. Because everything is known up front this is a single
// belief (one segment): the path is just a time-dependent function, revealed
// at t = 0. Consumption jumps *immediately* at t = 0, well before the change
// takes effect, as agents bring forward the news.
//
// Compare with rbc_surprise.mod, which has the *same* eventual path but where
// agents only learn about it at t = 10.

@#include "common.mod"

initval(steady);        // e = 0 at t = 0, so this anchors at the e = 0 SS
end;

shocks;
  var e;
  path = 0.05 * step(t, 10);   // known at t=0, takes effect at t=10
end;

simulate(T = 50, N = 250);
