"""Core circular-debt detection and multilateral netting logic for DebtLoop."""

from typing import Any, Dict, List, Optional

Debt = Dict[str, Any]


def find_debt_cycle(active_debts: List[Debt]) -> Optional[List[Debt]]:
    """Return the first directed debt cycle found, or None if there is no cycle."""
    graph: Dict[str, List[Debt]] = {}

    for debt in active_debts:
        if debt.get("amount", 0) <= 0:
            continue
        graph.setdefault(debt["from"], []).append(debt)

    def search(current: str, path_nodes: List[str], path_debts: List[Debt]):
        for debt in graph.get(current, []):
            next_user = debt["to"]

            if next_user in path_nodes:
                cycle_start = path_nodes.index(next_user)
                return path_debts[cycle_start:] + [debt]

            if len(path_nodes) < len(graph) + 1:
                result = search(
                    next_user,
                    path_nodes + [next_user],
                    path_debts + [debt],
                )
                if result:
                    return result

        return None

    for start_user in graph:
        result = search(start_user, [start_user], [])
        if result:
            return result

    return None


def calculate_cycle_netting(cycle: List[Debt]) -> Dict[str, Any]:
    """Calculate the maximum equal offset that can be applied around one cycle."""
    if not cycle:
        raise ValueError("Cycle must contain at least one debt")

    netting_amount = min(d["amount"] for d in cycle)
    total_before = sum(d["amount"] for d in cycle)

    residual_debts = []
    for debt in cycle:
        residual = debt["amount"] - netting_amount
        residual_debts.append(
            {
                "from": debt["from"],
                "to": debt["to"],
                "before": debt["amount"],
                "after": residual,
            }
        )

    total_after = sum(d["after"] for d in residual_debts)

    return {
        "netting_amount_per_link": netting_amount,
        "total_before": total_before,
        "total_after": total_after,
        "debt_eliminated": total_before - total_after,
        "residual_debts": residual_debts,
    }
