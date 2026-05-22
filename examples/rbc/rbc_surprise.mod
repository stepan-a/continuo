// rbc_surprise.mod — an unanticipated permanent change (an MIT shock).
//
// The eventual path is identical to rbc_anticipated.mod — the innovation is 0
// up to t = 10 and 0.05 afterwards — but here agents do *not* see it coming.
// The two `path at t=...` entries declare two reveal times: until t = 10 they
// believe e stays at 0 forever; at t = 10 they are surprised by the new
// permanent level. Each reveal partitions the horizon into a segment solved
// under the belief active at its start.
//
// The signature: nothing moves before t = 10 (consumption stays on the old
// steady state), then everything jumps at the reveal. That is the opposite of
// the anticipated case, where the jump happens at t = 0.

@#include "common.mod"

initval(steady);        // first belief has e = 0 at t = 0: anchors at e = 0 SS
end;

shocks;
  var e;
  path at t=0  = 0;      // belief until the next reveal: e stays at 0
  path at t=10 = 0.05;   // surprise at t=10: e is now 0.05 forever
end;

simulate(T = 50, N = 250);
