# Sereno — Serviço de IA (`sereno-ia`)

Global Solution 2026/2 · CitizenTech · FIAP — disciplina **Disruptive Architectures: IoT, IoB & Generative IA**

O Sereno é um app de acessibilidade urbana que avisa, antes de a pessoa sair de casa, se o destino e o caminho são acessíveis para ela. Este repositório é o serviço de IA do app: duas funções que aparecem dentro das telas do Sereno.

## Integrantes

| Nome | RM |
| --- | --- |
| Eduardo Augusto de Oliveira Souza | RM565269 |
| Fellipe Costa de Oliveira | RM564673 |
| Felype Ferreira Maschio | RM563009 |
| Gustavo Vieira de Matos | RM563304 |
| Pedro Henrique dos Santos Costa | RM562156 |

## O problema e quem se beneficia

Uma pessoa autista, com TDAH ou ansiedade pode desistir de ir à UBS ou ao mercado por medo de chegar num momento barulhento, iluminado demais ou lotado. Um cadeirante que encontra o elevador da estação parado muitas vezes não sabe o que a lei garante a ele. O serviço ataca as duas situações:

| Função | Onde aparece no app | Quem ajuda | Técnica |
| --- | --- | --- | --- |
| **Previsão de calma** — como o lugar deve estar num dia e hora, o horário mais tranquilo e uma frase simples explicando | Card na tela de detalhe do lugar | Pessoas com sensibilidade sensorial | Machine Learning (Random Forest) + IA generativa |
| **Quais são meus direitos?** — orientação baseada na lei, citando os artigos | Botão na tela da estação quando há equipamento parado | Pessoas com deficiência, mobilidade reduzida ou autismo | RAG básico (busca vetorial sobre 3 leis) + IA generativa |

Os requisitos pedem IA generativa mais um aprofundamento; aqui há dois (ML e RAG).

## Arquitetura

![Arquitetura do serviço de IA](docs/arquitetura.png)

Fonte do diagrama: [`docs/arquitetura.mmd`](docs/arquitetura.mmd).

1. O usuário faz login na **API Java**, que emite um token JWT (HS256, `iss=sereno-auth`, `aud=sereno-app`). O serviço de IA só **valida** esse token com o mesmo `JWT_SECRET`; não existe login próprio.
2. **Previsão:** o serviço descobre a categoria do lugar (pela API Java ou, se ela não responder, pelo catálogo `ml/dados/locais.json`), o modelo prevê ruído, luz e lotação para todas as horas do dia e o LLM transforma o resultado numa frase simples.
3. **Direitos:** a pergunta vira um vetor, o índice FAISS devolve os 3 trechos de lei mais parecidos e, se forem relevantes o bastante, o LLM responde **só com base neles**, citando lei e artigo.
4. **Se o LLM falhar** (sem chave, fora do ar, tempo esgotado), o serviço continua respondendo com um texto montado por regra (`geradoPor: "regra"`). Se o serviço inteiro cair, o app esconde o card, como combinado no Contrato.

Os erros seguem o mesmo formato das APIs Java e .NET: `{ status, erro, mensagem, campos, timestamp, path }`.

## Funcionalidade 1 — Previsão de calma (ML + IA generativa)

```http
POST /ia/previsao-calma
Authorization: Bearer <token da API Java>

{ "localId": 4, "diaSemana": 6, "hora": 11 }
```

Resposta (exemplo; o número e os alertas são os reais do modelo, a frase varia a cada chamada do LLM):

```json
{
  "nivelPrevisto": 76,
  "faixa": "AGITADO",
  "explicacao": "Sábado às 11h o parque costuma estar cheio e com sol forte. Se puder, vá no fim da tarde, que é bem mais tranquilo.",
  "melhorHorario": 20,
  "alertas": ["Barulho alto previsto nesse horário", "Luz forte prevista nesse horário", "Lugar cheio previsto nesse horário"],
  "geradoPor": "llm"
}
```

- `diaSemana`: 0 = domingo … 6 = sábado (padrão do `Date.getDay()` do JavaScript), ou o nome do dia (`"SEGUNDA"`). `hora`: 0–23 ou `"HH:MM"`.
- `nivelPrevisto`: **sobrecarga sensorial** de 0 (muito calmo) a 100 (muito intenso) — média das notas de ruído, luz e lotação (1 a 5) levada para 0–100. Faixas: `TRANQUILO` (< 40), `MODERADO` (40–69), `AGITADO` (≥ 70).
- `melhorHorario`, `alertas` e `geradoPor` são campos extras; quem consome só o Contrato pode ignorá-los.

### Dados e preparação

| Fonte | O que é | Arquivo |
| --- | --- | --- |
| Conjunto sintético | 6.000 avaliações de 24 lugares (6 do catálogo + 3 extras por categoria), geradas a partir de padrões documentados: UBS cheia logo cedo e às segundas, terminal cheio nos horários de pico, parque cheio no fim de semana e com sol forte ao meio-dia, biblioteca calma de manhã. Semente fixa (2026), então o arquivo sai igual em qualquer máquina. | `ml/gerar_dados.py` → `ml/dados/avaliacoes_sinteticas.csv` |
| Avaliações reais (opcional) | Exportação da tabela `SER_AVALIACAO` do Oracle. Se o arquivo existir, o treino junta ao sintético. | `ml/dados/avaliacoes_oracle.csv` |

Por que sintético: o app ainda não tem volume de avaliações reais. Exportação das avaliações reais, quando houver:

```sql
SELECT a.local_id, l.categoria, TO_CHAR(a.data_hora_visita, 'YYYY-MM-DD HH24:MI') AS data_hora_visita,
       a.ruido, a.luminosidade, a.lotacao
  FROM SER_AVALIACAO a JOIN SER_LOCAL l ON l.id = a.local_id;
```

Preparação: o dia e a hora da visita viram `dia_semana`, `hora` e `fim_de_semana`; a categoria vira 6 colunas 0/1. O lugar específico **não** entra como coluna: o modelo aprende o padrão do tipo de lugar e cada lugar recebe depois um ajuste próprio (soma dos resíduos das avaliações dele dividida por nº de avaliações + 20). Com poucas avaliações o ajuste fica perto de zero, e um lugar recém-cadastrado já tem previsão pela categoria.

### Modelo e justificativa

- **Random Forest** (`scikit-learn`, 200 árvores, folhas com no mínimo 5 avaliações) com **três saídas** — ruído, luz e lotação. Prever as três separadas permite gerar alertas específicos ("luz forte prevista") em vez de só um número.
- Por que Random Forest: captura padrões não lineares (dois picos no dia, diferença entre dia útil e fim de semana) sem precisar desenhar essas curvas à mão, funciona bem com poucos milhares de linhas, treina em 2 segundos e roda em CPU no plano B1 da Azure. Uma rede neural não traria ganho com esse volume de dados e seria mais difícil de explicar.
- Por que LLM só na frase: o número vem do modelo (reprodutível e medido); o LLM recebe apenas os dados já calculados e é instruído a não inventar números nem horários.

### Resultados (`ml/RESULTADOS.md`)

| Cenário | Modelo (MAE / R²) | Média geral (MAE / R²) | Média por categoria e hora (MAE / R²) |
| --- | --- | --- | --- |
| Teste aleatório (20% das avaliações) | **8,21 / 0,749** | 17,23 / 0,00 | 8,82 / 0,711 |
| Lugares novos (nunca vistos) | **8,33 / 0,728** | 17,14 / −0,02 | 8,42 / 0,724 |

MAE em pontos da escala 0–100. O modelo erra metade do que erra a média simples (linha de base pedida) e vence também uma linha de base bem mais forte, a média por categoria, dia útil/fim de semana e hora. A margem sobre essa segunda linha de base é pequena porque as notas têm ruído (pessoas diferentes dão notas diferentes para a mesma situação): pela variação usada na geração dos dados, só esse ruído já impõe um erro mínimo estimado em cerca de 7 pontos. As 5 checagens de bom senso passam (ex.: UBS na segunda às 8h = 72 contra 23 às 16h).

## Funcionalidade 2 — "Quais são meus direitos?" (RAG + IA generativa)

```http
POST /ia/direitos
Authorization: Bearer <token da API Java>

{ "situacao": "O elevador da estação está parado e eu sou cadeirante", "contexto": "Estação Sé" }
```

Resposta (exemplo ilustrativo do formato):

```json
{
  "resposta": "As estações de transporte coletivo precisam ser acessíveis a todas as pessoas (Lei 13.146/2015, art. 48) ...",
  "fontes": [{ "lei": "Lei 13.146/2015", "artigo": "art. 48", "trecho": "Os veículos de transporte coletivo ...", "url": "https://www.planalto.gov.br/...", "relevancia": 0.27 }],
  "encontrouBase": true,
  "geradoPor": "llm",
  "aviso": "Esta orientação é informativa e não substitui a de um advogado ou da Defensoria Pública."
}
```

### Fontes e preparação dos dados

| Lei | Assunto | Texto oficial |
| --- | --- | --- |
| Lei 13.146/2015 | Lei Brasileira de Inclusão | [planalto.gov.br](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/lei/l13146.htm) |
| Lei 10.098/2000 | Acessibilidade | [planalto.gov.br](https://www.planalto.gov.br/ccivil_03/leis/l10098.htm) |
| Lei 12.764/2012 | Pessoa com transtorno do espectro autista | [planalto.gov.br](https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2012/lei/l12764.htm) |

`rag/indexar.py` lê as páginas salvas em `rag/leis/`, remove o texto **riscado** (no site do Planalto, riscado = revogado) e as notas de alteração ("Incluído pela Lei…"), corta a assinatura e divide o texto **por artigo**. O nome do capítulo de cada artigo (ex.: "CAPÍTULO X — DO DIREITO AO TRANSPORTE E À MOBILIDADE") entra como contexto do trecho, o que ajuda a busca. Artigos com mais de 1.500 caracteres viram mais de um trecho, sempre com o número do artigo.

### Busca, recusa e geração

- **Embeddings locais:** TF-IDF de palavras e de pedaços de 3 a 5 letras (para "elevador" casar com "elevadores"), reduzido com SVD a até 256 dimensões (LSA). Índice **FAISS** com similaridade de cosseno. Justificativa: roda sem GPU e sem baixar modelos de centenas de MB, não manda o texto para uma API externa e dá sempre o mesmo resultado; para 3 leis com vocabulário jurídico fixo, isso basta. A limitação (pouco entendimento de sinônimos) é compensada por uma pequena tabela que traduz a linguagem do dia a dia para os termos da lei ("cadeirante" → "pessoa com deficiência… mobilidade reduzida", "metrô" → "transporte coletivo… estações").
- **Recusa em duas barreiras:** (1) se o trecho mais parecido tiver relevância abaixo de **0,13**, o serviço responde que não encontrou base, sem nem chamar o LLM; (2) se os trechos não respondem à pergunta, o LLM é instruído a devolver `NAO_SEI`, que vira a mesma resposta de recusa.
- **Geração:** o LLM recebe a pergunta e os 3 trechos numerados, com regras explícitas: responder só com base neles, citar `(Lei, art.)` em cada afirmação, linguagem simples e nada de inventar prazos, valores ou órgãos.

### Resultados (`rag/RESULTADOS.md`)

Índice: 198 trechos (Lei 13.146: 127 artigos · Lei 10.098: 30 · Lei 12.764: 8; artigos vetados ficam de fora).

| Conjunto | Acerto top-3 | Acerto top-1 | Perguntas no tema respondidas | Perguntas fora do tema recusadas |
| --- | --- | --- | --- | --- |
| Desenvolvimento (15 no tema + 5 fora) | 15/15 | 9/15 | 15/15 | 5/5 |
| Validação (6 no tema + 2 fora) | **5/6** | 3/6 | 4/6 | 1/2 |
| Fluxo principal do app (4 jeitos de perguntar sobre elevador/escada parados na estação) | **4/4** | — | 4/4 | — |

Acerto top-3 = o artigo esperado está entre os 3 trechos que vão para o LLM. Como ler esses números:

- **Desenvolvimento (otimista):** foi olhando os erros deste conjunto que a tabela de sinônimos e o limiar foram ajustados. Na primeira rodada o acerto top-3 era 12/15: errava perguntas de definição ("o que a lei considera…") e a palavra "prédio", que nas leis aparece como "edificação".
- **Validação (mais honesta):** 6 perguntas escritas depois desses ajustes. Erro de verdade: a do hotel. A pergunta fala em "quartos", e o art. 45 da Lei 13.146 fala em "dormitórios"; é o limite de uma busca por palavras. Na pergunta do cinema, o art. 12 da Lei 10.098 (espaços para cadeira de rodas em locais de espetáculos) veio em 2º lugar e também responde; o gabarito, que só tinha o art. 44 da Lei 13.146, foi corrigido e a correção está anotada em `perguntas.json`.
- **Fluxo principal:** depois da validação, testando a pergunta da demonstração, apareceu um problema: "elevador da estação parado, sou cadeirante" trazia em 1º o artigo sobre empréstimo de cadeiras de rodas em shoppings. A expansão de "cadeirante" incluía "cadeira de rodas", e "elevador" repetia a própria palavra (que aparece nos artigos sobre elevadores em prédios). As duas expansões foram corrigidas, o que não mudou nenhum resultado do desenvolvimento nem da validação, e as 4 perguntas do fluxo viraram teste de regressão.
- **Limiar 0,13:** separa as perguntas fora do tema (nota máxima 0,128) das no tema (mínima 0,135) no desenvolvimento. A margem é pequena, e a validação mostra os dois lados disso: a pergunta da faculdade achou o artigo certo, mas com nota 0,09, abaixo do limiar, e seria recusada; "quanto custa uma passagem de avião" passou do limiar por causa da palavra "aéreo" no art. 48 e depende da segunda barreira (o LLM responder `NAO_SEI`).
- **Próximos passos:** embeddings neurais multilíngues (entendem que "quartos" e "dormitórios" são parecidos) se o servidor comportar, e um conjunto de validação maior.

Tabelas pergunta a pergunta e varredura de limiares: [`rag/RESULTADOS.md`](rag/RESULTADOS.md). Com a chave do LLM, `python -m rag.avaliar --com-llm` grava as respostas completas em `rag/avaliacao/respostas_llm.md` e conta quantas citam artigo.

## Modelos e tecnologias

| Peça | Escolha | Por quê |
| --- | --- | --- |
| API | FastAPI + Uvicorn/Gunicorn | Validação automática dos dados, Swagger em `/ia/docs`, leve para o plano B1 |
| Autenticação | PyJWT (HS256) | Mesmo token da API Java, sem login duplicado |
| Previsão | scikit-learn `RandomForestRegressor` | Ver justificativa acima |
| RAG | TF-IDF + SVD (scikit-learn) e FAISS | Ver justificativa acima |
| LLM | Google Gemini (`gemini-2.5-flash`) por API compatível com OpenAI | Plano gratuito para estudantes; trocar para Groq ou OpenAI é só mudar `AI_BASE_URL` e `AI_MODEL` |

## Como executar

Requisitos: Python 3.12+.

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                                    # preencha JWT_SECRET e AI_API_KEY

python -m ml.gerar_dados        # dados sintéticos (o CSV já vem no repositório)
python -m ml.treinar            # treina e grava ml/modelo/ e ml/RESULTADOS.md
python -m rag.indexar           # lê rag/leis/ e grava rag/indice/
python -m rag.avaliar           # 15 + 6 + 4 perguntas → rag/RESULTADOS.md (com --com-llm grava as respostas completas)

uvicorn app.main:app --reload --port 8000
```

Swagger: <http://localhost:8000/ia/docs>. Para testar sem a API Java, gere um token de desenvolvimento:

```bash
python -c "import jwt,time,os;from dotenv import load_dotenv;load_dotenv();t=int(time.time());print(jwt.encode({'sub':'1','email':'cidadao@sereno.app','role':'CIDADAO','iss':'sereno-auth','aud':'sereno-app','iat':t,'exp':t+7200},os.environ['JWT_SECRET'],algorithm='HS256'))"
```

## Testes

```bash
pytest -q
```

36 testes automatizados, todos sem rede e sem LLM de verdade (o LLM é simulado):

- **Autenticação e erros:** sem token, token expirado, outro segredo e outro emissor dão 401 no formato padrão; dados inválidos dão 400 com o campo.
- **Previsão:** formato do Contrato, UBS cheia cedo e vazia à tarde, melhor horário dentro do funcionamento, alerta fora do horário, dia e hora em formatos diferentes, local inexistente (404), LLM fora do ar (texto alternativo).
- **RAG:** divisão por artigo, remoção de texto revogado e notas, capítulos como contexto, busca, recusa fora do tema sem chamar o LLM, `NAO_SEI` do LLM, índice ausente (503).
- **Regressão com as leis reais:** as 4 perguntas do fluxo principal trazem o art. 46 ou 48 da Lei 13.146, e perguntas fora do tema são recusadas.

## Deploy na Azure

Web App Python (Linux), criado pelo script de infraestrutura do projeto (`sereno-ia-rm562156`).

- **Comando de inicialização:** `gunicorn -w 2 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 app.main:app`
- **Configurações do aplicativo:** `JWT_SECRET`, `AI_API_KEY`, `AI_BASE_URL`, `AI_MODEL`, `JAVA_API_URL`, `SCM_DO_BUILD_DURING_DEPLOYMENT=true`
- O modelo treinado (`ml/modelo/`) e o índice (`rag/indice/`) vão no repositório; o servidor não precisa treinar nada ao subir.

## Uso responsável e limitações

- **Credenciais:** nenhum segredo no código. `JWT_SECRET` e `AI_API_KEY` vêm de variáveis de ambiente; `.env` está no `.gitignore`.
- **Dados pessoais:** o serviço não guarda nada. Ao LLM vão só os dados calculados (lugar, dia, hora, nível) ou a pergunta e os trechos de lei — nunca o e-mail ou o id do usuário. Recomenda-se não escrever dados pessoais no campo da pergunta.
- **Dados sintéticos:** a previsão hoje reflete os padrões supostos em `ml/gerar_dados.py`, não medições reais. Ela melhora quando entram avaliações reais do Oracle.
- **Não é orientação jurídica:** a resposta de direitos traz sempre o aviso e os links das fontes oficiais; a base cobre só 3 leis federais (sem leis estaduais, municipais ou normas técnicas como a ABNT NBR 9050).
- **Busca por palavras:** perguntas com vocabulário muito diferente do da lei podem não achar o artigo certo (acerto top-3 de 5/6 na validação; falhou em "quartos" × "dormitórios"). A tabela de sinônimos ajuda, mas, mal calibrada, pode abafar o assunto principal da pergunta, como aconteceu com "cadeirante" no fluxo principal antes da correção.
- **LLM:** pode errar mesmo com os trechos certos. Por isso cada resposta vem com as fontes para conferência, e a temperatura é baixa (0,1 no RAG).
- **Horário de funcionamento:** é típico por categoria, não do lugar exato; horários fora dele geram um alerta para confirmar antes de ir.

## Estrutura do repositório

```
app/          serviço FastAPI (rotas, JWT, erros, previsão, RAG, cliente do LLM)
ml/           gerar_dados.py, treinar.py, dados/, modelo/, RESULTADOS.md
rag/          leis/ (textos oficiais), indexar.py, avaliar.py, indice/, avaliacao/, RESULTADOS.md
tests/        pytest (36 testes) e uma lei fictícia de teste
docs/         diagrama da arquitetura
```
