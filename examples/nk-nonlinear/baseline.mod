// baseline.mod — fully nonlinear continuous-time New Keynesian model
// (Rotemberg price adjustment, no habit). Two forward-looking variables
// (consumption C and inflation pi) and an algebraic policy rate R subject
// to the zero lower bound. The exogenous natural rate `rnat` drops below
// zero over [0, 2) to trigger a liquidity trap.
//
// See README.md for the full derivation and references.
//
// In this folder each scenario is a self-contained file rather than an
// @#include of a shared common.mod — the three models differ structurally
// (number of state variables, sets of FOCs) so factoring is awkward.

var(jump) C, pi;
var       R, MC;
varexo    rnat;

parameters sigma, eta, eps, phi, rho, phipi;
sigma = 1;       // inverse intertemporal elasticity (log utility for sigma=1)
eta   = 1;       // inverse Frisch elasticity of labour supply
eps   = 6;       // elasticity of substitution between varieties (20% markup)
phi   = 40;      // Rotemberg price-adjustment cost
rho   = 0.02;    // rate of time preference / steady-state natural rate
phipi = 1.5;     // Taylor-rule inflation feedback

model;
  // real marginal cost: MC = w/A with w = N^eta * C^sigma (labour FOC under
  // separable utility, log consumption felicity at sigma=1), Y = A*N = C
  // (resource constraint) and A normalised to 1
  MC = C^(sigma + eta);

  // Taylor rule with zero lower bound on the policy rate
  R = max(0, rho + phipi * pi);

  // continuous-time consumption Euler with a "natural-rate" preference shock:
  // the long-run discount rate rho is replaced inside the household's
  // intertemporal trade-off by the exogenous rnat (baseline = rho)
  diff(C)  = (C / sigma) * (R - pi - rnat);

  // Rotemberg New Keynesian Phillips Curve (continuous time):
  // pi^dot = rho * pi - (eps/phi) * (MC - (eps-1)/eps)
  diff(pi) = rho * pi - (eps / phi) * (MC - (eps - 1) / eps);
end;

steady_state_model;
  pi = 0;                              // zero-inflation steady state
  R  = rho;                            // R = rnat = rho
  MC = (eps - 1) / eps;                // flex-price markup = eps/(eps-1)
  C  = MC^(1 / (sigma + eta));         // from MC = C^(sigma+eta)
end;

shocks;
  var rnat;
  // baseline rnat is rho (= 0.02); the trap pulls it to rho - 0.06 = -0.04
  // over the half-open window [0, 2) before snapping back. The entire path
  // is known at t = 0 (single belief, one segment).
  path = rho - 0.06 * pulse(t, 0, 2);
end;

simulate(T = 25, N = 600);
