// ---------------------------------------------------------------------------
// common.mod — shared core of the Goodwin growth-cycle examples.
//
// This file is not run on its own. Each scenario file pulls it in with
//
//     @#include "common.mod"
//
// and then adds only its own initval and simulate blocks — the scenarios
// differ solely in the initial condition (the amplitude of the cycle), since
// the model is autonomous (no exogenous driver, no shocks).
//
// The economy: Goodwin's (1967) growth cycle, a Lotka–Volterra ("predator–
// prey") system in two predetermined STATE variables,
//
//   v  the employment rate     (prey)
//   u  the wage share of output (predator)
//
// Behind them: output is Leontief in capital (capital–output ratio sigma);
// labour productivity grows at alpha and the labour force at beta; a real-wage
// Phillips curve dw/w = -gamma + rho*v makes wages rise faster when employment
// is high; and all profits are invested. Eliminating the levels leaves the two
// laws of motion below.
//
//   diff(v) = v * [ (1 - u)/sigma - (alpha + beta) ]
//   diff(u) = u * [ rho*v - (gamma + alpha) ]
//
// Unlike the optimising models in this gallery, NEITHER variable is forward-
// looking: both are physical/historical quantities pinned by initial
// conditions. There are no jumps, hence no terminal boundary condition — the
// solver integrates forward as a pure initial-value problem. The interior
// fixed point below is a *centre* (closed orbits, neutrally stable), so the
// economy neither converges to it nor diverges: it cycles. The steady_state_
// model here is used only to seed the solver's initial guess, not as a
// boundary condition.
// ---------------------------------------------------------------------------

var(state) v, u;     // employment rate (prey), wage share (predator)

parameters sigma, alpha, beta, gamma, rho;
sigma = 3;           // capital–output ratio
alpha = 0.06;        // labour-productivity growth
beta  = 0.04;        // labour-force growth
gamma = 0.3;         // real-wage Phillips-curve intercept
rho   = 0.5;         // real-wage Phillips-curve slope

model;
  // employment rises when the profit-financed growth rate exceeds the
  // productivity + labour-force growth that the employment rate must "outrun"
  diff(v) = v * ((1 - u) / sigma - (alpha + beta));

  // the wage share rises when employment is high enough that real wages
  // grow faster than productivity
  diff(u) = u * (rho * v - (gamma + alpha));
end;

// Interior fixed point (the centre of the orbits). Used only to seed the
// solver's guess — the trajectory cycles around it, it is not an attractor.
steady_state_model;
  v = (gamma + alpha) / rho;       // v* = 0.72
  u = 1 - sigma * (alpha + beta);  // u* = 0.70
end;
