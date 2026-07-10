"""Optimizer pass manager. Each pass is independently toggleable via the
CLI's --passes= allowlist (decisions.md #8). Selected passes run in a
fixed sequence, repeated until a full round changes nothing (each pass can
expose opportunities for the others - e.g. constant propagation turning a
BinOp's operands into constants for folding to pick up, folding then
turning a branch condition constant for DCE to prune) or MAX_ROUNDS is
hit, whichever comes first."""

from . import constant_folding, constant_propagation, cse, dce

MAX_ROUNDS = 10

PASS_REGISTRY = {
    "const-fold": constant_folding.run,
    "const-prop": constant_propagation.run,
    "dce": dce.run,
    "cse": cse.run,
}

# order passes run in within a single round, regardless of the order they
# were named in --passes=
PASS_ORDER = ["const-prop", "const-fold", "cse", "dce"]


def run_passes(module, pass_names):
    unknown = set(pass_names) - set(PASS_REGISTRY)
    if unknown:
        raise ValueError(f"unknown optimization pass(es): {sorted(unknown)}")

    selected = [name for name in PASS_ORDER if name in pass_names]
    for _ in range(MAX_ROUNDS):
        changed = False
        for name in selected:
            changed |= PASS_REGISTRY[name](module)
        if not changed:
            break
    return module
