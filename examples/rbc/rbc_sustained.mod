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
// (e = 0) steady state. The initval(steady, e={...}) override does exactly
// that: fill every state from the steady state evaluated at the overridden
// exogenous (here e = 0) rather than at the active value (e = 0.05).

@#include "common.mod"

initval(steady, e={e: 0});   // anchor all states at the pre-shock (e = 0) SS
end;

shocks;
  var e;
  path = 0.05;          // permanent innovation, known and effective from t = 0
end;

simulate(T = 50, N = 250);
