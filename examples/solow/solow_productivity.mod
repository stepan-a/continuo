// solow_productivity.mod — a permanent rise in productivity, A 1 -> 1.3.
//
// The economy rests at its old steady state (A = 1) when, at t = 0, total
// factor productivity jumps permanently to 1.3. Higher productivity raises
// output immediately at the inherited capital stock, and the extra saving it
// generates pushes capital up to a new, higher steady state as well. Both
// capital and output settle at higher levels — productivity scales the whole
// balanced path, raising K* by the factor A^(1/(1-alpha)) and Y* by even more.
//
// As in the savings-rate experiment the change is already live at t = 0, so
// the initial state is anchored at the *pre-shock* (A = 1) steady state with
// the initval(steady, e={...}) override.

@#include "common.mod"

initval(steady, e={A: 1});   // anchor at the pre-shock (A = 1) SS
end;

shocks;
  var A;
  path = 1.3;          // permanent rise in productivity, effective from t = 0
  var sav;
  path = 0.2;          // savings rate held constant
end;

simulate(T = 150, N = 300);
