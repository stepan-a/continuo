// ---------------------------------------------------------------------------
// common.mod — shared core of the continuous-time Dornbusch examples.
//
// This file is not run on its own. Each scenario file pulls it in with
//
//     @#include "common.mod"
//
// and then adds its own initval, shocks and simulate blocks. Keeping the
// declarations, the model and the analytical steady state here means the
// scenarios differ only in how the money supply is shocked and where the
// economy starts — see the sibling dornbusch*.mod files and README.md.
//
// The economy: Dornbusch's (1976) exchange-rate overshooting model under
// perfect foresight. A small open economy with a sluggish (sticky) price
// level and a freely floating exchange rate. There are two endogenous
// dynamic variables,
//
//   p  the (log) domestic price level — a sticky, predetermined STATE
//   s  the (log) nominal exchange rate — a forward-looking JUMP
//
// the domestic interest rate i as a static (algebraic) function of the state,
// and a single exogenous driver, the (log) money supply
//
//   m  the money supply
//
// Three relations close the model:
//
//   * Money market (LM): real balances equal money demand, decreasing in the
//     interest rate and increasing in (constant) output ybar,
//
//         m - p = phi * ybar - lambda * i   =>   i = (phi*ybar - m + p)/lambda.
//
//   * Uncovered interest parity (UIP) under perfect foresight: the home–foreign
//     interest differential equals the expected (= actual) depreciation,
//
//         diff(s) = i - istar.
//
//   * Sticky prices: the price level crawls toward demand, which rises with
//     competitiveness s - p (a real depreciation raises demand for home goods),
//
//         diff(p) = psi * gamma * (s - p).
//
// The Jacobian of (p, s) has eigenvalues of opposite sign — a SADDLE. With p
// predetermined (it cannot jump) and s free to jump, the stable manifold pins
// a unique perfect-foresight path. A monetary expansion drives the exchange
// rate to OVERSHOOT its new long-run level on impact, then converge back as
// prices slowly rise — Dornbusch's central result.
// ---------------------------------------------------------------------------

var(state) p;        // the (log) price level — sticky, predetermined
var(jump)  s;        // the (log) exchange rate — forward-looking (jumps)
var        i;        // the domestic interest rate — static (algebraic)
varexo     m;        // the (log) money supply

parameters lambda, gamma, psi, ybar, istar, phi;
lambda = 0.5;        // interest semi-elasticity of money demand
gamma  = 0.4;        // sensitivity of goods demand to competitiveness
psi    = 1.0;        // speed of price adjustment
ybar   = 1;          // (constant) full-employment output
istar  = 0.05;       // foreign (world) interest rate
phi    = 0.5;        // income elasticity of money demand

model;
  // money market (LM): real balances = money demand  =>  interest rate
  i = (phi * ybar - m + p) / lambda;

  // sticky prices: crawl toward demand, driven by competitiveness s - p
  diff(p) = psi * gamma * (s - p);

  // uncovered interest parity under perfect foresight
  diff(s) = i - istar;
end;

// Analytical steady state as a function of the parameters and m.
steady_state_model;
  p = m + lambda * istar - phi * ybar;   // diff(p)=0 and i=istar  =>  s=p
  s = m + lambda * istar - phi * ybar;   // diff(s)=0  =>  i=istar
  i = istar;                             // UIP at rest
end;
