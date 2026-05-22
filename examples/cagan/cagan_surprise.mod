// cagan_surprise.mod — an unanticipated permanent monetary expansion.
//
// The eventual money path is identical to cagan.mod — m is 0 up to t = 5 and
// 0.2 afterwards — but here agents do *not* see it coming. The two
// `path at t=...` entries declare two reveal times: until t = 5 they believe
// money stays at 0 forever; at t = 5 they are surprised by the new permanent
// level. Each reveal partitions the horizon into a segment solved under the
// belief active at its start.
//
// The signature: the price level stays flat at 0 until t = 5, then jumps
// straight to 0.2 at the reveal. That is the opposite of the anticipated case,
// where prices move from t = 0 onward.

@#include "common.mod"

shocks;
  var m;
  path at t=0 = 0;     // belief until the next reveal: money stays at 0
  path at t=5 = 0.2;   // surprise at t=5: money is now 0.2 forever
end;

simulate(T = 20, N = 200);
