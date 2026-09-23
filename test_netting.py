import unittest

from netting import find_debt_cycle, calculate_cycle_netting


class NettingTests(unittest.TestCase):
    def test_three_company_cycle(self):
        debts = [
            {"from": "CompanyA", "to": "CompanyB", "amount": 100000},
            {"from": "CompanyB", "to": "CompanyC", "amount": 80000},
            {"from": "CompanyC", "to": "CompanyA", "amount": 70000},
        ]
        cycle = find_debt_cycle(debts)
        self.assertIsNotNone(cycle)
        result = calculate_cycle_netting(cycle)
        self.assertEqual(result["netting_amount_per_link"], 70000)
        self.assertEqual(result["total_before"], 250000)
        self.assertEqual(result["total_after"], 40000)
        self.assertEqual(result["debt_eliminated"], 210000)

    def test_no_cycle(self):
        debts = [
            {"from": "CompanyA", "to": "CompanyB", "amount": 100000},
            {"from": "CompanyB", "to": "CompanyC", "amount": 80000},
        ]
        self.assertIsNone(find_debt_cycle(debts))


if __name__ == "__main__":
    unittest.main()
