# -*- coding: utf-8 -*-
"""
Licitacao Cost Calculator - HLX TECH (PySide6 GUI completo)
- Colunas auto-ajustáveis
- Edição de projeto, produtos e outros custos
- Relatório completo (DIFAL IN/OUT, DAS, custo total, lucro, margens)
- Gerar relatório pelo menu principal (selecionando projeto ou digitando número)
"""

import os
import sys
import json
import sqlite3
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTableWidget, QTableWidgetItem, QMessageBox,
    QDialog, QFormLayout, QLineEdit, QHeaderView, QTextEdit,
    QLabel, QInputDialog, QSpinBox, QDoubleSpinBox
)
from PySide6.QtCore import Qt

# -----------------------------
# FUNÇÃO caminho_recurso
# -----------------------------
def caminho_recurso(relativo):
    """Retorna o caminho absoluto para um recurso quando empacotado ou rodando no Python"""
    if hasattr(sys, "_MEIPASS"):
        # Usado apenas para arquivos de leitura (ex: ícones, imagens)
        return os.path.join(sys._MEIPASS, relativo)  # type: ignore
    return os.path.join(os.path.abspath("."), relativo)

# -----------------------------
# DEFINIR OS CAMINHOS
# -----------------------------
# Diretório onde o executável ou script está rodando
if getattr(sys, 'frozen', False):  # executável PyInstaller
    BASE_DIR = os.path.dirname(sys.executable)
else:  # script Python normal
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Banco de dados fica sempre fora do .exe, persistente
DB_FILE = os.path.join(BASE_DIR, "licitacao.db")

# Pasta de relatórios ao lado do programa
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

COMPANY_STATE = 'MG'
DEFAULT_INTERSTATE_RATE = 0.12
DEFAULT_STATE_RATES = {'MG': 0.18, 'SP': 0.18, 'RJ': 0.20}
DEFAULT_SIMPLES_RATE = 0.05

conn = sqlite3.connect(DB_FILE)
cur = conn.cursor()

# -----------------------------
# SCHEMA
# -----------------------------
cur.executescript(f"""
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_number TEXT UNIQUE,
    client_name TEXT,
    gross_sale REAL DEFAULT 0.0,
    purchase_state TEXT,
    sale_state TEXT,
    simples_rate REAL DEFAULT {DEFAULT_SIMPLES_RATE},
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    description TEXT,
    purchase_cost REAL,
    sale_price REAL,
    qty INTEGER DEFAULT 1,
    purchase_state TEXT,
    sale_state TEXT,
    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS other_costs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    description TEXT,
    cost REAL,
    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);
""")
conn.commit()

# -----------------------------
# FUNÇÕES AUXILIARES
# -----------------------------
def state_rate(state: str) -> float:
    if not state:
        return 0.0
    return DEFAULT_STATE_RATES.get(state.upper(), DEFAULT_INTERSTATE_RATE)

def load_project(project_id: int):
    cur.execute('SELECT id, project_number, client_name, gross_sale, purchase_state, sale_state, simples_rate FROM projects WHERE id=?', (project_id,))
    p = cur.fetchone()
    if not p:
        return None
    project = dict(
        id=p[0], project_number=p[1], client_name=p[2],
        gross_sale=p[3] or 0.0, purchase_state=p[4] or '',
        sale_state=p[5] or '', simples_rate=p[6] or DEFAULT_SIMPLES_RATE
    )
    cur.execute('SELECT id, description, purchase_cost, sale_price, qty, purchase_state, sale_state FROM products WHERE project_id=?', (project_id,))
    project['products'] = [
        dict(id=r[0], description=r[1], purchase_cost=r[2] or 0.0,
             sale_price=r[3] or 0.0, qty=r[4] or 1,
             purchase_state=r[5] or '', sale_state=r[6] or '')
        for r in cur.fetchall()
    ]
    cur.execute('SELECT id, description, cost FROM other_costs WHERE project_id=?', (project_id,))
    project['other_costs'] = [
        dict(id=r[0], description=r[1], cost=r[2] or 0.0)
        for r in cur.fetchall()
    ]
    return project

def calculate_report(project: dict):
    total_sale_from_products = sum((p['sale_price'] or 0) * (p['qty'] or 1) for p in project['products'])
    gross = total_sale_from_products if total_sale_from_products > 0 else float(project['gross_sale'] or 0.0)
    simples_rate = float(project.get('simples_rate', DEFAULT_SIMPLES_RATE) or DEFAULT_SIMPLES_RATE)
    
    product_subtotals = []
    total_purchase = 0.0
    total_sale_assigned = 0.0
    interstate_rate = DEFAULT_INTERSTATE_RATE
    company_internal_rate = state_rate(COMPANY_STATE)
    
    for p in project['products']:
        qty = p.get('qty') or 1
        purchase_total = float(p.get('purchase_cost') or 0.0) * qty
        sale_total = float(p.get('sale_price') or 0.0) * qty
        total_purchase += purchase_total
        total_sale_assigned += sale_total
        origin = (p.get('purchase_state') or project.get('purchase_state') or '').upper()
        dest = (p.get('sale_state') or project.get('sale_state') or '').upper()
        product_subtotals.append({
            'id': p['id'], 'description': p['description'], 'qty': qty,
            'purchase_total': purchase_total, 'sale_total': sale_total,
            'purchase_state': origin, 'sale_state': dest
        })
    
    das_total = gross * simples_rate
    
    total_difal_out = 0.0
    for item in product_subtotals:
        dst = item['sale_state']
        sale_value = item['sale_total'] if item['sale_total'] > 0 else item['purchase_total']
        difal_out = max(0.0, (state_rate(dst) - interstate_rate)) * sale_value if dst and dst != COMPANY_STATE else 0.0
        item['difal_out'] = difal_out
        total_difal_out += difal_out
    
    total_difal_in = 0.0
    for item in product_subtotals:
        origin = item['purchase_state']
        purchase_value = item['purchase_total']
        difal_in = max(0.0, (company_internal_rate - interstate_rate)) * purchase_value if origin and origin != COMPANY_STATE else 0.0
        item['difal_in'] = difal_in
        total_difal_in += difal_in
    
    total_other = sum(o['cost'] for o in project['other_costs'])
    total_cost = total_purchase + total_difal_in + total_difal_out + total_other + das_total
    net_value = gross - total_cost
    net_percent = (net_value / gross * 100.0) if gross else 0.0
    
    profit_margins = [0.10, 0.15, 0.20]
    min_sale_for_profit = {f"{int(m*100)}%": round(total_cost / (1 - m), 2) for m in profit_margins}
    
    report = {
        'project_number': project['project_number'],
        'client_name': project['client_name'],
        'created_at': datetime.now().isoformat(),
        'company_state': COMPANY_STATE,
        'gross_sale': gross,
        'simples_rate': simples_rate,
        'das_total': das_total,
        'products': product_subtotals,
        'total_purchase': total_purchase,
        'total_difal_in': total_difal_in,
        'total_difal_out': total_difal_out,
        'other_costs': project['other_costs'],
        'total_other': total_other,
        'total_cost': total_cost,
        'net_value': net_value,
        'net_percent': net_percent,
        'min_sale_for_profit': min_sale_for_profit,
        'assumptions': {
            'interstate_rate': interstate_rate,
            'state_rates': DEFAULT_STATE_RATES,
            'note': 'Modelo simplificado para Simples Nacional; ajuste conforme regras específicas de seu regime/NCM.'
        }
    }
    return report

def save_report_json(report: dict):
    fname = os.path.join(REPORTS_DIR, f"report_{report['project_number']}_{datetime.now().strftime('%Y%m%d%H%M%S')}.json")
    with open(fname, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return fname

# ---------------- DIALOGs ----------------
class ProductDialog(QDialog):
    def __init__(self, project_id, product=None, parent=None):
        super().__init__(parent)
        self.project_id = project_id
        self.product = product
        self.setWindowTitle("Produto")
        form = QFormLayout(self)

        self.desc = QLineEdit(product['description'] if product else "")
        self.purchase_cost = QDoubleSpinBox()
        self.purchase_cost.setMaximum(1e12)
        self.purchase_cost.setDecimals(2)
        self.purchase_cost.setValue(float(product['purchase_cost']) if product else 0.0)

        self.sale_price = QDoubleSpinBox()
        self.sale_price.setMaximum(1e12)
        self.sale_price.setDecimals(2)
        self.sale_price.setValue(float(product['sale_price']) if product else 0.0)

        self.qty = QSpinBox()
        self.qty.setMaximum(10**9)
        self.qty.setValue(int(product['qty']) if product else 1)

        self.p_state = QLineEdit(product.get('purchase_state', '') if product else "")
        self.s_state = QLineEdit(product.get('sale_state', '') if product else "")

        form.addRow("Descrição:", self.desc)
        form.addRow("Custo compra (un):", self.purchase_cost)
        form.addRow("Preço venda (un):", self.sale_price)
        form.addRow("Quantidade:", self.qty)
        form.addRow("UF Origem (opcional):", self.p_state)
        form.addRow("UF Destino (opcional):", self.s_state)

        btns = QHBoxLayout()
        save = QPushButton("Salvar")
        save.setMinimumWidth(90)
        save.clicked.connect(self.on_save)
        cancel = QPushButton("Cancelar")
        cancel.setMinimumWidth(90)
        cancel.clicked.connect(self.reject)
        btns.addWidget(save)
        btns.addWidget(cancel)
        form.addRow(btns)

    def on_save(self):
        desc = self.desc.text().strip()
        if not desc:
            QMessageBox.warning(self, "Erro", "Descrição é obrigatória.")
            return

        purchase_cost = float(self.purchase_cost.value())
        sale_price = float(self.sale_price.value())
        qty = int(self.qty.value())
        p_state = self.p_state.text().strip().upper() or None
        s_state = self.s_state.text().strip().upper() or None

        if self.product:  # update
            cur.execute('''UPDATE products
                           SET description=?, purchase_cost=?, sale_price=?, qty=?, purchase_state=?, sale_state=?
                           WHERE id=?''',
                        (desc, purchase_cost, sale_price, qty, p_state, s_state, self.product['id']))
        else:  # insert
            cur.execute('''INSERT INTO products (project_id, description, purchase_cost, sale_price, qty, purchase_state, sale_state)
                           VALUES (?,?,?,?,?,?,?)''',
                        (self.project_id, desc, purchase_cost, sale_price, qty, p_state, s_state))
        conn.commit()
        self.accept()

class OtherCostDialog(QDialog):
    def __init__(self, project_id, cost=None, parent=None):
        super().__init__(parent)
        self.project_id = project_id
        self.cost = cost
        self.setWindowTitle("Outro Custo")
        form = QFormLayout(self)

        self.desc = QLineEdit(cost['description'] if cost else "")
        self.value = QDoubleSpinBox()
        self.value.setMaximum(1e12)
        self.value.setDecimals(2)
        self.value.setValue(float(cost['cost']) if cost else 0.0)

        form.addRow("Descrição:", self.desc)
        form.addRow("Valor:", self.value)

        btns = QHBoxLayout()
        save = QPushButton("Salvar")
        save.setMinimumWidth(90)
        save.clicked.connect(self.on_save)
        cancel = QPushButton("Cancelar")
        cancel.setMinimumWidth(90)
        cancel.clicked.connect(self.reject)
        btns.addWidget(save)
        btns.addWidget(cancel)
        form.addRow(btns)

    def on_save(self):
        desc = self.desc.text().strip()
        if not desc:
            QMessageBox.warning(self, "Erro", "Descrição é obrigatória.")
            return
        cost_val = float(self.value.value())
        if self.cost:
            cur.execute('UPDATE other_costs SET description=?, cost=? WHERE id=?',
                        (desc, cost_val, self.cost['id']))
        else:
            cur.execute('INSERT INTO other_costs (project_id, description, cost) VALUES (?,?,?)',
                        (self.project_id, desc, cost_val))
        conn.commit()
        self.accept()

class ReportDialog(QDialog):
    def __init__(self, project_id, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Relatório do Projeto")
        self.resize(800, 600)
        v = QVBoxLayout(self)

        project = load_project(project_id)
        if not project:
            QMessageBox.warning(self, "Erro", "Projeto não encontrado.")
            self.reject()
            return

        report = calculate_report(project)

        # Montagem do texto completo (similar ao CLI original)
        lines = []
        lines.append(f"Projeto: {report['project_number']} - {report['client_name']}")
        lines.append(f"Empresa (estado base): {report['company_state']}")
        lines.append(f"Venda bruta: R$ {report['gross_sale']:.2f}")
        lines.append(f"DAS (Simples {report['simples_rate']*100:.2f}%): R$ {report['das_total']:.2f}")
        lines.append("")
        lines.append("Produtos:")
        for it in report['products']:
            lines.append(
                f"  - {it['description']} | Qtd: {it['qty']} | "
                f"Compra: R$ {it['purchase_total']:.2f} | Venda: R$ {it['sale_total']:.2f} | "
                f"Origem: {it['purchase_state'] or '-'} | Destino: {it['sale_state'] or '-'} | "
                f"DIFAL IN: R$ {it['difal_in']:.2f} | DIFAL OUT: R$ {it['difal_out']:.2f}"
            )
        lines.append("")
        lines.append("Outros custos:")
        if report['other_costs']:
            for oc in report['other_costs']:
                lines.append(f"  - {oc['description']}: R$ {oc['cost']:.2f}")
        else:
            lines.append("  (nenhum)")
        lines.append("")
        lines.append(f"Total compras (produtos): R$ {report['total_purchase']:.2f}")
        lines.append(f"DIFAL ENTRADA (compra interestadual → {COMPANY_STATE}): R$ {report['total_difal_in']:.2f}")
        lines.append(f"DIFAL SAÍDA (venda interestadual): R$ {report['total_difal_out']:.2f}")
        lines.append(f"Outros custos: R$ {report['total_other']:.2f}")
        lines.append(f"CUSTO TOTAL: R$ {report['total_cost']:.2f}")
        lines.append(f"LUCRO LÍQUIDO: R$ {report['net_value']:.2f} ({report['net_percent']:.2f}%)")
        lines.append("")
        lines.append("Preço mínimo de venda para lucro desejado:")
        for margin, value in report['min_sale_for_profit'].items():
            lines.append(f"  {margin}: R$ {value:.2f}")
        lines.append("")
        lines.append("Premissas:")
        lines.append(f"  Alíquota interestadual: {report['assumptions']['interstate_rate']*100:.2f}%")
        srates = ", ".join(f"{k}:{v*100:.0f}%" for k,v in report['assumptions']['state_rates'].items())
        lines.append(f"  Alíquotas internas: {srates}")
        lines.append(f"  Nota: {report['assumptions']['note']}")

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setText("\n".join(lines))
        v.addWidget(self.text)

        btns = QHBoxLayout()
        save_json = QPushButton("Salvar JSON")
        save_json.setMinimumWidth(110)
        save_json.clicked.connect(lambda: self.on_save_json(report))
        close = QPushButton("Fechar")
        close.setMinimumWidth(90)
        close.clicked.connect(self.accept)
        btns.addWidget(save_json)
        btns.addWidget(close)
        v.addLayout(btns)

    def on_save_json(self, report):
        path = save_report_json(report)
        QMessageBox.information(self, "Relatório salvo", f"Arquivo salvo em:\n{path}")

class ProjectDialog(QDialog):
    """Editar dados do projeto e gerenciar Produtos/Outros Custos"""
    def __init__(self, project_id, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Detalhes do Projeto")
        self.resize(950, 600)
        self.project_id = project_id

        root = QVBoxLayout(self)

        # ---- Header com campos do projeto ----
        self.header_form = QFormLayout()
        self.client_name = QLineEdit()
        self.project_number = QLineEdit()
        self.gross_sale = QDoubleSpinBox()
        self.gross_sale.setMaximum(1e13); self.gross_sale.setDecimals(2)
        self.purchase_state = QLineEdit()
        self.sale_state = QLineEdit()
        self.simples_rate = QDoubleSpinBox()
        self.simples_rate.setDecimals(4); self.simples_rate.setSingleStep(0.005); self.simples_rate.setMaximum(1.0)

        self.header_form.addRow("Número do projeto:", self.project_number)
        self.header_form.addRow("Cliente:", self.client_name)
        self.header_form.addRow("Venda bruta (R$):", self.gross_sale)
        self.header_form.addRow("UF Origem (default):", self.purchase_state)
        self.header_form.addRow("UF Destino (default):", self.sale_state)
        self.header_form.addRow("Alíquota Simples:", self.simples_rate)

        root.addLayout(self.header_form)

        header_btns = QHBoxLayout()
        save_proj = QPushButton("Salvar Projeto")
        save_proj.setMinimumWidth(130)
        save_proj.clicked.connect(self.save_project)
        report_btn = QPushButton("Gerar Relatório")
        report_btn.setMinimumWidth(130)
        report_btn.clicked.connect(self.open_report)
        header_btns.addWidget(save_proj)
        header_btns.addWidget(report_btn)
        root.addLayout(header_btns)

        # ---- TABELA DE PRODUTOS ----
        root.addWidget(QLabel("Produtos"))
        self.table_prod = QTableWidget()
        self.table_prod.setColumnCount(8)
        self.table_prod.setHorizontalHeaderLabels(["ID","Descrição","Custo (un)","Venda (un)","Qtd","Origem","Destino","Ações"])
        self.table_prod.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch) #type: ignore
        root.addWidget(self.table_prod)

        prod_btns = QHBoxLayout()
        add_prod = QPushButton("Adicionar Produto")
        add_prod.setMinimumWidth(150)
        add_prod.clicked.connect(self.add_product)
        prod_btns.addWidget(add_prod)
        root.addLayout(prod_btns)

        # ---- TABELA DE OUTROS CUSTOS ----
        root.addWidget(QLabel("Outros custos"))
        self.table_cost = QTableWidget()
        self.table_cost.setColumnCount(4)
        self.table_cost.setHorizontalHeaderLabels(["ID","Descrição","Valor","Ações"])
        self.table_cost.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch) #type: ignore
        root.addWidget(self.table_cost)

        cost_btns = QHBoxLayout()
        add_cost = QPushButton("Adicionar Custo")
        add_cost.setMinimumWidth(150)
        add_cost.clicked.connect(self.add_cost)
        cost_btns.addWidget(add_cost)
        root.addLayout(cost_btns)

        self.load_data()

    # ----- Data binding -----
    def load_data(self):
        proj = load_project(self.project_id)
        if not proj:
            QMessageBox.warning(self, "Erro", "Projeto não encontrado.")
            self.reject(); return
        self._project = proj
        # header
        self.project_number.setText(proj['project_number'])
        self.client_name.setText(proj['client_name'])
        self.gross_sale.setValue(float(proj['gross_sale']))
        self.purchase_state.setText(proj['purchase_state'])
        self.sale_state.setText(proj['sale_state'])
        self.simples_rate.setValue(float(proj['simples_rate']))

        # produtos
        self.table_prod.setRowCount(0)
        for i, p in enumerate(proj['products']):
            self.table_prod.insertRow(i)
            self.table_prod.setItem(i, 0, QTableWidgetItem(str(p['id'])))
            self.table_prod.setItem(i, 1, QTableWidgetItem(p['description']))
            self.table_prod.setItem(i, 2, QTableWidgetItem(f"{float(p['purchase_cost']):.2f}"))
            self.table_prod.setItem(i, 3, QTableWidgetItem(f"{float(p['sale_price']):.2f}"))
            self.table_prod.setItem(i, 4, QTableWidgetItem(str(int(p['qty']))))
            self.table_prod.setItem(i, 5, QTableWidgetItem(p['purchase_state'] or ""))
            self.table_prod.setItem(i, 6, QTableWidgetItem(p['sale_state'] or ""))

            edit_btn = QPushButton("Editar")
            edit_btn.setMinimumWidth(70)
            edit_btn.clicked.connect(lambda _, pid=p['id']: self.edit_product(pid))
            del_btn = QPushButton("Excluir")
            del_btn.setMinimumWidth(70)
            del_btn.clicked.connect(lambda _, pid=p['id']: self.delete_product(pid))

            btns = QHBoxLayout()
            btns.setContentsMargins(2,0,2,0)
            btns.setSpacing(8)
            btns.addWidget(edit_btn)
            btns.addWidget(del_btn)
            cell = QWidget()
            cell.setLayout(btns)
            self.table_prod.setCellWidget(i, 7, cell)

        # outros custos
        self.table_cost.setRowCount(0)
        for i, c in enumerate(proj['other_costs']):
            self.table_cost.insertRow(i)
            self.table_cost.setItem(i, 0, QTableWidgetItem(str(c['id'])))
            self.table_cost.setItem(i, 1, QTableWidgetItem(c['description']))
            self.table_cost.setItem(i, 2, QTableWidgetItem(f"{float(c['cost']):.2f}"))

            edit_btn = QPushButton("Editar")
            edit_btn.setMinimumWidth(70)
            edit_btn.clicked.connect(lambda _, cid=c['id']: self.edit_cost(cid))
            del_btn = QPushButton("Excluir")
            del_btn.setMinimumWidth(70)
            del_btn.clicked.connect(lambda _, cid=c['id']: self.delete_cost(cid))

            btns = QHBoxLayout()
            btns.setContentsMargins(2,0,2,0)
            btns.setSpacing(8)
            btns.addWidget(edit_btn)
            btns.addWidget(del_btn)
            cell = QWidget()
            cell.setLayout(btns)
            self.table_cost.setCellWidget(i, 3, cell)

    def save_project(self):
        pn = self.project_number.text().strip()
        cn = self.client_name.text().strip()
        gs = float(self.gross_sale.value())
        pstate = self.purchase_state.text().strip().upper()
        sstate = self.sale_state.text().strip().upper()
        srate = float(self.simples_rate.value() or DEFAULT_SIMPLES_RATE)

        if not pn or not cn:
            QMessageBox.warning(self, "Erro", "Número do projeto e Cliente são obrigatórios.")
            return
        try:
            cur.execute('''UPDATE projects
                           SET project_number=?, client_name=?, gross_sale=?, purchase_state=?, sale_state=?, simples_rate=?
                           WHERE id=?''',
                        (pn, cn, gs, pstate or None, sstate or None, srate, self.project_id))
            conn.commit()
            QMessageBox.information(self, "OK", "Projeto salvo.")
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Erro", "Número de projeto já existe.")

    def add_product(self):
        dlg = ProductDialog(self.project_id, parent=self)
        if dlg.exec():
            self.load_data()

    def edit_product(self, product_id: int):
        cur.execute('SELECT id, description, purchase_cost, sale_price, qty, purchase_state, sale_state FROM products WHERE id=?', (product_id,))
        r = cur.fetchone()
        if not r: return
        prod = dict(id=r[0], description=r[1], purchase_cost=r[2] or 0.0, sale_price=r[3] or 0.0,
                    qty=r[4] or 1, purchase_state=r[5] or '', sale_state=r[6] or '')
        dlg = ProductDialog(self.project_id, product=prod, parent=self)
        if dlg.exec():
            self.load_data()

    def delete_product(self, product_id: int):
        if QMessageBox.question(self, "Confirmar", "Excluir este produto?") == QMessageBox.Yes: #type: ignore
            cur.execute('DELETE FROM products WHERE id=?', (product_id,))
            conn.commit()
            self.load_data()

    def add_cost(self):
        dlg = OtherCostDialog(self.project_id, parent=self)
        if dlg.exec():
            self.load_data()

    def edit_cost(self, cost_id: int):
        cur.execute('SELECT id, description, cost FROM other_costs WHERE id=?', (cost_id,))
        r = cur.fetchone()
        if not r: return
        cost = dict(id=r[0], description=r[1], cost=r[2] or 0.0)
        dlg = OtherCostDialog(self.project_id, cost=cost, parent=self)
        if dlg.exec():
            self.load_data()

    def delete_cost(self, cost_id: int):
        if QMessageBox.question(self, "Confirmar", "Excluir este custo?") == QMessageBox.Yes: #type: ignore
            cur.execute('DELETE FROM other_costs WHERE id=?', (cost_id,))
            conn.commit()
            self.load_data()

    def open_report(self):
        ReportDialog(self.project_id, self).exec()

# ---------------- MAIN WINDOW ----------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Licitacao Cost Calculator - HLX TECH")
        self.resize(1050, 600)

        central = QWidget()
        self.setCentralWidget(central)
        v = QVBoxLayout(central)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["ID","Número","Cliente","Venda Bruta","Origem","Destino","Simples"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch) #type: ignore
        v.addWidget(self.table)

        btns = QHBoxLayout()
        new_btn = QPushButton("Criar Projeto")
        new_btn.setMinimumWidth(130)
        new_btn.clicked.connect(self.create_project)

        open_btn = QPushButton("Abrir/Editar")
        open_btn.setMinimumWidth(130)
        open_btn.clicked.connect(self.open_project_dialog)

        del_btn = QPushButton("Excluir")
        del_btn.setMinimumWidth(100)
        del_btn.clicked.connect(self.delete_project)

        report_btn = QPushButton("Gerar Relatório (seleção ou nº)")
        report_btn.setMinimumWidth(220)
        report_btn.clicked.connect(self.generate_report_main)

        refresh_btn = QPushButton("Atualizar")
        refresh_btn.setMinimumWidth(110)
        refresh_btn.clicked.connect(self.load_projects)

        btns.addWidget(new_btn)
        btns.addWidget(open_btn)
        btns.addWidget(del_btn)
        btns.addWidget(report_btn)
        btns.addWidget(refresh_btn)
        v.addLayout(btns)

        self.load_projects()

        # duplo clique também abre o projeto
        self.table.cellDoubleClicked.connect(lambda r, c: self.open_project_dialog())

    def load_projects(self):
        cur.execute('SELECT id, project_number, client_name, gross_sale, purchase_state, sale_state, simples_rate FROM projects ORDER BY created_at DESC NULLS LAST')
        rows = cur.fetchall()
        self.table.setRowCount(0)
        for i, r in enumerate(rows):
            self.table.insertRow(i)
            for j, val in enumerate(r):
                if j == 3 and val is not None:
                    self.table.setItem(i, j, QTableWidgetItem(f"{float(val):.2f}"))
                elif j == 6 and val is not None:
                    self.table.setItem(i, j, QTableWidgetItem(f"{float(val)*100:.2f}%"))
                else:
                    self.table.setItem(i, j, QTableWidgetItem("" if val is None else str(val)))

    def _current_project_id(self):
        row = self.table.currentRow()
        if row >= 0:
            return int(self.table.item(row, 0).text()) #type: ignore
        return None

    def create_project(self):
        number, ok = QInputDialog.getText(self, "Novo Projeto", "Número do projeto (chave):")
        if not ok or not number.strip():
            return
        client, ok = QInputDialog.getText(self, "Novo Projeto", "Nome do cliente:")
        if not ok or not client.strip():
            return
        now = datetime.now().isoformat()
        try:
            cur.execute('INSERT INTO projects (project_number, client_name, created_at) VALUES (?,?,?)',
                        (number.strip(), client.strip(), now))
            conn.commit()
            self.load_projects()
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Erro", "Número de projeto já existe.")

    def open_project_dialog(self):
        pid = self._current_project_id()
        if pid is None:
            QMessageBox.information(self, "Info", "Selecione um projeto para abrir.")
            return
        ProjectDialog(pid, self).exec()
        self.load_projects()

    def delete_project(self):
        pid = self._current_project_id()
        if pid is None:
            QMessageBox.information(self, "Info", "Selecione um projeto para excluir.")
            return
        if QMessageBox.question(self, "Confirmar", "Excluir este projeto e todos os seus itens?") == QMessageBox.Yes: #type: ignore
            cur.execute('DELETE FROM projects WHERE id=?', (pid,))
            conn.commit()
            self.load_projects()

    def generate_report_main(self):
        # 1) tenta usar seleção
        pid = self._current_project_id()
        if pid is None:
            # 2) pergunta número do projeto
            pnum, ok = QInputDialog.getText(self, "Gerar Relatório", "Número do projeto:")
            if not ok or not pnum.strip():
                return
            cur.execute('SELECT id FROM projects WHERE project_number=?', (pnum.strip(),))
            r = cur.fetchone()
            if not r:
                QMessageBox.warning(self, "Erro", "Projeto não encontrado.")
                return
            pid = r[0]
        ReportDialog(pid, self).exec()


# ---------------- RUN ----------------
if __name__ == "__main__":
    app = QApplication([])
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
