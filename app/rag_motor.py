"""Motor do RAG: divide as leis por artigo, gera embeddings e busca no índice vetorial (FAISS).

Embeddings: vetores densos calculados localmente (TF-IDF de palavras e de pedaços de palavras,
reduzido com SVD — a técnica conhecida como LSA). Por que não um modelo neural de embeddings:
- roda sem GPU e sem baixar modelos de centenas de MB (cabe no plano B1 da Azure);
- não envia o texto para nenhuma API externa e dá sempre o mesmo resultado;
- para um corpus pequeno e de vocabulário jurídico fixo (3 leis, ~250 trechos), funciona bem.
Limitação: entende pouco de sinônimos; por isso a consulta passa por expandir_consulta().
"""
import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path

import faiss
import joblib
import numpy as np
from bs4 import BeautifulSoup
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import make_union
from sklearn.preprocessing import Normalizer

LEIS = {
    "13146": {"lei": "Lei 13.146/2015", "nome": "Lei Brasileira de Inclusão da Pessoa com Deficiência",
              "url": "https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/lei/l13146.htm"},
    "10098": {"lei": "Lei 10.098/2000", "nome": "Lei de Acessibilidade",
              "url": "https://www.planalto.gov.br/ccivil_03/leis/l10098.htm"},
    "12764": {"lei": "Lei 12.764/2012", "nome": "Política Nacional de Proteção dos Direitos da Pessoa com Transtorno do Espectro Autista",
              "url": "https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2012/lei/l12764.htm"},
}

MAX_CARACTERES = 1500  # artigos maiores viram mais de um trecho, sempre com o número do artigo


@dataclass
class Trecho:
    id: int
    lei: str
    artigo: str
    capitulo: str
    texto: str
    url: str


# ---------------------------------------------------------------- leitura e divisão por artigo

_NOTAS = re.compile(
    r"\((?:Incluíd[oa]|Redação dada|Vide|Vigência|Revogad[oa]|Regu?lamento|Promulga|Produção de efeito|Renumerad)[^()]*(?:\([^()]*\)[^()]*)*\)",
    re.IGNORECASE,
)
_ARTIGO = re.compile(r"^Art\.\s*(\d+)\s*[º°o]?\s*(?:-\s*([A-Z]))?\s*[.\-–]?\s*", re.MULTILINE)
_TITULO = re.compile(r"^(LIVRO|TÍTULO|CAPÍTULO|Seção|SEÇÃO)\b.*$", re.MULTILINE)


def texto_da_lei(caminho: Path) -> str:
    bruto = caminho.read_bytes()
    if caminho.suffix.lower() in (".htm", ".html"):
        sopa = BeautifulSoup(bruto, "html.parser")
        for tag in sopa(["script", "style", "strike", "s", "del"]):  # no Planalto, texto riscado = revogado
            tag.decompose()
        texto = sopa.get_text("\n")
    else:
        texto = bruto.decode("utf-8", errors="replace")
    texto = texto.replace("\xa0", " ")
    texto = _NOTAS.sub("", texto)
    texto = re.sub(r"((?:Art\.|§)\s*\d{1,2})\s+o\b", r"\1º", texto)  # "Art. 7 o" → "Art. 7º"
    linhas = [re.sub(r"[ \t]+", " ", l).strip() for l in texto.splitlines()]
    linhas = [_NOTAS.sub("", l).strip() for l in _refluir([l for l in linhas if l])]  # notas que estavam quebradas em 2 linhas
    return "\n".join(l for l in linhas if l)


_INICIO = re.compile(r"^(Art\.\s*\d|§|Parágrafo único|[IVXLC]+\s*[-–—]|[IVXLC]+$|[a-z]\)|Brasília,)")
_PALAVRA_TITULO = re.compile(r"^(LIVRO|TÍTULO|CAPÍTULO|Seção|SEÇÃO)\b")


def _refluir(linhas: list[str]) -> list[str]:
    """O HTML do Planalto quebra linhas no meio da frase (e em volta de palavras em itálico).

    Junta cada linha à anterior, a não ser que ela comece uma unidade nova: artigo, parágrafo,
    inciso, alínea, título de capítulo/seção ou o nome do capítulo logo abaixo do título.
    """
    saida: list[str] = []
    anterior = ""  # "titulo" | "nome" | ""
    for l in linhas:
        if _PALAVRA_TITULO.match(l):
            saida.append(l)
            anterior = "titulo"
        elif _INICIO.match(l) or not saida:
            saida.append(l)
            anterior = ""
        elif anterior == "titulo":  # nome do capítulo
            saida.append(l)
            anterior = "nome"
        elif anterior == "nome" and l.isupper():  # nome do capítulo quebrado em duas linhas
            saida[-1] += " " + l
        else:
            saida[-1] += ("" if saida[-1].endswith(("-", "–")) and saida[-1][-2:-1].isalpha() else " ") + l
            anterior = "" if anterior != "nome" else anterior
    return saida


def identificar_lei(caminho: Path, texto: str) -> dict:
    for numero, meta in LEIS.items():
        if numero in caminho.name.replace(".", "") or numero in texto[:3000].replace(".", ""):
            return meta
    raise ValueError(f"Não reconheci a lei do arquivo {caminho.name} (esperado 13146, 10098 ou 12764 no nome)")


def _eh_nome_de_titulo(linha: str) -> bool:
    """Linha logo abaixo de 'CAPÍTULO X' com o nome dele (ex.: 'DO DIREITO AO TRANSPORTE')."""
    return (
        len(linha) <= 120
        and not _ARTIGO.match(linha)
        and not re.match(r"^(§|[IVXLC]+\s*[-–]|[a-z]\))", linha)
        and not linha.endswith((".", ";", ":", ","))
    )


def dividir_por_artigo(texto: str, meta: dict) -> list[dict]:
    linhas = texto.split("\n")
    comeco = next((i for i, l in enumerate(linhas) if _ARTIGO.match(l)), None)
    if comeco is None:
        return []
    linhas = linhas[comeco:]
    fim = next((i for i, l in enumerate(linhas) if re.match(r"^Brasília,\s*\d", l)), len(linhas))
    linhas = linhas[:fim]  # corta a assinatura no final da lei

    trechos, capitulo, artigo, corpo = [], "", None, []

    def fechar():
        sem_rotulo = _ARTIGO.sub("", "\n".join(corpo), count=1).strip()
        if artigo and corpo and sem_rotulo not in ("", "(VETADO)", "(VETADO).", "(Revogado)"):  # artigo vetado não informa nada
            for parte in _quebrar("\n".join(corpo)):
                trechos.append({"lei": meta["lei"], "artigo": artigo[0], "capitulo": artigo[1], "texto": parte, "url": meta["url"]})

    i = 0
    while i < len(linhas):
        linha = linhas[i]
        if _TITULO.match(linha):  # título de capítulo/seção: vira contexto, não texto do artigo
            titulo = linha
            if i + 1 < len(linhas) and _eh_nome_de_titulo(linhas[i + 1]):
                titulo += " — " + linhas[i + 1]
                i += 1
            if linha.upper().startswith(("LIVRO", "TÍTULO", "CAPÍTULO")):
                capitulo = titulo
            else:  # seção fica dentro do capítulo
                capitulo = capitulo.split(" | ")[0] + " | " + titulo if capitulo else titulo
            i += 1
            continue
        m = _ARTIGO.match(linha)
        if m:
            fechar()
            n = int(m.group(1))
            artigo = (f"art. {n}{'º' if n < 10 else ''}{'-' + m.group(2) if m.group(2) else ''}", capitulo)
            corpo = [linha]
        elif artigo:
            corpo.append(linha)
        i += 1
    fechar()
    return trechos


def _quebrar(corpo: str) -> list[str]:
    if len(corpo) <= MAX_CARACTERES:
        return [corpo]
    cabeca = corpo.split("\n", 1)[0][:60]
    partes, atual = [], ""
    for linha in corpo.split("\n"):
        if atual and len(atual) + len(linha) > MAX_CARACTERES:
            partes.append(atual.strip())
            atual = f"{cabeca} (continuação)\n"
        atual += linha + "\n"
    partes.append(atual.strip())
    return partes


# ---------------------------------------------------------------- embeddings e índice

def _normalizar(t: str) -> str:
    t = unicodedata.normalize("NFD", t.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _texto_indexado(t: dict) -> str:
    return f"{t['capitulo']}\n{t['texto']}"


# Linguagem do dia a dia → termos usados nas leis (preparação da consulta)
SINONIMOS = {
    # "cadeira de rodas" fica de fora: puxava artigos sobre empréstimo de cadeiras em shoppings
    "cadeirante": "pessoa com deficiência mobilidade reduzida",
    "cadeira de rodas": "pessoa com deficiência mobilidade reduzida",
    # "elevador" NÃO é expandido: repetir a palavra puxava os artigos sobre elevadores em prédios,
    # e o direito central do app (estação acessível) está no capítulo de transporte e mobilidade
    "metro": "transporte coletivo estações terminais mobilidade",
    "metrô": "transporte coletivo estações terminais mobilidade",
    "trem": "transporte coletivo estações terminais mobilidade",
    "onibus": "transporte coletivo veículos",
    "ônibus": "transporte coletivo veículos",
    "estacao": "transporte coletivo estações terminais mobilidade",
    "estação": "transporte coletivo estações terminais mobilidade",
    "autista": "pessoa com transtorno do espectro autista",
    "autismo": "transtorno do espectro autista",
    "tea": "transtorno do espectro autista",
    "fila": "atendimento prioritário",
    "prioridade": "atendimento prioritário",
    "idoso": "pessoa com mobilidade reduzida",
    "carrinho de bebê": "pessoa com mobilidade reduzida",
    "rampa": "rampa acessibilidade",
    "vaga": "vagas estacionamento reservadas",
    "estacionamento": "vagas estacionamento reservadas",
    "escola": "educação matrícula ensino",
    "matricula": "matrícula ensino",
    "matrícula": "matrícula ensino",
    "discrimina": "discriminação",
    "barulho": "barreiras",
    "posto de saude": "saúde atendimento",
    # perguntas de definição → como as leis escrevem definições
    "o que e": "considera-se consideram-se definições para fins de aplicação desta lei",
    "o que é": "considera-se consideram-se definições para fins de aplicação desta lei",
    "considera": "considera-se consideram-se definições",
    "significa": "considera-se consideram-se definições",
    "definição": "considera-se consideram-se definições",
    "predio": "edifícios edificações uso coletivo",
    "prédio": "edifícios edificações uso coletivo",
    "obrigado a ser acessível": "devem garantir acessibilidade",
    "ubs": "saúde atendimento",
    "hospital": "saúde atendimento",
}


def expandir_consulta(consulta: str) -> str:
    base = consulta.lower()
    extras = [v for k, v in SINONIMOS.items() if re.search(rf"\b{re.escape(k)}\b", base)]
    return consulta + " " + " ".join(extras)


class Vetorizador:
    """TF-IDF (palavras + pedaços de palavras) → SVD → vetor denso de até 256 dimensões."""

    def __init__(self, n_trechos: int):
        self.tfidf = make_union(
            TfidfVectorizer(preprocessor=_normalizar, analyzer="word", ngram_range=(1, 2), sublinear_tf=True),
            TfidfVectorizer(preprocessor=_normalizar, analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, min_df=2),
        )
        self.svd = TruncatedSVD(n_components=min(256, max(2, n_trechos - 1)), random_state=0)

    def treinar(self, textos: list[str]) -> np.ndarray:
        reduzidos = self.svd.fit_transform(self.tfidf.fit_transform(textos))
        return Normalizer().transform(reduzidos).astype("float32")

    def consulta(self, texto: str) -> np.ndarray:
        """Divide pela norma ORIGINAL da consulta, não pela norma depois da projeção.

        Assim o produto interno com um trecho é o cosseno de verdade: uma pergunta sem relação
        com as leis tem pouca "massa" no espaço das leis e recebe nota baixa, em vez de ser
        esticada até parecer parecida.
        """
        x = self.tfidf.transform([texto])
        norma = float(np.sqrt(x.multiply(x).sum()))
        if norma == 0:
            return np.zeros((1, self.svd.n_components), dtype="float32")
        return (self.svd.transform(x) / norma).astype("float32")


def construir_indice(trechos: list[dict], destino: Path) -> int:
    destino.mkdir(parents=True, exist_ok=True)
    itens = [Trecho(id=i, **t) for i, t in enumerate(trechos)]
    vetorizador = Vetorizador(len(itens))
    vetores = vetorizador.treinar([_texto_indexado(asdict(t)) for t in itens])
    indice = faiss.IndexFlatIP(vetores.shape[1])  # produto interno = cosseno (trechos normalizados)
    indice.add(vetores)
    faiss.write_index(indice, str(destino / "leis.faiss"))
    joblib.dump(vetorizador, destino / "vetorizador.joblib", compress=3)
    (destino / "trechos.json").write_text(json.dumps([asdict(t) for t in itens], ensure_ascii=False, indent=1), encoding="utf-8")
    return len(itens)


class Buscador:
    def __init__(self, pasta: Path):
        self.indice = faiss.read_index(str(pasta / "leis.faiss"))
        self.vetorizador = joblib.load(pasta / "vetorizador.joblib")
        self.trechos = json.loads((pasta / "trechos.json").read_text(encoding="utf-8"))

    def buscar(self, consulta: str, k: int = 3) -> list[tuple[dict, float]]:
        v = self.vetorizador.consulta(expandir_consulta(consulta))
        if not np.any(v):
            return []
        notas, ids = self.indice.search(v, k)
        return [(self.trechos[i], float(s)) for i, s in zip(ids[0], notas[0]) if i >= 0]
