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
var        R, MC, Y;
varexo     A;             // total-factor productivity

parameters sigma, eta, eps, phi, rho, phipi, lam, h;
sigma = 1;       eta   = 1;       eps   = 6;       phi   = 40;
rho   = 0.02;    phipi = 1.5;
lam   = 0.5;     // habit adjustment speed (exponential averaging rate)
h     = 0.7;     // habit weight in u(C - h X)

model;
  // Resource constraint with Rotemberg adjustment cost as a real resource
  // loss: Y = C + (phi/2)*pi^2 * Y.
  Y = C / (1 - (phi / 2) * pi^2);

  // Real marginal cost with the habit-adjusted labour FOC:
  // w = N^eta / u_C = N^eta * (C - h X)^sigma and N = Y/A.
  MC = Y^eta * (C - h * X)^sigma / A^(eta + 1);

  R = max(0, rho + phipi * pi);

  // habit law of motion: exponential moving average of aggregate consumption
  diff(X)  = lam * (C - X);

  // Euler equation with EXTERNAL habit. Differentiating u_C = (C - hX)^(-sigma)
  // and equating d log(u_C)/dt = rho - R + pi (no preference shifter) gives
  //   d/dt (C - h X) = ((C - h X)/sigma) * (R - pi - rho),
  // whence diff(C) = ((C - h X)/sigma)(R - pi - rho) + h * diff(X).
  diff(C)  = ((C - h * X) / sigma) * (R - pi - rho) + h * lam * (C - X);

  // Rotemberg NKPC, EXACT for sigma = 1: see baseline.mod for the derivation.
  diff(pi) = (1 - (phi / 2) * pi^2) / (1 + (phi / 2) * pi^2)
           * (rho * pi - (eps / phi) * (MC - (eps - 1) / eps));
end;

steady_state_model;
  pi = 0;
  R  = rho;
  MC = (eps - 1) / eps;
  // X* = C* and pi*=0 give Y* = C*. Then MC* = C*^(sigma+eta) * (1-h)^sigma
  // / A^(eta+1); solving for C*:
  C  = (MC * A^(eta + 1) / (1 - h)^sigma)^(1 / (sigma + eta));
  X  = C;
  Y  = C;
end;

initval(steady);
end;

shocks;
  var A;
  // The same productivity boom as the baseline: A rises to 1.12 over [0, 3).
  path = 1 + 0.12 * pulse(t, 0, 3);
end;

simulate(T = 25, N = 600);
