// ---------------------------------------------------------------------------
// common.mod — shared core of the continuous-time Cagan examples.
//
// This file is not run on its own. Each scenario file pulls it in with
//
//     @#include "common.mod"
//
// and then adds its own shocks and simulate blocks. Keeping the declarations,
// the model and the analytical steady state here means the scenarios differ
// only in how the money supply is shocked — see the sibling cagan*.mod files
// and README.md.
//
// The economy: Cagan's (1956) model of money and prices under perfect
// foresight. There is a single endogenous variable, the (log) price level
//
//   p  the price level — a forward-looking JUMP
//
// and a single exogenous driver, the (log) money supply
//
//   m  the money supply
//
// Real money demand is a decreasing function of expected inflation, which under
// perfect foresight equals actual inflation dp/dt:
//
//   m - p = -alpha * dp/dt,
//
// where alpha > 0 is the semi-elasticity of money demand to expected inflation.
// Rearranged, this is the law of motion of the price level:
//
//   diff(p) = (p - m) / alpha.
//
// The coefficient 1/alpha on p is POSITIVE, so the price level is the unstable
// (forward-looking) root: it is pinned not by an initial condition but by the
// requirement that it not explode. The stable solution makes p the discounted
// present value of all future money,
//
//   p(t) = (1/alpha) * \int_t^\infty exp(-(s-t)/alpha) m(s) ds,
//
// so prices LEAD anticipated money. There is no predetermined state and hence
// no initval block: a pure forward-looking model.
// ---------------------------------------------------------------------------

var(jump)  p;        // the (log) price level — forward-looking
varexo     m;        // the (log) money supply

parameters alpha;
alpha = 2;           // semi-elasticity of money demand to expected inflation

model;
  // Cagan money demand, m - p = -alpha * dp/dt, written as the law of motion:
  diff(p) = (p - m) / alpha;
end;

// Analytical steady state: with dp/dt = 0, prices equal money.
steady_state_model;
  p = m;
end;
