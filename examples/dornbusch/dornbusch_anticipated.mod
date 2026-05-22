// dornbusch_anticipated.mod — an anticipated permanent monetary expansion.
//
// At t = 0 agents already know that money will step permanently from 0 to 0.1
// at t = 5. Because everything is known up front this is a single belief (one
// segment): the path is just a time-dependent function, revealed at t = 0.
//
// The exchange rate jumps *immediately* at t = 0, well before money actually
// rises, as agents bring forward the news; the sticky price starts moving
// before money does too. Compare with dornbusch.mod, where the same eventual
// money level arrives unanticipated and right away.

@#include "common.mod"

initval(steady);        // m = 0 at t = 0, so this anchors at the m = 0 SS
end;

shocks;
  var m;
  path = 0.1 * step(t, 5);   // known at t=0, takes effect at t=5
end;

simulate(T = 30, N = 300);
