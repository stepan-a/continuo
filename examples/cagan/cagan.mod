// cagan.mod — baseline scenario: an anticipated permanent monetary expansion.
//
// At t = 0 agents already know that money will step permanently from 0 to 0.2
// at t = 5. Because everything is known up front this is a single belief (one
// segment): the path is just a time-dependent function, revealed at t = 0.
//
// Because the price level is the present value of future money, prices move
// *immediately* and rise gradually toward the new level, reaching ~0.2 around
// t = 5 — that is, prices LEAD the money increase rather than follow it.
//
// Compare with cagan_surprise.mod, which has the *same* eventual money path but
// where agents only learn about it at t = 5.

@#include "common.mod"

shocks;
  var m;
  path = 0.2 * step(t, 5);   // known at t=0, takes effect at t=5
end;

simulate(T = 20, N = 200);
