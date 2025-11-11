# PMaP_enhanced — Planificador de Malla y Prerrequisitos

**Proyecto EDA2 (4º semestre).**  
App de **consola** que representa la malla como **grafo dirigido** para: detectar **ciclos**, obtener **orden topológico** y **sugerir** el próximo semestre respetando un **tope de créditos**. También **grafica** el grafo, **carga/guarda** JSON y **exporta** CSV.

---

## 🚀 Ejecutar
```powershell
cd .\PMaP_enhanced
python .\main.py     
```

### para graficar
```powershell
python -m pip install networkx matplotlib
```

---

## 🧠 Qué hace 
- Modelamos materias como **nodos** y prerrequisitos como **aristas dirigidas** `P → C`.
- Con **Kahn** (indegree + cola) detectamos **ciclos** y sacamos un **orden topológico** (**O(V+E)**).
- Desde las **aprobadas** calculamos **candidatas** (indegree **efectivo = 0**) y armamos una **sugerencia** ≤ tope con un **criterio**:
  - `desbloqueo` (abre más materias), `creditos` (menor carga) o `nivel` (1000, 2000…).
- Extras: **gráfico** del grafo, **métricas** (V, E, tiempo), **plan completo** por semestres, **CSV** de la sugerencia.

---

## 🧩 Modelo y EDD
- `Course(code, name, credits)`  
- `PMaPModel`:  
  - `courses: dict[str, Course]`  
  - `prereqs: dict[str, set[str]]` *(lista de adyacencia dirigida)*  
  - `passed: set[str]`
- Complejidad: construir grafo **O(V+E)**; Kahn **O(V+E)**; candidatas **O(E)**; selección **O(C log C)**.

---

## 📋 Menú 
1 Ver materias · 2 Ver prerrequisitos · **3 Topo + ciclos (Kahn)** · 4 Candidatas · 5 Sugerir semestre (tope + criterio) · 6 Marcar aprobada · 7 Agregar materia · 8 Agregar prerrequisito · 9 Guardar JSON · **10 Cargar JSON** · **11 Exportar CSV** · **12 Graficar grafo** (PNG) · **13 Bloqueadas** (qué falta) · **14 Métricas** (V, E, tiempo) · **15 Plan completo** · 0 Salir.

---

## 📂 Datasets
- **Grande:** `data/malla_ampliada.json` (20+ materias).  
- **Embebido:** mini de arranque.  
- **Propios:** usa **9/10** para guardar/cargar.

---

## 📦 Evidencias útiles
- `out/grafo.png` (verde=aprobada, amarillo=candidata, azul=resto).  
- `out/sugerencia_{cap}_{criterio}.csv` (códigos, créditos, “desbloquea n”).

---

## 🧭 Demo rápida 
1) **10** `data/malla_ampliada.json` → **14** métricas (mencionar **O(V+E)**).  
2) **3** orden topológico (o ciclo si lo hay).  
3) **12** genera `out/grafo.png`.  
4) **5** sugerencia (tope 16, criterio `desbloqueo`) → **11** exporta CSV.  
5) (Opcional) **15** plan completo por semestres.

---

## 🧪 Tests (opcional)
```powershell
python -m unittest -v -s tests
```
Topo sin ciclo · detección de ciclo · candidatas con aprobadas.

---

## 🔧 Problemas comunes
- **No encuentra main.py** → `cd .\PMaP_enhanced` y `dir` para verificar que está `main.py`.  
- **No grafica** → instala `networkx` y `matplotlib`, luego opción **12**.  

**Resumen:** grafo dirigido + Kahn + heurística de selección = planificador de malla funcional, con visualización y exportables. Ideal para EDA2.