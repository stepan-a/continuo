// rbc_transitory.mod — a transitory productivity boom delivered through the
// *innovation path*, fully anticipated.
//
// e is switched on to 0.05 over the window [5, 15) and off otherwise, using
// the `pulse` shock helper. The whole path is known at t = 0 (a single belief,
// one segment), so consumption jumps immediately in anticipation of the coming
// boom. Productivity climbs toward 1 + e/theta = 1.1 while the innovation is
// on, then mean-reverts back to 1.
//
// Contrast this with rbc.mod, which produces a transitory disturbance through
// the initial condition rather than the forcing term.

@#include "common.mod"

initval(steady);        // e = 0 at t = 0, so this anchors at the e = 0 SS
end;

shocks;
  var e;
  path = 0.05 * pulse(t, 5, 15);   // a boom over [5, 15), known from t=0
end;

simulate(T = 50, N = 250);
