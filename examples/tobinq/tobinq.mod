// tobinq.mod — baseline scenario: an unanticipated permanent rise in
// profitability, in effect from the very first instant.
//
// A jumps from 1 to 1.5 at t = 0 and stays there. The firm was resting at the
// old (A = 1) steady state, so the predetermined capital stock starts there and
// transitions to the new, higher one; Tobin's q jumps up on impact and the firm
// invests heavily to build the capital stock toward its richer steady state.
//
// Because the higher profitability is already live at t = 0, the initial state
// cannot be read off the active steady state — it must be anchored at the
// *pre-shock* (A = 1) steady state. The initval(steady, e={...}) override does
// exactly that: fill every state from the steady state evaluated at the
// overridden exogenous (here A = 1) rather than at the active value (A = 1.5).

@#include "common.mod"

initval(steady, e={A: 1});   // anchor capital at the old (A = 1) steady state
end;

shocks;
  var A;
  path = 1.5;          // permanent rise, known and effective from t = 0
end;

simulate(T = 50, N = 300);
