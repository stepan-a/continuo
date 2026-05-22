// dornbusch.mod — baseline scenario: an unanticipated permanent monetary
// expansion, in effect from the very first instant.
//
// The money supply jumps from m = 0 to m = 0.1 at t = 0 and stays there. The
// economy was resting at the old (m = 0) steady state, so the predetermined,
// sticky price level p starts there and crawls up to the new steady state;
// the exchange rate s, free to jump, reacts on impact.
//
// Because the change is already live at t = 0, the initial state cannot be read
// off the active steady state — it must be anchored at the *pre-shock* (m = 0)
// steady state. The initval(steady, e={...}) override does exactly that: fill
// every state from the steady state evaluated at the overridden exogenous
// (here m = 0) rather than at the active value (m = 0.1).
//
// This delivers Dornbusch's OVERSHOOTING: money up lowers the interest rate, so
// by UIP the exchange rate must be *appreciating* along the path; to do so from
// a higher level it jumps on impact ABOVE its new long-run value, then converges
// down as the sticky price rises. Check that s(0) exceeds s(end).

@#include "common.mod"

initval(steady, e={m: 0});   // anchor the price level at the pre-shock (m=0) SS
end;

shocks;
  var m;
  path = 0.1;          // permanent expansion, unanticipated but live from t = 0
end;

simulate(T = 30, N = 300);
