# RCA eval (hard-rule scorer)

Three labeled scenarios. The scorer does **not** call an LLM. It checks whether
the answer body contains the phrases in `eval_scenarios.py`.

| id | inject | what a hit means |
|----|--------|------------------|
| `healthy-baseline` | nothing | agent does **not** invent an incident |
| `pod-kill-frontend` | existing PodChaos | names **frontend** + a kill/terminate verb |
| `pod-kill-checkout` | new PodChaos | names **checkout** + a kill/terminate verb |

`healthy-baseline` is first on purpose so leftover kill events do not pollute it.

## Commands

```powershell
cd components
# catalog only — no cluster, no API key
python -m agent_cli.eval_rca --list
python -m agent_cli.eval_rca --dry-run

# live (needs cluster + Chaos Mesh + DEEPSEEK_API_KEY)
python -m agent_cli.eval_rca --scenario healthy-baseline
python -m agent_cli.eval_rca --all
```

`--all` writes `data/eval/rca_eval_<timestamp>.json` (gitignored).

`--skip-inject` runs the agent against whatever is already in the cluster
(useful if you already ran `.\infra\chaos\run-demo.ps1`).

## What the numbers mean

- **root-cause hit**: phrase check on the answer *body* (the evidence footer is stripped).
- **evidence HIGH/MEDIUM/LOW**: the Step-1 stamp from tool-call counts. Separate metric.
- **expected tools missing**: reported, does not flip the hit by itself.

A hit is not “this is a good RCA”. It is “the agent named the labeled fault”.
Wrong-service stories fail (checkout scenario + frontend-only answer = miss).

## Unit tests (no cluster)

```powershell
cd components
python -m pytest agent_cli/tests/test_eval_score.py -q
```
