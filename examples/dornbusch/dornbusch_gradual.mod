// dornbusch_gradual.mod — a gradual, pre-announced monetary expansion.
//
// Money grows smoothly from 0 to 0.1 over the interval [0, 10] (a ramp), known
// from t = 0. Because the increase is slow and anticipated, the sticky price
// has time to keep pace and the exchange rate need not overshoot: s and p rise
// roughly together to the new steady state, with little or no impact jump.
//
// Contrast with dornbusch.mod, where the *same* eventual money level arrives at
// once and unanticipated, forcing the exchange rate to overshoot.

@#include "common.mod"

initval(steady);        // m = 0 at t = 0, so this anchors at the m = 0 SS
end;

shocks;
  var m;
  path = 0.1 * ramp(t, 0, 10);   // money grows linearly 0 -> 0.1 over [0, 10]
end;

simulate(T = 30, N = 300);
