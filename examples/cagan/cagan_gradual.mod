// cagan_gradual.mod — a gradual, anticipated monetary expansion (a ramp).
//
// Instead of stepping discontinuously, money rises linearly from 0 to 0.2 over
// the interval [3, 9] and stays there. As in cagan.mod the whole path is known
// at t = 0 (a single segment), so prices respond from t = 0 onward.
//
// Because the price level is the present value of future money, prices LEAD the
// ramp: they begin rising before money does and stay ahead of it through the
// transition, converging to 0.2 once money settles.

@#include "common.mod"

shocks;
  var m;
  path = 0.2 * ramp(t, 3, 9);   // linear 0 -> 0.2 over [3, 9], known at t=0
end;

simulate(T = 20, N = 200);
