// baseline.mod — fully nonlinear continuous-time New Keynesian model
// (Rotemberg price adjustment, no habit). Two forward-looking variables
// (consumption C and inflation pi) and an algebraic policy rate R subject
// to the zero lower bound. The exogenous total-factor productivity A rises
// temporarily and drives marginal cost down; the resulting deflation hits
// the ZLB and triggers the liquidity trap.
//
// See README.md for the full derivation and references.
//
// In this folder each scenario is a self-contained file rather than an
// @#include of a shared common.mod — the three models differ structurally
// (number of state variables, sets of FOCs) so factoring is awkward.

var(jump) C, pi;
var       R, MC, Y;
varexo    A;

parameters sigma, eta, eps, phi, rho, phipi;
sigma = 1;       // inverse intertemporal elasticity (log utility for sigma=1)
eta   = 1;       // inverse Frisch elasticity of labour supply
eps   = 6;       // elasticity of substitution between varieties (20% markup)
phi   = 40;      // Rotemberg price-adjustment cost
rho   = 0.02;    // rate of time preference (= steady-state real rate)
phipi = 1.5;     // Taylor-rule inflation feedback

model;
  // Resource constraint with Rotemberg adjustment cost as a real resource
  // loss: Y = C + (phi/2)*pi^2 * Y, equivalently Y = C / (1 - (phi/2)*pi^2).
  Y = C / (1 - (phi / 2) * pi^2);

  // Real marginal cost: MC = w/A with w = N^eta / u_C and N = Y/A.
  // For log utility u_C = 1/C, so MC = Y^eta * C^sigma / A^(eta+1). At A=1
  // and pi=0 this reduces to the canonical MC = C^(sigma+eta).
  MC = Y^eta * C^sigma / A^(eta + 1);

  // Taylor rule with zero lower bound on the policy rate
  R = max(0, rho + phipi * pi);

  // Continuous-time consumption Euler (standard, no preference shifter, so
  // the rate of time preference is exactly rho throughout):
  diff(C)  = (C / sigma) * (R - pi - rho);

  // Rotemberg New Keynesian Phillips Curve (continuous time, EXACT, sigma=1).
  // Using the resource constraint exactly to differentiate ν = Λ φ π Y, the
  // log-utility cancellation leaves a correction factor (1 - (phi/2)*pi^2)
  // / (1 + (phi/2)*pi^2) multiplying the canonical right-hand side. At
  // pi = 0 the factor is 1 (so the steady state is unchanged); during the
  // deepest trap it is about 0.97 and damps the NKPC by ~3%.
  diff(pi) = (1 - (phi / 2) * pi^2) / (1 + (phi / 2) * pi^2)
           * (rho * pi - (eps / phi) * (MC - (eps - 1) / eps));
end;

steady_state_model;
  pi = 0;                              // zero-inflation steady state
  R  = rho;
  MC = (eps - 1) / eps;                // flex-price markup target
  // MC = C^(sigma+eta) / A^(eta+1) at Y = C, so C = (MC * A^(eta+1))^(1/(sigma+eta)).
  C  = (MC * A^(eta + 1))^(1 / (sigma + eta));
  Y  = C;
end;

shocks;
  var A;
  // Baseline A is 1; the productivity boom raises A to 1.12 over [0, 3)
  // before returning. The boom lowers marginal cost, drives deflation,
  // hits the ZLB and triggers the trap. The entire path is known at t = 0.
  path = 1 + 0.12 * pulse(t, 0, 3);
end;

simulate(T = 25, N = 600);
