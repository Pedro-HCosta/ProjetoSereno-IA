"""Avaliação do RAG.

Dois conjuntos de perguntas (rag/avaliacao/perguntas.json):
- desenvolvimento: 15 perguntas no tema + 5 fora do tema. Foi olhando os erros DESTE conjunto
  que a tabela de sinônimos e o limiar foram ajustados — por isso o resultado aqui é otimista;
- validação: 6 perguntas no tema + 2 fora do tema escritas depois dos ajustes e rodadas uma vez,
  sem mexer em nada. É o número mais honesto.

Métricas: acerto top-3 (um artigo esperado entre os 3 trechos devolvidos) e recusa fora do tema
(nota do 1º trecho abaixo do limiar). Com --com-llm (precisa de AI_API_KEY) grava as respostas
completas em rag/avaliacao/respostas_llm.md e confere se cada uma cita um artigo.

Uso: python -m rag.avaliar [--com-llm]
"""
import json
import re
import sys
from pathlib import Path

from app import direitos
from app.config import carregar
from app.rag_motor import Buscador

RAIZ = Path(__file__).resolve().parent


def avaliar_no_tema(buscador, perguntas):
    saida = []
    for q in perguntas:
        consulta = f"{q['pergunta']}. {q['contexto']}" if q.get("contexto") else q["pergunta"]  # igual ao endpoint
        achados = buscador.buscar(consulta, 3)
        esperados = {tuple(e) for e in q["esperado"]}
        top = [(t["lei"], t["artigo"]) for t, _ in achados]
        posicao = next((i + 1 for i, a in enumerate(top) if a in esperados), None)
        saida.append({"id": q["id"], "pergunta": q["pergunta"], "top3": top, "nota_top1": round(achados[0][1], 3),
                      "acertou": posicao is not None, "posicao": posicao, "esperado": q["esperado"]})
    return saida


def avaliar_fora(buscador, perguntas):
    saida = []
    for q in perguntas:
        achados = buscador.buscar(q["pergunta"], 1)
        saida.append({"id": q["id"], "pergunta": q["pergunta"], "nota_top1": round(achados[0][1], 3) if achados else 0.0})
    return saida


def resumo(no_tema, fora, limiar):
    return {
        "acerto_top3": f"{sum(r['acertou'] for r in no_tema)}/{len(no_tema)}",
        "acerto_top1": f"{sum(r['posicao'] == 1 for r in no_tema)}/{len(no_tema)}",
        "respondidas_no_tema": f"{sum(r['nota_top1'] >= limiar for r in no_tema)}/{len(no_tema)}",
        "recusadas_fora_do_tema": f"{sum(r['nota_top1'] < limiar for r in fora)}/{len(fora)}",
    }


def main(com_llm: bool = False):
    dados = json.loads((RAIZ / "avaliacao" / "perguntas.json").read_text(encoding="utf-8"))
    buscador = Buscador(carregar().caminho_indice)
    limiar = direitos.LIMIAR_RELEVANCIA

    dev_tema, dev_fora = avaliar_no_tema(buscador, dados["no_tema"]), avaliar_fora(buscador, dados["fora_do_tema"])
    val_tema, val_fora = avaliar_no_tema(buscador, dados["validacao_no_tema"]), avaliar_fora(buscador, dados["validacao_fora_do_tema"])
    fluxo = avaliar_no_tema(buscador, dados["fluxo_principal"])
    varredura = [{
        "limiar": l,
        "respondidas_no_tema": sum(r["nota_top1"] >= l for r in dev_tema),
        "recusadas_fora_do_tema": sum(r["nota_top1"] < l for r in dev_fora),
    } for l in [0.10, 0.12, 0.13, 0.15, 0.20, 0.25]]

    resultado = {
        "limiar_em_uso": limiar,
        "desenvolvimento": resumo(dev_tema, dev_fora, limiar),
        "validacao": resumo(val_tema, val_fora, limiar),
        "fluxo_principal": {"acerto_top3": f"{sum(r['acertou'] for r in fluxo)}/{len(fluxo)}"},
        "varredura_de_limiar": varredura,
        "detalhe": {"desenvolvimento": {"no_tema": dev_tema, "fora": dev_fora}, "validacao": {"no_tema": val_tema, "fora": val_fora}, "fluxo_principal": fluxo},
    }
    (RAIZ / "avaliacao" / "resultados.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    escrever_md(resultado)
    print(json.dumps({k: v for k, v in resultado.items() if k != "detalhe"}, ensure_ascii=False, indent=2))
    for r in dev_tema + val_tema + fluxo:
        if not r["acertou"]:
            print(f"ERROU #{r['id']}: esperado {r['esperado']} | veio {r['top3']}")

    if com_llm:
        avaliar_llm(dados)


def _curto(pares):
    return "; ".join(f"{a} ({b.replace('Lei ', '').split('/')[0]})" for b, a in pares)


def _tabela(no_tema, fora, limiar):
    l = ["| # | Pergunta | Artigo esperado | 3 primeiros trechos | Nota do 1º | Acertou |", "| --- | --- | --- | --- | --- | --- |"]
    for q in no_tema:
        ok = f"sim ({q['posicao']}º)" if q["acertou"] else "não"
        l.append(f"| {q['id']} | {q['pergunta']} | {_curto(q['esperado'])} | {_curto(q['top3'])} | {q['nota_top1']} | {ok} |")
    l += ["", "| # | Pergunta fora do tema | Nota do 1º trecho | Recusada |", "| --- | --- | --- | --- |"]
    for q in fora:
        l.append(f"| {q['id']} | {q['pergunta']} | {q['nota_top1']} | {'sim' if q['nota_top1'] < limiar else 'não'} |")
    return l


def escrever_md(r):
    d, v, lim = r["desenvolvimento"], r["validacao"], r["limiar_em_uso"]
    l = ["# Avaliação do RAG (direitos de acessibilidade)", "",
         "Gerado por `python -m rag.avaliar`. Perguntas em `rag/avaliacao/perguntas.json`. Índice: 3 leis divididas por artigo.", "",
         "| Conjunto | Acerto top-3 | Acerto top-1 | Respondidas (no tema) | Recusadas (fora do tema) |",
         "| --- | --- | --- | --- | --- |",
         f"| Desenvolvimento (usado para ajustar) | {d['acerto_top3']} | {d['acerto_top1']} | {d['respondidas_no_tema']} | {d['recusadas_fora_do_tema']} |",
         f"| Validação (escrita depois dos ajustes) | {v['acerto_top3']} | {v['acerto_top1']} | {v['respondidas_no_tema']} | {v['recusadas_fora_do_tema']} |",
         f"| Fluxo principal do app (elevador/escada parados na estação) | {r['fluxo_principal']['acerto_top3']} | — | — | — |",
         "",
         f"Limiar de relevância em uso: **{lim}** (abaixo dele o serviço responde que não encontrou base, sem chamar o LLM).",
         "",
         "## Desenvolvimento", ""] + _tabela(r["detalhe"]["desenvolvimento"]["no_tema"], r["detalhe"]["desenvolvimento"]["fora"], lim)
    l += ["", "## Validação", ""] + _tabela(r["detalhe"]["validacao"]["no_tema"], r["detalhe"]["validacao"]["fora"], lim)
    l += ["", "## Fluxo principal do app", "", "Botão \"Quais são meus direitos?\" na estação: o esperado é o art. 46 ou o art. 48 da Lei 13.146/2015.", "",
          "| # | Pergunta (+ contexto) | 3 primeiros trechos | Acertou |", "| --- | --- | --- | --- |"]
    for q in r["detalhe"]["fluxo_principal"]:
        l.append(f"| {q['id']} | {q['pergunta']} | {_curto(q['top3'])} | {'sim' if q['acertou'] else 'não'} |")
    l += ["", "## Escolha do limiar (conjunto de desenvolvimento)", "",
          "| Limiar | Respondidas no tema (de 15) | Recusadas fora do tema (de 5) |", "| --- | --- | --- |"]
    for x in r["varredura_de_limiar"]:
        l.append(f"| {x['limiar']} | {x['respondidas_no_tema']} | {x['recusadas_fora_do_tema']} |")
    (RAIZ / "RESULTADOS.md").write_text("\n".join(l) + "\n", encoding="utf-8")


def avaliar_llm(dados):
    from app import llm

    from app import cache

    cache.limpar()
    llm.ESPERAR_LIMITE = True  # em lote, o limite de uso do plano gratuito estoura: espera e tenta de novo
    try:  # falha logo, com o motivo, em vez de gerar um arquivo inteiro de respostas sem IA
        llm.gerar("Responda só: ok", "ok")
    except llm.LLMIndisponivel as e:
        print(f"\nO LLM não respondeu, então as respostas completas não foram geradas.\nMotivo: {e}\n"
              "Rode python -m app.llm para diagnosticar.")
        return

    linhas = ["# Respostas completas do serviço (com LLM)", ""]
    citou, total, pelo_llm, por_regra, fieis = 0, 0, 0, 0, 0
    for q in dados["no_tema"] + dados["validacao_no_tema"] + dados["fora_do_tema"] + dados["validacao_fora_do_tema"]:
        r = direitos.responder(q["pergunta"], None)
        tem_citacao = bool(re.search(r"art\.\s*\d", r["resposta"], re.IGNORECASE))
        fora_das_fontes = citacoes_fora_das_fontes(r) if r["geradoPor"] == "llm" else []
        if "esperado" in q and r["encontrouBase"]:
            if r["geradoPor"] == "llm":
                pelo_llm += 1
                citou += tem_citacao
                fieis += not fora_das_fontes
            else:
                por_regra += 1  # o LLM falhou nesta pergunta e entrou o texto alternativo
        linhas += [f"## {q['id']}. {q['pergunta']}", "", r["resposta"], "",
                   f"*Gerado por: {r['geradoPor']} · encontrou base: {r['encontrouBase']} · cita artigo: {tem_citacao}"
                   + (f" · CITA ARTIGO FORA DOS TRECHOS: {', '.join(fora_das_fontes)}" if fora_das_fontes else "") + "*",
                   "**Trechos recuperados:** " + ("; ".join(f"{f['lei']}, {f['artigo']}" for f in r["fontes"]) or "nenhum"), ""]
    (RAIZ / "avaliacao" / "respostas_llm.md").write_text("\n".join(linhas), encoding="utf-8")
    print(f"Respostas geradas pelo LLM que citam artigo: {citou}/{pelo_llm}")
    print(f"Respostas que só citam artigos presentes nos trechos recuperados: {fieis}/{pelo_llm} → rag/avaliacao/respostas_llm.md")
    if por_regra:
        print(f"ATENÇÃO: em {por_regra} perguntas o LLM falhou e entrou o texto alternativo (veja o log acima).")


def citacoes_fora_das_fontes(r) -> list[str]:
    """Artigos citados na resposta que NÃO estão entre os trechos entregues ao LLM (sinal de invenção)."""
    permitidos = {(f["lei"].split(" ")[1], re.sub(r"[º°]", "", f["artigo"]).replace("art. ", "")) for f in r["fontes"]}
    citados = re.findall(r"Lei\s*n?º?\s*([\d.]+/\d{4})[^)]*?art\.\s*(\d+(?:-[A-Z])?)", re.sub(r"[º°]", "", r["resposta"]))
    return sorted({f"Lei {lei}, art. {art}" for lei, art in citados if (lei, art) not in permitidos})


if __name__ == "__main__":
    main(com_llm="--com-llm" in sys.argv)
