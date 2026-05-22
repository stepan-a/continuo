// solow_savings.mod — a permanent rise in the savings rate, 0.2 -> 0.3.
//
// The economy rests at its old steady state (sav = 0.2) when, at t = 0, the
// savings rate jumps permanently to 0.3. More of each unit of output is now
// invested, so capital accumulates until it reaches a new, higher steady state
// (sav*A/delta)^(1/(1-alpha)). Output rises with it. Crucially the long-run
// *growth rate* is unchanged — it returns to zero — only the *level* of the
// balanced path is higher: the hallmark Solow result that saving lifts levels
// but not the asymptotic growth rate.
//
// Because the higher savings rate is already live at t = 0, the initial state
// cannot be read off the active steady state — it must be anchored at the
// *pre-shock* (sav = 0.2) steady state. The initval(steady, e={...}) override
// does exactly that: fill every state from the steady state evaluated at the
// overridden exogenous (here sav = 0.2) rather than at the active value.

@#include "common.mod"

initval(steady, e={sav: 0.2});   // anchor at the pre-shock (sav = 0.2) SS
end;

shocks;
  var sav;
  path = 0.3;          // permanent rise in the savings rate, effective from t = 0
  var A;
  path = 1;            // productivity held constant
end;

simulate(T = 150, N = 300);
