// external_habit.mod — nonlinear NK with EXTERNAL additive habit.
//
// The representative household values consumption relative to an aggregate
// habit stock X that follows a backward-looking moving average of past
// aggregate consumption (catching-up-with-the-Joneses). Because habit is
// external the household treats it as given, so the Euler equation is the
// no-habit one applied to (C - h X) rather than to C. The habit stock is
// a new STATE variable; consumption remains a forward-looking JUMP.
//
// See README.md for the derivation.

var(state) X;             // habit stock — predetermined
var(jump)  C, pi;         // forward-looking
var        R, MC;
varexo     rnat;

parameters sigma, eta, eps, phi, rho, phipi, lam, h;
sigma = 1;       eta   = 1;       eps   = 6;       phi   = 40;
rho   = 0.02;    phipi = 1.5;
lam   = 0.5;     // habit adjustment speed (exponential averaging rate)
h     = 0.7;     // habit weight in u(C - h X)

model;
  // real marginal cost: w/A with the habit-adjusted labour FOC
  // w = N^eta * (C - h X)^sigma, A = 1, N = C
  MC = C^eta * (C - h * X)^sigma;

  R = max(0, rho + phipi * pi);

  // habit law of motion: exponential moving average of aggregate consumption
  diff(X)  = lam * (C - X);

  // Euler equation with EXTERNAL habit. Differentiating u_C = (C - hX)^(-sigma)
  // and equating d log(u_C)/dt = rnat - R + pi gives
  //   d/dt (C - h X) = ((C - h X)/sigma) * (R - pi - rnat),
  // whence diff(C) = ((C - h X)/sigma)(R - pi - rnat) + h * diff(X).
  diff(C)  = ((C - h * X) / sigma) * (R - pi - rnat) + h * lam * (C - X);

  // Rotemberg NKPC
  diff(pi) = rho * pi - (eps / phi) * (MC - (eps - 1) / eps);
end;

steady_state_model;
  pi = 0;
  R  = rho;
  // X* = C* in steady state (the moving average has converged), so
  // MC* = C*^eta * ((1 - h) C*)^sigma = C*^(sigma+eta) (1 - h)^sigma;
  // setting MC* = (eps - 1)/eps gives:
  C  = ((eps - 1) / (eps * (1 - h)^sigma))^(1 / (sigma + eta));
  X  = C;
  MC = (eps - 1) / eps;
end;

initval(steady);
end;

shocks;
  var rnat;
  path = rho - 0.06 * pulse(t, 0, 2);
end;

simulate(T = 25, N = 600);
