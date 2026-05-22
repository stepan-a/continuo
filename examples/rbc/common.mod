// ---------------------------------------------------------------------------
// common.mod — shared core of the continuous-time RBC examples.
//
// This file is not run on its own. Each scenario file pulls it in with
//
//     @#include "common.mod"
//
// and then adds its own initval, shocks and simulate blocks. Keeping the
// declarations, the model and the analytical steady state here means the
// scenarios differ only in how productivity is shocked and where the economy
// starts — see the sibling rbc*.mod files and README.md.
//
// The economy: a textbook Ramsey/RBC model with two state variables,
//
//   K  capital stock
//   A  total factor productivity
//
// one jump variable (consumption C) and output Y as a static function of the
// states. Productivity is a *stable* continuous-time AR(1) — an Ornstein–
// Uhlenbeck process in levels — mean-reverting to 1 at speed `theta`, forced
// by the innovation `e`:
//
//   diff(A) = theta * (1 - A) + e
//
// With e = 0 the solution is A(t) = 1 + (A0 - 1) * exp(-theta t): a deviation
// decays exponentially, the continuous-time analogue of a discrete AR(1) with
// autoregressive root exp(-theta) and half-life ln(2)/theta.
// ---------------------------------------------------------------------------

var(state) K, A;     // capital and productivity carry time derivatives
var(jump)  C;        // consumption is forward-looking (jumps at surprises)
var        Y;        // output is a static (algebraic) function of K and A
varexo     e;        // productivity innovation

parameters alpha, delta, rho, theta;
alpha = 0.33;        // capital share in production
delta = 0.10;        // depreciation rate
rho   = 0.03;        // rate of time preference (discount rate)
theta = 0.50;        // speed of mean reversion of productivity

model;
  // capital accumulation: investment = output minus consumption
  diff(K) = Y - C - delta * K;

  // productivity: stable AR(1) in levels, mean 1, forced by e
  diff(A) = theta * (1 - A) + e;

  // consumption Euler equation (log utility): dC/C = MPK - delta - rho
  diff(C) = C * (alpha * Y / K - delta - rho);

  // production (Cobb–Douglas)
  Y = A * K^alpha;
end;

// Analytical steady state as a function of the parameters and e.
steady_state_model;
  A = 1 + e / theta;                                  // diff(A) = 0
  K = (alpha * A / (rho + delta))^(1 / (1 - alpha));  // MPK = rho + delta
  Y = A * K^alpha;
  C = Y - delta * K;                                  // diff(K) = 0
end;
