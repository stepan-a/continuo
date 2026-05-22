// tobinq_surprise.mod — an unanticipated permanent change (an MIT shock).
//
// The eventual path is identical to tobinq_anticipated.mod — profitability is 1
// up to t = 5 and 1.5 afterwards — but here the firm does *not* see it coming.
// The two `path at t=...` entries declare two reveal times: until t = 5 the
// firm believes A stays at 1 forever; at t = 5 it is surprised by the new
// permanent level. Each reveal partitions the horizon into a segment solved
// under the belief active at its start.
//
// The signature: nothing moves before t = 5 (q stays on the old steady state),
// then everything jumps at the reveal. That is the opposite of the anticipated
// case, where q jumps at t = 0.

@#include "common.mod"

initval(steady);        // first belief has A = 1 at t = 0: anchors at A = 1 SS
end;

shocks;
  var A;
  path at t=0 = 1;      // belief until the next reveal: A stays at 1
  path at t=5 = 1.5;    // surprise at t=5: A is now 1.5 forever
end;

simulate(T = 50, N = 300);
