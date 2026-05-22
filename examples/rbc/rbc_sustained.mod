// rbc_sustained.mod — a permanent productivity innovation, in effect from
// the very first instant.
//
// e jumps to 0.05 at t = 0 and stays there, so productivity settles at a new,
// higher mean 1 + e/theta = 1.1. The economy was resting at the old (e = 0)
// steady state, so the predetermined states start there and transition to the
// new one; consumption jumps up on impact.
//
// Because the innovation is already live at t = 0, the initial state cannot be
// read off the active steady state — it must be anchored at the *pre-shock*
// (e = 0) steady state. We write that anchor explicitly below. (The
// initval(steady, e={...}) override documented for this case is not yet
// honoured by the solver — see ../README.md.)

@#include "common.mod"

initval;
  K = (alpha * 1 / (rho + delta))^(1 / (1 - alpha));  // e = 0 SS (A = 1)
  A = 1;                                              // productivity at its mean
end;

shocks;
  var e;
  path = 0.05;          // permanent innovation, known and effective from t = 0
end;

simulate(T = 50, N = 250);
