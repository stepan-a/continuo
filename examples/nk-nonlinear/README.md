# Continuous-time New Keynesian models (nonlinear)

This folder builds the **fully nonlinear** continuous-time New Keynesian model
in three flavours, all driven by the same exogenous "natural-rate" shock that
sends the economy into a temporary liquidity trap:

- [`baseline.mod`](baseline.mod) — no habits (the textbook nonlinear NK).
- [`external_habit.mod`](external_habit.mod) — additive habits taken as given
  by the household (catching-up-with-the-Joneses).
- [`internal_habit.mod`](internal_habit.mod) — the same habits **internalised**
  by the household: today's consumption is recognised as raising tomorrow's
  habit stock, so a habit costate enters the optimisation.

The companion folder `examples/nk/` carries the log-linearised version of the
same trap; here the equations are kept in levels, with the policy rate `R =
max(0, ρ + φπ·π)` introducing the ZLB kink directly.

Unlike the other example folders, the three model files here do **not** share
a `common.mod`: the variable sets and the equation systems differ
structurally (internal habit adds a costate; external doesn't), so a literal
`@#include` would not save much and would obscure the comparison. Each `.mod`
is self-contained and readable on its own.

## What's common to all three

### Households (basics)

A representative household has separable preferences over consumption and
labour,

```math
U = \int_0^\infty e^{-\rho t} [u(C(t),X(t)) - \frac{N(t)^{1+\eta}}{1+\eta}] dt,
```

with intertemporal discount rate $`\rho > 0`$ and inverse Frisch elasticity
$`\eta`$. The felicity $`u(\cdot)`$ depends on a habit stock $`X`$ that we will
specialise below (or set $`h = 0`$ to eliminate habits altogether). The
budget constraint, expressed in real terms with one-period real bonds $`B`$,
is

```math
\dot B(t) = (R(t) - \pi(t)) B(t) + w(t) N(t) - C(t),
```

where $`R`$ is the nominal policy rate, $`\pi`$ is inflation, and $`w`$ is the
real wage.

### Firms (Rotemberg)

A continuum of monopolistically competitive intermediate firms produce with
the linear technology $`y_i = A n_i`$ (so aggregate $`Y = A N`$), facing
quadratic price-adjustment costs at rate $`\phi/2`$ on $`\pi^2`$. Aggregating
their first-order condition under symmetric equilibrium yields the
continuous-time New Keynesian Phillips Curve:

```math
\dot\pi = \rho \pi - \frac{\varepsilon}{\phi} (MC - \frac{\varepsilon-1}{\varepsilon}),
```

where $`MC`$ is the real marginal cost (derived below from the labour FOC),
and $`(\varepsilon - 1)/\varepsilon`$ is the flexible-price markup target. We
normalise $`A = 1`$ throughout.

### Monetary policy

A Taylor-type rule responding to inflation, **clamped** at the zero lower
bound:

```math
R(t) = \max(0,\ \rho + \phi_\pi \pi(t)).
```

The intercept is $`\rho`$ so that the no-shock steady state has $`R^* = \rho`$,
$`\pi^* = 0`$. The `max(0, …)` is what makes the model genuinely nonlinear.

### The natural-rate shock

In continuous time the cleanest device for a "demand shock" is a
preference shifter multiplying the household's felicity, $`\xi(t) u(C,X)`$;
its derivative shifts the household's effective discount rate. We expose
the device directly through an exogenous **natural rate** $`r^{nat}(t)`$ that
replaces $`\rho`$ inside the wealth Euler equation. In the no-shock steady
state $`r^{nat} = \rho`$. The experiment below drops $`r^{nat}`$ to $`-0.04`$ over the
half-open window $`[0, 2)`$ — well below zero — to trigger the trap.

### Calibration (all three models)

| symbol | value | interpretation |
|---|---|---|
| σ | 1 | inverse IES (log utility) |
| η | 1 | inverse Frisch elasticity |
| ε | 6 | elasticity of substitution between varieties (20% markup) |
| φ | 40 | Rotemberg price-adjustment cost |
| ρ | 0.02 | rate of time preference (= long-run natural rate) |
| φ_π | 1.5 | Taylor-rule inflation response |
| λ | 0.5 | habit adjustment speed (habit variants only) |
| h | 0.7 | habit weight (habit variants only) |

## Baseline: nonlinear NK without habit

[`baseline.mod`](baseline.mod). With $`u(C) = C^{1-\sigma}/(1-\sigma)`$ and
$`X`$ absent ($`h = 0`$), the consumption Euler in continuous time is

```math
\dot C = \frac{C}{\sigma} (R - \pi - r^{nat}).
```

The labour FOC reads $`w = N^\eta / u_C = N^\eta C^\sigma`$, and with $`Y = C`$
(market clearing) and $`A = 1`$, real marginal cost simplifies to

```math
MC = w/A = C^\eta \cdot C^\sigma = C^{\sigma + \eta}.
```

The full system is:

**State.** None.

**Jumps.**

```math
\dot C = (C/\sigma)(R - \pi - r^{nat})
```

```math
\dot\pi = \rho\pi - (\varepsilon/\phi)(MC - (\varepsilon-1)/\varepsilon)
```

**Algebraic.**

```math
MC = C^{\sigma+\eta}
```

```math
R = \max(0, \rho + \phi_\pi\pi)
```

**Steady state** ($`r^{nat} = \rho`$): $`\pi^* = 0`$, $`R^* = \rho`$,
$`MC^* = (\varepsilon-1)/\varepsilon`$, $`C^* = (MC^*)^{1/(\sigma+\eta)}`$.

## External habit

[`external_habit.mod`](external_habit.mod). Now the felicity is

```math
u(C, X) = \frac{(C - h X)^{1-\sigma}}{1-\sigma},
```

with `0 ≤ h < 1` and a habit stock $`X`$ that evolves as a backward-looking
moving average of consumption,

```math
\dot X = \lambda (C - X),    \lambda > 0.
```

**External** means the household treats $`X`$ as a given (aggregate) state —
it does not internalise that $`C`$ raises future $`X`$. Marginal utility is
$`u_C = (C - hX)^{-\sigma}`$, and the continuous-time Euler reads
$`d(\log u_C)/dt = r^{nat} - R + \pi`$. Differentiating,

```math
-\sigma \frac{\dot C - h \dot X}{C - hX} = r^{nat} - R + \pi
```

which rearranges to

```math
\dot C - h \dot X = \frac{C - hX}{\sigma} (R - \pi - r^{nat}),
```

and substituting $`\dot X = \lambda(C - X)`$ gives the **habit-augmented
consumption Euler**,

```math
\dot C = \frac{C - hX}{\sigma} (R - \pi - r^{nat}) + h \lambda (C - X).
```

The habit-modified labour FOC is $`w = N^\eta / u_C = N^\eta (C-hX)^\sigma`$,
which (with $`N = C`$, $`A = 1`$) gives

```math
MC = w/A = C^\eta (C - hX)^\sigma.
```

The full system is:

**State.**

```math
\dot X = \lambda(C - X)
```

**Jumps.**

```math
\dot C = \frac{C-hX}{\sigma}(R-\pi-r^{nat}) + h\lambda(C-X)
```

```math
\dot\pi = \rho\pi - (\varepsilon/\phi)(MC-(\varepsilon-1)/\varepsilon)
```

**Algebraic.**

```math
MC = C^\eta(C-hX)^\sigma
```

```math
R = \max(0, \rho + \phi_\pi\pi)
```

**Steady state**: $`\dot X = 0 \Rightarrow X^* = C^*`$, so $`C - hX = (1-h)C`$
in SS, hence
$`MC^* = C^{* \eta} \cdot ((1-h)C^*)^\sigma = (1-h)^\sigma C^{* \sigma+\eta}`$.
Setting $`MC^* = (\varepsilon-1)/\varepsilon`$:

```math
C^* = (\frac{\varepsilon-1}{\varepsilon (1-h)^\sigma})^{1/(\sigma+\eta)}.
```

When $`h = 0`$ this collapses to the baseline.

## Internal habit

[`internal_habit.mod`](internal_habit.mod). Same felicity
$`u(C, X) = (C - hX)^{1-\sigma}/(1-\sigma)`$, same habit law
$`\dot X = \lambda(C - X)`$, but the household now **internalises** the
effect of $`C`$ on $`X`$. The current-value Hamiltonian carries a costate
$`\mu`$ on the habit stock:

```math
H = u(C, X) - \frac{N^{1+\eta}}{1+\eta} + \lambda_B[(R-\pi)B + wN - C] + \mu \lambda (C - X),
```

where $`\lambda_B`$ is the costate of wealth.

**First-order conditions.**

- $`\partial H/\partial C = 0 \Rightarrow u_C - \lambda_B + \lambda\mu = 0`$, so

```math
\lambda_B = (C - hX)^{-\sigma} + \lambda \mu
```

(the consumption FOC).

- $`\partial H/\partial N = 0 \Rightarrow -N^\eta + \lambda_B w = 0`$, so $`w = N^\eta/\lambda_B`$. With $`Y = C = AN`$ and $`A = 1`$,

```math
MC = w / A = C^\eta / \lambda_B.
```

**Costate equations** (current-value Hamiltonian, $`\rho`$ the
discount rate; the natural-rate shock enters the wealth Euler only):

- Wealth:
  $`\dot\lambda_B = \rho\lambda_B - \partial H/\partial B = \lambda_B (\rho - R + \pi)`$.
  With the natural-rate device:

```math
\dot\lambda_B = \lambda_B (r^{nat} - R + \pi).
```

- Habit: $`\dot\mu = \rho\mu - \partial H/\partial X`$, with
  $`\partial H/\partial X = u_X - \mu\lambda`$ and $`u_X = -h (C-hX)^{-\sigma}`$:

```math
\dot\mu = (\rho + \lambda) \mu + h (C - hX)^{-\sigma}.
```

**The role of `C` in the system.** The consumption FOC is an *algebraic*
relation between $`\lambda_B`$, $`C`$, $`X`$, $`\mu`$. Solved for $`C`$ (the unknown
not constrained by any time derivative),

```math
C = h X + (\lambda_B - \lambda\mu)^{-1/\sigma}.
```

So $`C`$ is **algebraic** — pinned at every grid point by the FOC given the
state $`X`$ and the two costates $`\lambda_B`$, $`\mu`$ — while $`\pi`$,
$`\lambda_B`$ and $`\mu`$ are the three forward-looking **jumps** of the
system.

The full system is

**State.**

```math
\dot X = \lambda(C - X)
```

**Jumps.**

```math
\dot\lambda_B = \lambda_B (r^{nat} - R + \pi)
```

```math
\dot\mu = (\rho + \lambda) \mu + h (C - hX)^{-\sigma}
```

```math
\dot\pi = \rho\pi - (\varepsilon/\phi)(MC - (\varepsilon-1)/\varepsilon)
```

**Algebraic.**

```math
C = hX + (\lambda_B - \lambda\mu)^{-1/\sigma}
```

```math
MC = C^\eta / \lambda_B
```

```math
R = \max(0, \rho + \phi_\pi\pi)
```

**Steady state.** $`\dot\pi = 0`$ and $`\dot\lambda_B = 0`$ give $`\pi^* = 0`$ and
$`R^* = r^{nat} = \rho`$. From $`\dot\mu = 0`$:

```math
\mu^* = - \frac{h (C^* - h X^*)^{-\sigma}}{\rho + \lambda}.
```

With $`X^* = C^*`$ (from $`\dot X = 0`$) so $`C^* - hX^* = (1-h)C^*`$:

```math
\mu^* = - \frac{h ((1-h)C^*)^{-\sigma}}{\rho + \lambda} \;<\;0.
```

The consumption FOC then gives

```math
\lambda_B^* = ((1-h)C^*)^{-\sigma} \frac{\rho + \lambda - \lambda h}{\rho + \lambda},
```

and $`MC^* = (\varepsilon-1)/\varepsilon`$ combined with $`MC = C^\eta/\lambda_B`$ yields

```math
C^* = (\frac{\varepsilon-1}{\varepsilon (1-h)^\sigma}\cdot\frac{\rho + \lambda - \lambda h}{\rho + \lambda})^{1/(\sigma+\eta)}.
```

When $`h = 0`$ this again collapses to the baseline. Compared with external
habit, internal habit pins $`C^*`$ *closer* to the no-habit level — the extra
$`(\rho+\lambda-\lambda h)/(\rho+\lambda) < 1`$ factor partly offsets the
$`(1-h)^{-\sigma}`$ inflation of $`C^*`$ that external habit produces.

## The experiment

All three scenarios share the same liquidity-trap shock,

```
shocks;
  var rnat;
  path = rho - 0.06 * pulse(t, 0, 2);   // rnat = -0.04 on [0, 2), then rho
end;
```

revealed at $`t = 0`$ (single belief, one segment). All three start at their
respective steady states (`initval(steady)` — vacuous for the baseline since
it has no state). Each is solved on a uniform Crank–Nicolson grid with
`simulate(T = 25, N = 600)`.

## Simulation results

The three scenarios overlaid (generated by `run_nk_nonlinear.py`):

![Baseline, external-habit and internal-habit nonlinear NK under the same liquidity-trap shock](nk-nonlinear.png)

Numerical headlines:

| scenario | C-gap on impact | π trough | R minimum | time spent at ZLB |
|---|---:|---:|---:|---:|
| baseline (no habit) | **−11.0 %** | −2.66 % | 0 | 2.5 % of horizon |
| external habit (h = 0.7) | −3.1 % | −1.94 % | 0 | 1.8 % of horizon |
| internal habit (h = 0.7) | **−1.4 %** | −1.63 % | 0 | 1.0 % of horizon |

**Habits dampen the impact response and stretch the tail.** Without
habits, consumption drops 11% on impact and is essentially back at steady
state by $`t = 2`$. With either form of habit the impact response is much
smaller (factor 3.5–8×), but the recovery has a visible tail past $`t = 5`$.
Internal habit produces the smallest impact: by *internalising* that
today's $`C`$ raises tomorrow's $`X`$, the household values smoothing not just
across time but along the habit stock as well, and is even less willing to
let consumption fall.

**The ZLB still binds in all three cases**, but only briefly. With habit
the deflation is milder, so the Taylor-rule rate is dragged below zero only
for a short window around $`t = 1`$.

### A note on the shape of the response

Discrete-time NK textbooks with habits typically show a **hump-shaped**
consumption IRF — the trough lands a few periods *after* impact. In this
continuous-time perfect-foresight setting the trough sits exactly at $`t = 0`$
in all three runs: there is no Calvo-style expectational delay to push it
back, and the entire path is known to agents at the reveal time, so a
forward-looking variable jumps directly to its optimal continuation. Habit
still produces *persistence* — a longer tail — but not a hump. Recovering
the hump shape would require an additional friction (e.g. an adjustment
cost on $`\dot C`$ itself), discrete-time information frictions, or a
stochastic environment in which agents update beliefs along the path.

## Running

With continuo installed (`pip install -e .` from the repository root):

```console
$ continuo examples/nk-nonlinear/baseline.mod
continuo: wrote 601 rows to examples/nk-nonlinear/baseline.csv

$ python examples/nk-nonlinear/run_nk_nonlinear.py     # overlays all three, writes nk-nonlinear.png
```

The CSV columns are `t, C, pi, R, MC` for the baseline; the habit variants
add `X` and (for internal habit) `mu, lambda_B`.

```python
import continuo

model = continuo.parse("examples/nk-nonlinear/internal_habit.mod")
sol = model.simul()
ss  = model.steady_state(exogenous={"rnat": 0.02})
print(sol["C"][0] / ss["C"] - 1)   # consumption gap on impact
```

## References

- Werning, I. (2011), "Managing a Liquidity Trap: Monetary and Fiscal
  Policy," NBER Working Paper 17344 — continuous-time NK and the
  liquidity-trap experiment that motivates the calibration here.
- Rotemberg, J.J. (1982), "Sticky Prices in the United States," *Journal of
  Political Economy* 90(6):1187–1211 — the quadratic price-adjustment-cost
  foundation of the NKPC.
- Cochrane, J.H. (2017), "The New-Keynesian Liquidity Trap," *Journal of
  Monetary Economics* 92:47–63 — nonlinear NK and the ZLB.
- Galí, J. (2015), *Monetary Policy, Inflation, and the Business Cycle*,
  Princeton University Press — textbook treatment (discrete time, but the
  derivations carry over directly).
- Abel, A.B. (1990), "Asset Prices under Habit Formation and Catching Up
  with the Joneses," *American Economic Review Papers and Proceedings*
  80(2):38–42 — external (catching-up) habit.
- Constantinides, G.M. (1990), "Habit Formation: A Resolution of the
  Equity Premium Puzzle," *Journal of Political Economy* 98(3):519–543 —
  internal habit.
- Christiano, L.J., Eichenbaum, M., and Evans, C.L. (2005), "Nominal
  Rigidities and the Dynamic Effects of a Shock to Monetary Policy,"
  *Journal of Political Economy* 113(1):1–45 — habits as a source of
  output persistence in the medium-scale DSGE tradition (discrete-time).
