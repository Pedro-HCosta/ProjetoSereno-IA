# Avaliação do RAG (direitos de acessibilidade)

Gerado por `python -m rag.avaliar`. Perguntas em `rag/avaliacao/perguntas.json`. Índice: 3 leis divididas por artigo.

| Conjunto | Acerto top-3 | Acerto top-1 | Respondidas (no tema) | Recusadas (fora do tema) |
| --- | --- | --- | --- | --- |
| Desenvolvimento (usado para ajustar) | 15/15 | 9/15 | 15/15 | 5/5 |
| Validação (escrita depois dos ajustes) | 5/6 | 3/6 | 4/6 | 1/2 |
| Fluxo principal do app (elevador/escada parados na estação) | 4/4 | — | — | — |

Limiar de relevância em uso: **0.13** (abaixo dele o serviço responde que não encontrou base, sem chamar o LLM).

## Desenvolvimento

| # | Pergunta | Artigo esperado | 3 primeiros trechos | Nota do 1º | Acertou |
| --- | --- | --- | --- | --- | --- |
| 1 | O elevador da estação de metrô está parado e eu sou cadeirante. Quais são meus direitos? | art. 48 (13.146); art. 46 (13.146) | art. 46 (13.146); art. 48 (13.146); art. 16 (10.098) | 0.288 | sim (1º) |
| 2 | A estação de trem não tem rampa nem elevador. Ela é obrigada a ser acessível? | art. 48 (13.146); art. 46 (13.146) | art. 16 (10.098); art. 48 (13.146); art. 46 (13.146) | 0.266 | sim (2º) |
| 3 | O ônibus da minha linha não tem elevador para cadeira de rodas. Isso é permitido? | art. 16 (10.098); art. 48 (13.146) | art. 16 (10.098); art. 12-A (10.098); art. 46 (13.146) | 0.273 | sim (1º) |
| 4 | Tenho direito a atendimento prioritário na fila do Poupatempo? | art. 9º (13.146) | art. 9º (13.146); art. 111 (13.146); art. 18 (13.146) | 0.247 | sim (1º) |
| 5 | Meu filho é autista. Ele é considerado pessoa com deficiência pela lei? | art. 1º (12.764) | art. 2º (12.764); art. 5º (12.764); art. 1º (12.764) | 0.333 | sim (3º) |
| 6 | A escola recusou a matrícula do meu filho autista. O que a lei diz sobre isso? | art. 7º (12.764) | art. 7º (12.764); art. 2º (12.764); art. 3º (12.764) | 0.266 | sim (1º) |
| 7 | Meu filho autista tem direito a um acompanhante especializado na sala de aula? | art. 3º (12.764) | art. 2º (12.764); art. 3º (12.764); art. 5º (12.764) | 0.314 | sim (2º) |
| 8 | Quantas vagas de estacionamento precisam ser reservadas para pessoas com deficiência? | art. 47 (13.146); art. 7º (10.098) | art. 7º (10.098); art. 47 (13.146); art. 119 (13.146) | 0.273 | sim (1º) |
| 9 | O prédio público onde fica a UBS não tem acesso para cadeirantes. Ele é obrigado a ser acessível? | art. 11 (10.098); art. 57 (13.146); art. 25 (13.146) | art. 57 (13.146); art. 12-A (10.098); art. 13 (10.098) | 0.297 | sim (1º) |
| 10 | O que a lei considera como pessoa com deficiência? | art. 2º (13.146) | art. 26 (13.146); art. 2º (13.146); art. 4º (13.146) | 0.187 | sim (2º) |
| 11 | O que significa acessibilidade segundo a lei? | art. 3º (13.146); art. 2º (10.098) | art. 26 (13.146); art. 3º (13.146); art. 2º (13.146) | 0.135 | sim (2º) |
| 12 | Fui discriminado por ser pessoa com deficiência. Isso é crime? | art. 88 (13.146); art. 4º (13.146) | art. 4º (13.146); art. 23 (13.146); art. 5º (13.146) | 0.165 | sim (1º) |
| 13 | A pessoa com autismo tem direito a atendimento de saúde e diagnóstico precoce? | art. 3º (12.764); art. 2º (12.764) | art. 2º (12.764); art. 3º (12.764); art. 5º (12.764) | 0.395 | sim (1º) |
| 14 | Existe uma carteira de identificação para pessoa com transtorno do espectro autista? | art. 3º-A (12.764) | art. 3º-A (12.764); art. 2º (12.764); art. 5º (12.764) | 0.395 | sim (1º) |
| 15 | Prédios residenciais que têm elevador precisam seguir regras de acessibilidade? | art. 13 (10.098) | art. 14 (10.098); art. 13 (10.098); art. 104 (13.146) | 0.171 | sim (2º) |

| # | Pergunta fora do tema | Nota do 1º trecho | Recusada |
| --- | --- | --- | --- |
| 101 | Qual é a receita de bolo de cenoura com cobertura de chocolate? | 0.088 | sim |
| 102 | Qual é a capital da França? | 0.084 | sim |
| 103 | Vai chover amanhã em São Paulo? | 0.085 | sim |
| 104 | Como faço para trocar o pneu do carro? | 0.091 | sim |
| 105 | Qual é o melhor time de futebol do Brasil? | 0.128 | sim |

## Validação

| # | Pergunta | Artigo esperado | 3 primeiros trechos | Nota do 1º | Acertou |
| --- | --- | --- | --- | --- | --- |
| 201 | Os semáforos precisam ter sinal sonoro para pessoas cegas? | art. 9º (10.098) | art. 9º (10.098); art. 112 (13.146); art. 8º (10.098) | 0.303 | sim (1º) |
| 202 | Os banheiros do parque precisam ser acessíveis? | art. 6º (10.098) | art. 6º (10.098); art. 73-A (13.146); art. 48 (13.146) | 0.303 | sim (1º) |
| 203 | O hotel precisa ter quartos acessíveis para cadeirantes? | art. 45 (13.146) | art. 3º (10.098); art. 13 (10.098); art. 73-A (13.146) | 0.09 | não |
| 204 | Pessoa com deficiência tem direito de trabalhar em igualdade com as outras pessoas? | art. 34 (13.146) | art. 34 (13.146); art. 38 (13.146); art. 4º (13.146) | 0.265 | sim (1º) |
| 205 | Fui impedido de me matricular na faculdade por ter deficiência. Isso é permitido? | art. 27 (13.146); art. 28 (13.146); art. 7º (12.764) | art. 76 (13.146); art. 2º (13.146); art. 7º (12.764) | 0.09 | sim (3º) |
| 206 | O cinema precisa reservar lugar para cadeira de rodas? | art. 44 (13.146); art. 12 (10.098) | art. 12-A (10.098); art. 12 (10.098); art. 53 (13.146) | 0.252 | sim (2º) |

| # | Pergunta fora do tema | Nota do 1º trecho | Recusada |
| --- | --- | --- | --- |
| 301 | Como faço para declarar o imposto de renda? | 0.121 | sim |
| 302 | Quanto custa uma passagem de avião para o Rio de Janeiro? | 0.16 | não |

## Fluxo principal do app

Botão "Quais são meus direitos?" na estação: o esperado é o art. 46 ou o art. 48 da Lei 13.146/2015.

| # | Pergunta (+ contexto) | 3 primeiros trechos | Acertou |
| --- | --- | --- | --- |
| 401 | O elevador da estação está parado e eu sou cadeirante. | art. 46 (13.146); art. 48 (13.146); art. 12-A (10.098) | sim |
| 402 | Sou cadeirante e a escada rolante do metrô não funciona | art. 46 (13.146); art. 12-A (10.098); art. 48 (13.146) | sim |
| 403 | Quais são meus direitos? | art. 46 (13.146); art. 48 (13.146); art. 16 (10.098) | sim |
| 404 | A plataforma elevatória do trem quebrou | art. 16 (10.098); art. 48 (13.146); art. 46 (13.146) | sim |

## Escolha do limiar (conjunto de desenvolvimento)

| Limiar | Respondidas no tema (de 15) | Recusadas fora do tema (de 5) |
| --- | --- | --- |
| 0.1 | 15 | 4 |
| 0.12 | 15 | 4 |
| 0.13 | 15 | 5 |
| 0.15 | 14 | 5 |
| 0.2 | 11 | 5 |
| 0.25 | 10 | 5 |
