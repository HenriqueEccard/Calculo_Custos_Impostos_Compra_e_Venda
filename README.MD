# 📊 Calculadora de Custos para Licitações

Este projeto é uma ferramenta desenvolvida em **Python** para auxiliar no **gerenciamento de custos de compra e venda**, especialmente em cenários de **licitações públicas ou privadas**.  
O programa permite organizar, calcular e gerar relatórios sobre custos, valores de venda e margens de lucro, de forma prática e automatizada.
Considera compra e venda em diversos estados já considerando diferenças de ICMS Difal de entrada, saída e outros impostos.
Exemplo: Compro a mercadoria em Belo Horizonte e vendo em SP ou compro em MG e vendo no mesmo estado... e assim por diante. 
O programa já realiza os Cálculos de impostos para composição do custo para evitar erros de margem.

Ainda está em fase de acabamento do Layout. Quando finalizar faço as alterações aqui, no entanto já funciona bem para quem prioriza apenas a necessidade de composição do custo. 

---

## ⚙️ Funcionalidades

- Cadastro de produtos/serviços com custos associados.
- Definição de preços de venda.
- Cálculo automático de:
  - Custo total
  - Valor de venda bruto
  - Lucro estimado
- Geração de relatórios organizados em formato **JSON**.
- Persistência dos dados em um banco de dados **SQLite**.
- Interface desenvolvida com **PySide6** (Python + Qt).

---

## 🗂 Estrutura do Projeto

GERENCIAMENTO_CUSTOS_COMPRA_VENDA/
│
├── main.py # Arquivo principal para rodar o programa
├── licitacao.db # Banco de dados SQLite com as informações salvas
├── reports/ # Pasta onde ficam os relatórios gerados em JSON
│ └── exemplo.json
└── README.md # Este arquivo

yaml
Copy code

---

## 🚀 Como Executar

### 1. Requisitos
- Python **3.11+**
- Bibliotecas:
  - `PySide6`
  - `sqlite3` (já vem com Python)
  - `json` (já vem com Python)

Instale as dependências com:
```bash
pip install PySide6
2. Rodar o programa
No terminal, dentro da pasta do projeto:

bash
Copy code
python main.py
3. Gerar Executável (opcional)
É possível gerar um .exe com o PyInstaller:

bash
Copy code
pyinstaller --onefile --noconsole main.py
O executável será criado na pasta dist/.

📑 Relatórios
Os relatórios são gerados automaticamente na pasta reports/ em formato JSON, contendo informações de custos, preços de venda e lucros.

Exemplo de relatório (exemplo.json):

json
Copy code
{
  "produto": "Cabo de rede",
  "custo_unitario": 2.50,
  "quantidade": 100,
  "custo_total": 250.00,
  "preco_venda": 400.00,
  "lucro": 150.00
}
🎯 Objetivo
Este projeto foi criado para simplificar a rotina de empresas que participam de processos de compra e licitação, fornecendo uma visão clara de custos e margens de lucro, de forma rápida e intuitiva.

👨‍💻 Autor
Henrique Thadeu Eccard de Souza Leite
Empresa: HLX TECH
📍 Belo Horizonte - MG