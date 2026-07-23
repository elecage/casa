# orbitlib

Minimal two-body orbital mechanics in canonical units (mu = 1).

- `analytic` — closed-form Kepler solution for bound orbits (the ground
  truth: exact position/velocity at any time)
- `integrate` — numerical propagation (`propagate()` is the public API;
  see its module docstring for the accuracy contract)
- `energy` — conserved quantities: total energy, angular momentum

```python
from orbitlib.analytic import periapsis_state, period
from orbitlib.integrate import propagate

s0 = periapsis_state(a=1.0, e=0.3)
s1 = propagate(s0, dt=period(1.0) / 4000, n_steps=4000)  # one period
```

## Tests

```
python -m pytest
```
