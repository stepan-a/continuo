// internal_habit.mod — nonlinear NK with INTERNAL additive habit.
//
// The representative household now *internalises* the effect of current
// consumption on the future habit stock: today's C raises tomorrow's X
// via diff(X) = lam*(C - X), which lowers tomorrow's marginal utility.
// The household's optimisation therefore carries a costate mu on the habit
// stock, and the consumption FOC becomes
//     lambda_B = (C - h X)^(-sigma) + lam * mu,
// where lambda_B is the costate of wealth. C is no longer a jump — it is
// pinned algebraically by this FOC given X, lambda_B and mu. The forward-
// looking variables are pi, lambda_B and mu (three jumps); X is the single
// predetermined state.
//
// See README.md for the derivation.

var(state) X;                 // habit stock — predetermined
var(jump)  pi, lambda_B, mu;  // inflation + wealth costate + habit costate
var        R, MC, C;          // algebraic
varexo     rnat;

parameters sigma, eta, eps, phi, rho, phipi, lam, h;
sigma = 1;       eta   = 1;       eps   = 6;       phi   = 40;
rho   = 0.02;    phipi = 1.5;
lam   = 0.5;     // habit adjustment speed
h     = 0.7;     // habit weight

model;
  // FOC for C: lambda_B = u_C + lam*mu  with  u_C = (C - h*X)^(-sigma).
  // Solved for C so the LHS variable is the genuinely algebraic one.
  C = h * X + (lambda_B - lam * mu)^(-1 / sigma);

  // labour FOC + production: w = N^eta / lambda_B, A = 1, MC = w/A = C^eta / lambda_B
  MC = C^eta / lambda_B;

  R = max(0, rho + phipi * pi);

  // habit law of motion
  diff(X)        = lam * (C - X);

  // wealth costate (the marginal-utility-of-wealth Euler) with the natural-rate
  // preference-shock device: rnat replaces rho here only
  diff(lambda_B) = lambda_B * (rnat - R + pi);

  // habit costate: with u_X = -h * u_C the costate equation is
  //   mu^dot = (rho + lam) * mu - u_X = (rho + lam) * mu + h * u_C
  diff(mu)       = (rho + lam) * mu + h * (C - h * X)^(-sigma);

  // Rotemberg NKPC
  diff(pi)       = rho * pi - (eps / phi) * (MC - (eps - 1) / eps);
end;

steady_state_model;
  pi = 0;
  R  = rho;
  // SS: X* = C*, mu_ss = -h u_C / (rho + lam) so lambda_B_ss
  // = u_C (1 - lam h/(rho + lam)) = u_C (rho + lam - lam h)/(rho + lam).
  // Combined with MC* = (eps - 1)/eps and MC = C^eta / lambda_B:
  C        = ((eps - 1) / (eps * (1 - h)^sigma) * (rho + lam - lam * h) / (rho + lam))^(1 / (sigma + eta));
  X        = C;
  mu       = -h * ((1 - h) * C)^(-sigma) / (rho + lam);
  lambda_B = ((1 - h) * C)^(-sigma) + lam * mu;
  MC       = (eps - 1) / eps;
end;

initval(steady);
end;

shocks;
  var rnat;
  path = rho - 0.06 * pulse(t, 0, 2);
end;

simulate(T = 25, N = 600);
