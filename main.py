#!/usr/bin/env python3
# PMaP — Planificador de Malla y Prerrequisitos (Versión mejorada)
# Cambios clave respecto a la versión base:
# - Opción de cargar dataset desde JSON
# - Exportar sugerencia a CSV
# - Graficar el grafo con networkx/matplotlib (colores: aprobadas, candidatas, resto)
# - Reporte de materias bloqueadas + prereqs faltantes
# - Métricas básicas (V, E, tiempo de topo_sort)
# - Plan completo por semestres (iterativo) bajo tope de créditos
#
# Requisitos adicionales opcionales para graficar:
#   pip install networkx matplotlib
#
from __future__ import annotations
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, Set, List, Tuple, Optional
import json, os, re, time, csv
from pathlib import Path

@dataclass
class Course:
    code: str
    name: str
    credits: int

@dataclass
class PMaPModel:
    courses: Dict[str, Course] = field(default_factory=dict)
    prereqs: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))
    passed: Set[str] = field(default_factory=set)

    def to_dict(self) -> dict:
        return {
            "courses": [
                {"code": c.code, "name": c.name, "credits": c.credits}
                for c in self.courses.values()
            ],
            "prerequisites": [[p, c] for c, pres in self.prereqs.items() for p in pres],
            "passed": sorted(list(self.passed)),
        }

    @staticmethod
    def from_dict(data: dict) -> 'PMaPModel':
        model = PMaPModel()
        for c in data.get("courses", []):
            model.courses[c["code"].upper()] = Course(c["code"].upper(), c["name"], int(c["credits"]))
        for p, c in data.get("prerequisites", []):
            p, c = p.upper(), c.upper()
            model.prereqs[c].add(p)
            if p not in model.courses:
                model.courses[p] = Course(p, p, 0)
            if c not in model.courses:
                model.courses[c] = Course(c, c, 0)
        model.passed = set([x.upper() for x in data.get("passed", [])])
        return model

    def save_json(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @staticmethod
    def load_json(path: str) -> 'PMaPModel':
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return PMaPModel.from_dict(data)

    def add_course(self, code: str, name: str, credits: int):
        code = code.strip().upper()
        self.courses[code] = Course(code, name.strip(), int(credits))
        _ = self.prereqs[code]

    def add_prereq(self, prereq: str, course: str):
        prereq = prereq.strip().upper()
        course = course.strip().upper()
        if course == prereq:
            raise ValueError("Una materia no puede ser prerrequisito de sí misma.")
        if prereq not in self.courses:
            self.courses[prereq] = Course(prereq, prereq, 0)
        if course not in self.courses:
            self.courses[course] = Course(course, course, 0)
        self.prereqs[course].add(prereq)

    def mark_passed(self, code: str):
        code = code.strip().upper()
        if code not in self.courses:
            raise KeyError(f"Materia desconocida: {code}")
        self.passed.add(code)

    def build_graph(self) -> Tuple[Dict[str, Set[str]], Dict[str, int]]:
        adjacency: Dict[str, Set[str]] = {c: set() for c in self.courses}
        indegree: Dict[str, int] = {c: 0 for c in self.courses}
        for course, pres in self.prereqs.items():
            for p in pres:
                adjacency.setdefault(p, set()).add(course)
                indegree[course] = indegree.get(course, 0) + 1
                indegree.setdefault(p, 0)
        for c in self.courses:
            adjacency.setdefault(c, set())
            indegree.setdefault(c, 0)
        return adjacency, indegree

    def topo_sort(self) -> Tuple[List[str], bool, Optional[List[str]]]:
        adjacency, indegree = self.build_graph()
        q = deque([c for c, d in indegree.items() if d == 0])
        order: List[str] = []
        indegree_copy = dict(indegree)
        while q:
            u = q.popleft()
            order.append(u)
            for v in adjacency.get(u, []):
                indegree_copy[v] -= 1
                if indegree_copy[v] == 0:
                    q.append(v)
        has_cycle = len(order) != len(indegree_copy)
        cycle = None
        if has_cycle:
            visited = set()
            stack = set()
            parent = {}
            def dfs(u):
                nonlocal cycle
                visited.add(u)
                stack.add(u)
                for v in adjacency.get(u, []):
                    if indegree_copy[v] > 0:
                        if v not in visited:
                            parent[v] = u
                            if dfs(v):
                                return True
                        elif v in stack:
                            path = [v]
                            cur = u
                            while cur != v:
                                path.append(cur)
                                cur = parent[cur]
                            path.append(v)
                            path.reverse()
                            cycle = path
                            return True
                stack.remove(u)
                return False
            for node, deg in indegree_copy.items():
                if deg > 0 and node not in visited:
                    if dfs(node):
                        break
        return order, has_cycle, cycle

    def current_indegree_effective(self) -> Dict[str, int]:
        indeg = {c: 0 for c in self.courses}
        for course, pres in self.prereqs.items():
            for p in pres:
                if p not in self.passed:
                    indeg[course] += 1
        return indeg

    def candidates(self) -> List[str]:
        indeg_eff = self.current_indegree_effective()
        return sorted([c for c, d in indeg_eff.items() if d == 0 and c not in self.passed])

    def unlock_count(self, course_code: str) -> int:
        adjacency, _ = self.build_graph()
        count = 0
        for v in adjacency.get(course_code, []):
            other_pres = self.prereqs.get(v, set()) - {course_code}
            if all(p in self.passed for p in other_pres):
                count += 1
        return count

    def suggest_next_semester(self, credit_cap: int, criterion: str = "desbloqueo") -> Tuple[List[str], int, List[str]]:
        cand = self.candidates()
        def priority_key(code: str):
            if criterion == "desbloqueo":
                return (-self.unlock_count(code), self.courses[code].credits, code)
            elif criterion == "creditos":
                return (self.courses[code].credits, code)
            elif criterion == "nivel":
                digits = re.findall(r'\d+', code)
                level = int(digits[0]) if digits else 9999
                return (level, code)
            else:
                return (0, code)
        cand_sorted = sorted(cand, key=priority_key)
        chosen, total, reasons = [], 0, []
        for code in cand_sorted:
            cr = self.courses[code].credits
            if total + cr <= credit_cap:
                chosen.append(code)
                total += cr
                reasons.append(f"{code} ({cr} cr) — desbloquea {self.unlock_count(code)} materia(s)")
        return chosen, total, reasons

EXAMPLE_DATA = {
    "courses": [
        {"code": "MAT101", "name": "Cálculo I", "credits": 4},
        {"code": "MAT102", "name": "Cálculo II", "credits": 4},
        {"code": "FIS101", "name": "Física I", "credits": 3},
        {"code": "EDA1", "name": "Estructuras de Datos I", "credits": 3},
        {"code": "EDA2", "name": "Estructuras de Datos II", "credits": 4},
    ],
    "prerequisites": [
        ["MAT101", "MAT102"],
        ["MAT101", "FIS101"],
        ["MAT102", "EDA1"],
        ["EDA1", "EDA2"],
    ],
    "passed": ["MAT101"],
}

def pause():
    input("\n(Enter para continuar) ")

def print_courses(model: PMaPModel):
    print("\nMaterias registradas:")
    for c in sorted(model.courses.values(), key=lambda x: x.code):
        mark = "✓" if c.code in model.passed else " "
        print(f"[{mark}] {c.code:7s} | {c.credits:2d} cr | {c.name}")

def print_prereqs(model: PMaPModel):
    print("\nPrerrequisitos (P -> C):")
    lines = []
    for c in sorted(model.courses.keys()):
        for p in sorted(model.prereqs.get(c, [])):
            lines.append((p, c))
    if not lines:
        print(" (ninguno)")
    else:
        for p, c in sorted(lines):
            print(f"  {p}  ->  {c}")

def action_topo(model: PMaPModel):
    t0 = time.perf_counter()
    order, has_cycle, cycle = model.topo_sort()
    t1 = time.perf_counter()
    if has_cycle:
        print("\n⚠ Se detectó un ciclo en los prerrequisitos.")
        if cycle:
            print("Ciclo ejemplo:", " -> ".join(cycle))
    else:
        print("\nNo hay ciclos. Orden topológico posible:")
        print("  " + " -> ".join(order))
    print(f"(topo_sort en {(t1 - t0)*1e3:.2f} ms)")

def action_candidates(model: PMaPModel):
    cand = model.candidates()
    if not cand:
        print("\nNo hay candidatas disponibles (revisa prerrequisitos o marca más aprobadas).")
    else:
        print("\nCandidatas (indegree efectivo 0):")
        for code in cand:
            print(f"  {code} ({model.courses[code].credits} cr)")

def action_suggest(model: PMaPModel):
    try:
        cap = int(input("Tope de créditos para el semestre (ej. 16): ").strip())
    except ValueError:
        print("Valor inválido.")
        return
    crit = input("Criterio [desbloqueo | creditos | nivel] (default desbloqueo): ").strip().lower() or "desbloqueo"
    chosen, total, reasons = model.suggest_next_semester(cap, crit)
    if not chosen:
        print("\nNo se pudo sugerir un conjunto sin exceder el tope.")
    else:
        print("\nSugerencia de próximo semestre:")
        for r in reasons:
            print("  -", r)
        print(f"Total créditos: {total} / {cap}")

def action_mark_passed(model: PMaPModel):
    code = input("Código de materia aprobada (ej. MAT101): ").strip().upper()
    try:
        model.mark_passed(code)
        print(f"Marcada {code} como aprobada.")
    except KeyError as e:
        print(str(e))

def action_add_course(model: PMaPModel):
    code = input("Código (ej. EDA1): ").strip().upper()
    name = input("Nombre: ").strip()
    try:
        credits = int(input("Créditos (int): ").strip())
    except ValueError:
        print("Créditos inválidos.")
        return
    model.add_course(code, name, credits)
    print(f"Agregada {code}.")

def action_add_prereq(model: PMaPModel):
    prereq = input("Prerrequisito (ej. MAT102): ").strip().upper()
    course = input("Materia destino (ej. EDA1): ").strip().upper()
    try:
        model.add_prereq(prereq, course)
        print(f"Agregado prerrequisito: {prereq} -> {course}")
    except ValueError as e:
        print(str(e))

def action_save(model: PMaPModel):
    path = input("Ruta de salida JSON (ej. data/mi_malla.json): ").strip() or "data/mi_malla.json"
    model.save_json(path)
    print(f"Guardado en {path}")

def action_load_json(current_model: PMaPModel) -> PMaPModel:
    path = input("Ruta JSON a cargar (ej. data/malla_ampliada.json): ").strip()
    try:
        new_model = PMaPModel.load_json(path)
        print(f"Cargado {path}  (materias: {len(new_model.courses)}, prereqs: {sum(len(v) for v in new_model.prereqs.values())})")
        return new_model
    except Exception as e:
        print(f"Error al cargar: {e}")
        return current_model

def action_export_suggestion(model: PMaPModel):
    try:
        cap = int(input("Tope de créditos: ").strip())
    except ValueError:
        print("Valor inválido."); return
    crit = input("Criterio [desbloqueo | creditos | nivel] (default desbloqueo): ").strip().lower() or "desbloqueo"
    chosen, total, reasons = model.suggest_next_semester(cap, crit)
    Path("out").mkdir(exist_ok=True)
    csv_path = f"out/sugerencia_{cap}_{crit}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["codigo","nombre","creditos","desbloquea","criterio"])
        for code in chosen:
            w.writerow([code, model.courses[code].name, model.courses[code].credits, model.unlock_count(code), crit])
        w.writerow([]); w.writerow(["total_creditos", total])
    print(f"Exportado a {csv_path}")

def action_report_blocked(model: PMaPModel):
    indeg = model.current_indegree_effective()
    print("\nMaterias bloqueadas (faltan prerequisitos):")
    blocked = [c for c,d in indeg.items() if c not in model.passed and d>0]
    if not blocked:
        print(" (ninguna)"); return
    for c in sorted(blocked):
        missing = [p for p in model.prereqs.get(c,set()) if p not in model.passed]
        print(f"  {c} necesita: {', '.join(missing)}")

def action_metrics(model: PMaPModel):
    adjacency, _ = model.build_graph()
    V = len(adjacency); E = sum(len(v) for v in adjacency.values())
    t0=time.perf_counter(); _ = model.topo_sort(); t1=time.perf_counter()
    order, has_cycle, cycle = _
    print(f"\nMétricas: V={V} materias, E={E} prerrequisitos")
    print(f"Topo_sort: {(t1-t0)*1e3:.2f} ms — ciclo: {'sí' if has_cycle else 'no'}")
    if has_cycle and cycle:
        print("Ciclo ejemplo:", " -> ".join(cycle))

def action_plot_graph(model: PMaPModel):
    try:
        import networkx as nx
        import matplotlib.pyplot as plt
    except Exception as e:
        print("Para graficar instala: pip install networkx matplotlib")
        print(f"Detalle: {e}")
        return
    G = nx.DiGraph()
    for c in model.courses: G.add_node(c)
    for course, pres in model.prereqs.items():
        for p in pres: G.add_edge(p, course)
    cand = set(model.candidates())
    colors = []
    for n in G.nodes():
        if n in model.passed: colors.append("lightgreen")
        elif n in cand: colors.append("khaki")
        else: colors.append("lightblue")
    pos = nx.spring_layout(G, seed=42)
    nx.draw(G, pos, with_labels=True, node_color=colors, node_size=1200, arrows=True, arrowsize=20, arrowstyle="-|>")
    Path("out").mkdir(exist_ok=True)
    out_path = "out/grafo.png"
    import matplotlib.pyplot as plt
    plt.title("PMaP — Grafo de prerrequisitos (verde=aprobada, amarillo=candidata)")
    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Gráfico guardado en {out_path}")

def plan_full(model: PMaPModel, credit_cap: int, criterion: str = "desbloqueo", max_semesters: int = 12):
    temp = PMaPModel.from_dict(model.to_dict())
    semesters = []
    for s in range(1, max_semesters+1):
        chosen, total, reasons = temp.suggest_next_semester(credit_cap, criterion)
        if not chosen:
            break
        semesters.append((chosen, total, reasons))
        for c in chosen: temp.mark_passed(c)
    return semesters

def action_plan_full(model: PMaPModel):
    try:
        cap = int(input("Tope de créditos por semestre: ").strip())
    except ValueError:
        print("Valor inválido."); return
    crit = input("Criterio [desbloqueo | creditos | nivel] (default desbloqueo): ").strip().lower() or "desbloqueo"
    semesters = plan_full(model, cap, crit)
    if not semesters:
        print("No hay materias cursables; revisa prerrequisitos o aprobadas.")
        return
    for i, (chs, total, reasons) in enumerate(semesters, 1):
        print(f"\nSemestre {i} ({total} cr):")
        for r in reasons: print("  -", r)

def action_load_example() -> PMaPModel:
    print("Cargando dataset de ejemplo embebido...")
    return PMaPModel.from_dict(EXAMPLE_DATA)

def main():
    model = action_load_example()
    while True:
        print("\n=== PMaP — Planificador de Malla y Prerrequisitos (Mejorado) ===")
        print("1) Ver materias")
        print("2) Ver prerrequisitos")
        print("3) Detectar ciclos y orden topológico")
        print("4) Ver candidatas actuales")
        print("5) Sugerir próximo semestre")
        print("6) Marcar materia como aprobada")
        print("7) Agregar materia")
        print("8) Agregar prerrequisito")
        print("9) Guardar dataset (JSON)")
        print("10) Cargar dataset (JSON)")
        print("11) Exportar sugerencia (CSV)")
        print("12) Graficar grafo (networkx/matplotlib)")
        print("13) Reporte de materias bloqueadas")
        print("14) Métricas (V, E, tiempo)")
        print("15) Plan completo por semestres")
        print("0) Salir")
        opt = input("> ").strip()
        if opt == "1":
            print_courses(model); pause()
        elif opt == "2":
            print_prereqs(model); pause()
        elif opt == "3":
            action_topo(model); pause()
        elif opt == "4":
            action_candidates(model); pause()
        elif opt == "5":
            action_suggest(model); pause()
        elif opt == "6":
            action_mark_passed(model); pause()
        elif opt == "7":
            action_add_course(model); pause()
        elif opt == "8":
            action_add_prereq(model); pause()
        elif opt == "9":
            action_save(model); pause()
        elif opt == "10":
            model = action_load_json(model); pause()
        elif opt == "11":
            action_export_suggestion(model); pause()
        elif opt == "12":
            action_plot_graph(model); pause()
        elif opt == "13":
            action_report_blocked(model); pause()
        elif opt == "14":
            action_metrics(model); pause()
        elif opt == "15":
            action_plan_full(model); pause()
        elif opt == "0":
            print("¡Hasta luego!"); break
        else:
            print("Opción inválida."); pause()

if __name__ == "__main__":
    main()
