// ---------------------------------------------------------------------------
// common.mod — shared core of the continuous-time New Keynesian / ZLB examples.
//
// This file is not run on its own. Each scenario file pulls it in with
//
//     @#include "common.mod"
//
// and then adds only its own shocks and simulate blocks. Keeping the
// declarations, the model and the analytical steady state here means the
// scenarios differ only in the size and length of the demand shock — see the
// sibling nk_*.mod files and README.md.
//
// The economy: a textbook continuous-time New Keynesian model in the Werning
// (2011) form, with two *forward-looking* variables and no predetermined state,
//
//   x   output gap   (jump)
//   pi  inflation     (jump)
//
// and the nominal policy rate `i` as a static (algebraic) Taylor rule that is
// clamped at zero — the zero lower bound (ZLB). The natural rate of interest
// `rnat` is exogenous; a temporary fall in it is a "demand shock" that can push
// the economy into a liquidity trap where the ZLB binds.
//
//   diff(x)  = sigma * (i - pi - rnat)     dynamic IS (Euler) equation
//   diff(pi) = rho * pi - kappa * x        New Keynesian Phillips curve
//   i        = max(0, rho + phipi*pi + phix*x)   Taylor rule with ZLB
//
// This is a *pure forward-looking* system: both endogenous dynamic variables
// jump, there is no capital-like state to anchor, so the model needs no
// initval block and is pinned down entirely by the terminal steady state and
// the exogenous path of rnat. The ZLB is an occasionally-binding constraint
// written with `max`; its kink is handled by the solver on the time grid.
// ---------------------------------------------------------------------------

var(jump) x, pi;     // output gap and inflation are forward-looking (jumps)
var       i;         // nominal policy rate: static Taylor rule, clamped at 0
varexo    rnat;      // natural (Wicksellian) real rate — the demand shock

parameters sigma, kappa, rho, phipi, phix;
sigma = 1;           // intertemporal elasticity of substitution
kappa = 0.3;         // slope of the New Keynesian Phillips curve
rho   = 0.02;        // rate of time preference (= natural rate in steady state)
phipi = 1.5;         // Taylor-rule response to inflation
phix  = 0.125;       // Taylor-rule response to the output gap

model;
  // dynamic IS: the output gap rises when the real rate exceeds the natural rate
  diff(x) = sigma * (i - pi - rnat);

  // New Keynesian Phillips curve (forward-looking, continuous time)
  diff(pi) = rho * pi - kappa * x;

  // Taylor rule clamped at the zero lower bound
  i = max(0, rho + phipi * pi + phix * x);
end;

// Analytical steady state, consistent with the baseline rnat = rho:
// no inflation, a closed output gap, and the policy rate at its natural level.
steady_state_model;
  x  = 0;
  pi = 0;
  i  = rho;
end;
