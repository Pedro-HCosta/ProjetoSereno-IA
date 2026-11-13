"""Corpos de entrada e saída dos endpoints (Contrato: base /ia)."""
import re
import unicodedata

from pydantic import BaseModel, Field, field_validator

# diaSemana no padrão do JavaScript (Date.getDay()): 0 = domingo ... 6 = sábado
DIAS = ["domingo", "segunda", "terca", "quarta", "quinta", "sexta", "sabado"]
NOMES_DIAS = ["domingo", "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado"]


def _sem_acento(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


class PrevisaoRequest(BaseModel):
    localId: int = Field(ge=1)
    diaSemana: int | str = Field(description="0 = domingo ... 6 = sábado, ou o nome do dia (ex.: 'SEGUNDA')")
    hora: int | str = Field(description="0 a 23, ou 'HH:MM'")

    @field_validator("diaSemana")
    @classmethod
    def _dia(cls, v):
        if isinstance(v, int) or (isinstance(v, str) and v.strip().isdigit()):
            n = int(v)
            if 0 <= n <= 6:
                return n
            raise ValueError("deve estar entre 0 (domingo) e 6 (sábado)")
        nome = _sem_acento(str(v)).lower().replace("-feira", "").strip()
        if nome in DIAS:
            return DIAS.index(nome)
        raise ValueError("dia da semana inválido (use 0 a 6 ou o nome do dia)")

    @field_validator("hora")
    @classmethod
    def _hora(cls, v):
        if isinstance(v, int):
            n = v
        else:
            m = re.fullmatch(r"\s*(\d{1,2})(?::\d{2})?\s*h?\s*", str(v))
            if not m:
                raise ValueError("hora inválida (use 0 a 23 ou 'HH:MM')")
            n = int(m.group(1))
        if not 0 <= n <= 23:
            raise ValueError("deve estar entre 0 e 23")
        return n


class PrevisaoResponse(BaseModel):
    nivelPrevisto: int = Field(description="Sobrecarga sensorial prevista: 0 = muito calmo, 100 = muito intenso")
    faixa: str = Field(description="TRANQUILO, MODERADO ou AGITADO")
    explicacao: str
    melhorHorario: int | None = Field(description="Hora mais tranquila prevista nesse mesmo dia")
    alertas: list[str]
    geradoPor: str = Field(description="'llm' quando a frase veio do modelo generativo; 'regra' no texto alternativo")


class DireitosRequest(BaseModel):
    situacao: str = Field(min_length=5, max_length=500)
    contexto: str | None = Field(default=None, max_length=300)


class Fonte(BaseModel):
    lei: str
    artigo: str
    trecho: str
    url: str
    relevancia: float


class DireitosResponse(BaseModel):
    resposta: str
    fontes: list[Fonte]
    encontrouBase: bool
    geradoPor: str
    aviso: str = "Esta orientação é informativa e não substitui a de um advogado ou da Defensoria Pública."
