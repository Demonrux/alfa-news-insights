from prompts.pe.infra.repo import CASES as CASES_DIR, load_cases, refs

R = refs()
CASES = {c["id"]: c for c in load_cases(CASES_DIR / "p5_cases.yaml")}
P1 = {c["id"]: c for c in load_cases(CASES_DIR / "p1_cases.yaml")}
FIRST = CASES["rate_cfo_construction"]
ROLES = tuple(R.role_names)
