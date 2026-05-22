// ---------------------------------------------------------------------------
// common.mod — shared core of the continuous-time Tobin's q examples.
//
// This file is not run on its own. Each scenario file pulls it in with
//
//     @#include "common.mod"
//
// and then adds its own initval, shocks and simulate blocks. Keeping the
// declarations, the model and the analytical steady state here means the
// scenarios differ only in how profitability is shocked and where the economy
// starts — see the sibling tobinq*.mod files and README.md.
//
// The economy: a textbook q theory of investment with convex (quadratic)
// capital adjustment costs. There is one state variable,
//
//   K  installed capital stock
//
// one jump variable,
//
//   q  Tobin's q — the shadow value of an extra unit of installed capital
//
// investment I as a static (algebraic) function of the state and the jump, and
// profitability A as the exogenous driving variable.
//
// A firm chooses investment to maximise the present value of profits A*K^alpha
// net of a convex adjustment cost. The first-order conditions give an optimal
// investment rule linear in q,
//
//   I = K * (q - 1) / phi,
//
// so investment is positive exactly when installed capital is worth more than
// its replacement cost (q > 1). With decreasing returns to capital (alpha < 1)
// the marginal product alpha*A*K^(alpha-1) pins down a finite steady state.
// ---------------------------------------------------------------------------

var(state) K;        // installed capital carries a time derivative
var(jump)  q;        // Tobin's q is forward-looking (jumps at surprises)
var        I;        // investment is a static (algebraic) function of K and q
varexo     A;        // profitability (marginal-revenue-product shifter)

parameters alpha, r, delta, phi;
alpha = 0.3;         // curvature of profits in capital (decreasing returns)
r     = 0.05;        // discount rate
delta = 0.1;         // depreciation rate
phi   = 2;           // adjustment-cost parameter (higher = costlier to invest)

model;
  // capital accumulation: net investment less depreciation
  diff(K) = K * (q - 1) / phi - delta * K;

  // the costate (arbitrage) equation for q: the required return r+delta on the
  // installed unit equals its marginal profit plus the saved adjustment cost
  diff(q) = (r + delta) * q - alpha * A * K^(alpha - 1) - (q - 1)^2 / (2 * phi);

  // optimal investment rule from the first-order condition
  I = K * (q - 1) / phi;
end;

// Analytical steady state as a function of the parameters and A.
steady_state_model;
  q = 1 + phi * delta;                                                       // diff(K) = 0
  K = (((r + delta) * (1 + phi * delta) - phi * delta^2 / 2) / (alpha * A))^(1 / (alpha - 1));  // diff(q) = 0
  I = delta * K;                                                             // gross = net + depreciation
end;
