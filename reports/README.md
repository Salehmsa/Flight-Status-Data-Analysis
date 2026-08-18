# reports/

**The dashboard moved.** It now lives at [`../docs/index.html`](../docs/index.html)
and is served live at:

**https://salehmsa.github.io/Flight-Status-Data-Analysis/**

## Why it moved

GitHub Pages serves from `/docs`. Keeping a second copy in `reports/` would mean
the live site and the committed artefact could drift apart — which is the exact
class of defect this project was corrected for. One file, one location.

## Regenerating it

```bash
python scripts/build_dashboard.py --data data/raw
```

The script recomputes every aggregate from `scripts/flight_rules.py`, asserts the
result against the published baselines, and **writes nothing if an assertion
fails**. It patches `docs/index.html` in place.

## The red banner

If the dashboard shows a red bar across the top, its data was not produced by
`build_dashboard.py`, or came from a run whose assertions failed. The banner
names the specific problem and disappears on a clean regeneration.

It exists because of what happened to the previous version: it was generated
with `> 15` where the model uses `>= 15`, and published 14,206 flights in the
wrong status. Nothing about the page looked wrong. A dashboard that has drifted
from its model should say so on its own face.

## Do not hand-edit the numbers

Correcting a figure by hand creates a second copy of the truth, which is the
problem this arrangement exists to prevent. Change the rule in
`scripts/flight_rules.py`, run `validate_dataset.py`, then regenerate.
