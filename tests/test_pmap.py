import unittest
from main import PMaPModel

class TestPMaP(unittest.TestCase):
    def setUp(self):
        self.model = PMaPModel.from_dict({
            "courses":[
                {"code":"A","name":"A","credits":1},
                {"code":"B","name":"B","credits":1},
                {"code":"C","name":"C","credits":1},
                {"code":"D","name":"D","credits":1}
            ],
            "prerequisites":[["A","B"],["B","C"]],
            "passed":["A"]
        })

    def test_topo_no_cycle(self):
        order, has_cycle, cycle = self.model.topo_sort()
        self.assertFalse(has_cycle)
        self.assertEqual(set(order), set(["A","B","C","D"]))

    def test_candidates_with_passed(self):
        cands = set(self.model.candidates())
        self.assertIn("B", cands)   # Aprobada A -> B queda libre
        self.assertIn("D", cands)   # D sin prereq
        self.assertNotIn("C", cands)  # C depende de B

    def test_cycle_detection(self):
        self.model.add_prereq("C","A")  # A<-B<-C<-A (ciclo)
        order, has_cycle, cycle = self.model.topo_sort()
        self.assertTrue(has_cycle)
        # Debe haber un ciclo detectado o al menos marcado
        assert has_cycle

if __name__ == "__main__":
    unittest.main()
