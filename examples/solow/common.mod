// ---------------------------------------------------------------------------
// common.mod — shared core of the continuous-time Solow–Swan examples.
//
// This file is not run on its own. Each scenario file pulls it in with
//
//     @#include "common.mod"
//
// and then adds its own initval, shocks and simulate blocks. Keeping the
// declarations, the model and the analytical steady state here means the
// scenarios differ only in the savings rate / productivity path and where the
// economy starts — see the sibling solow*.mod files and README.md.
//
// The economy: the textbook Solow–Swan growth model with a single state
// variable,
//
//   K  capital stock
//
// and output Y as a static function of the state. There is no jump variable:
// capital is purely predetermined and the law of motion is a single ordinary
// differential equation, so this is a pure initial-value problem (no saddle
// path, no forward-looking root). The savings rate `sav` and total factor
// productivity `A` are exogenous so that they can be shocked.
//
//   diff(K) = sav * Y - delta * K
//
// gross investment sav*Y less depreciation delta*K. With Y = A*K^alpha the
// per-capita capital stock converges monotonically to its unique positive
// steady state (sav*A/delta)^(1/(1-alpha)) from any positive starting point.
// ---------------------------------------------------------------------------

var(state) K;        // capital is the only state; it carries a time derivative
var        Y;        // output is a static (algebraic) function of K
varexo     sav, A;   // savings rate and productivity — exogenous, so shockable

parameters alpha, delta;
alpha = 0.3;         // capital share in production
delta = 0.05;        // depreciation rate

model;
  // production (Cobb–Douglas)
  Y = A * K^alpha;

  // capital accumulation: gross saving minus depreciation
  diff(K) = sav * Y - delta * K;
end;

// Analytical steady state as a function of the parameters and the exogenous.
steady_state_model;
  K = (sav * A / delta)^(1 / (1 - alpha));   // diff(K) = 0
  Y = A * K^alpha;
end;
