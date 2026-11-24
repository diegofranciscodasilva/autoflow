# AutoFlow

AutoFlow é uma aplicação web local para limpeza de planilhas e organização de arquivos em lote.

## Funcionalidades

- Processamento de arquivos CSV e XLSX de até 10 MB.
- Prévia das oito primeiras linhas antes do download.
- Regras para remover espaços, linhas vazias e duplicados.
- Padronização de maiúsculas e cabeçalhos.
- Preenchimento de campos vazios.
- Organização de vários arquivos em um ZIP por categoria.
- Opção de prefixar nomes pela data e padronizar nomes.
- Relatório de movimentação dentro do ZIP.

## Tecnologias

- Frontend: HTML, CSS e JavaScript.
- Backend: Python, Flask e Flask-Cors.
- Planilhas: pandas e openpyxl.

## Pré-requisitos

- Python 3.10 ou superior.
- Navegador moderno.
- Opcionalmente, um ambiente virtual Python.

## Instalação

No diretório do projeto:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Execução

Em um terminal, inicie o backend:

```powershell
cd backend
python app.py
```

O servidor será iniciado em `http://127.0.0.1:5000`.

Na raiz do projeto, abra `index.html` diretamente no navegador ou sirva a interface com:

```powershell
python -m http.server 8080
```

Depois, acesse `http://localhost:8080`.

## Uso

### Limpeza de planilhas

1. Selecione ou arraste um CSV/XLSX.
2. Opcionalmente, descreva as alterações e use Interpretar.
3. Revise as regras marcadas.
4. Clique em Gerar prévia.
5. Confirme o resultado e baixe em CSV ou XLSX.

### Organização de arquivos

1. Selecione vários arquivos ou arraste-os para a área indicada.
2. Escolha a inclusão da data e/ou a padronização dos nomes.
3. Clique em Organizar e baixar ZIP.
4. Abra o ZIP e consulte `RELATORIO.txt`.

## Estrutura

- `index.html`: interface da aplicação.
- `assets/css/style.css`: estilos e responsividade.
- `assets/js/script.js`: seleção de arquivos, chamadas à API e interface.
- `backend/app.py`: servidor Flask e rotas da API.
- `backend/sheets.py`: leitura, limpeza e exportação de planilhas.
- `backend/files.py`: organização e compactação de arquivos.
- `backend/processor.py` e `backend/filetools.py`: módulos auxiliares de processamento.
- `backend/utils.py`: função compartilhada de padronização de nomes.
- `backend/requirements.txt`: dependências Python.
- `passo-a-passo.txt`: guia detalhado do projeto.
- `versão.txt`: histórico e plano de versões.

## Privacidade

Os arquivos enviados são processados em memória. O projeto não possui banco de dados e não salva os arquivos enviados no servidor.

## Limites

- Planilha: 10 MB.
- Conjunto de arquivos: 15 MB no total.

## 👨‍💻 Autor

### Diego Francisco da Silva

Desenvolvedor Front-End em formação e estudante de Engenharia de Software.

- **[Site Empresa](https://diegofranciscodasilva.github.io/dev-software-web/)**: dev.software.web Site Empresa
- **[LinkedIn](https://www.linkedin.com/in/diego-francisco-da-silva/)**: diego-francisco-da-silva
- **[GitHub](https://github.com/diegofranciscodasilva)**: diegofranciscodasilva
- **[Instagram](https://www.instagram.com/diego_francisco_da_silva/)**: @diego_francisco_da_silva
- **[Instagram](https://www.instagram.com/dev.software.web/)**: @dev.software.web

---

Feito com ❤️ por Diego.
