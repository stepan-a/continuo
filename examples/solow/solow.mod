// solow.mod — baseline scenario: convergence from below.
//
// The economy starts well below its steady state — capital is only 30% of its
// long-run value — and the savings rate and productivity are held at their
// reference levels (sav = 0.2, A = 1) throughout. With diminishing returns the
// marginal product of capital is high when K is scarce, so gross saving
// exceeds depreciation and capital climbs, monotonically and ever more slowly,
// to its unique steady state. This is the canonical Solow transition path.

@#include "common.mod"

initval;
  K = 0.3 * steady_state(K);   // start at 30% of the steady-state capital
end;

shocks;
  var sav;
  path = 0.2;          // savings rate held constant
  var A;
  path = 1;            // productivity held constant
end;

simulate(T = 150, N = 300);
