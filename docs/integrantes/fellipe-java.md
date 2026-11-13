# Fellipe (Java): o que você precisa saber do serviço de IA

O serviço de IA (`sereno-ia`, em Python/FastAPI) **depende de duas coisas da API Java**: o token de login e a rota de lugares. Se as duas estiverem certas, não precisa fazer mais nada.

## 1. O token JWT precisa sair assim

A IA não tem login próprio. Ela valida o token que o Java emite.

| Item | Valor |
| --- | --- |
| Algoritmo | HS256 |
| Segredo | `JWT_SECRET`, **o mesmo valor** no Java, no .NET e na IA, com no mínimo 32 caracteres |
| Como o segredo vira chave | **Texto UTF-8**, igual ao .NET (`Encoding.UTF8.GetBytes`). No Java: `Keys.hmacShaKeyFor(segredo.getBytes(StandardCharsets.UTF_8))`. Se você usa `Decoders.BASE64.decode(segredo)`, me avisa: a IA tem a opção `JWT_SECRET_BASE64=true`, mas aí o .NET também teria de mudar. O mais simples é os três usarem texto. |
| `iss` | `sereno-auth` |
| `aud` | `sereno-app` |
| `sub` | id do usuário (**obrigatório**) |
| `exp` | expiração (**obrigatório**) |
| `email`, `role` | opcionais (a IA lê, mas não exige) |

Se faltar `sub` ou `exp`, ou se `iss`/`aud` vierem diferentes, a IA responde **401 NAO_AUTENTICADO** mesmo com o segredo certo.

O segredo nunca entra no código nem no GitHub: só em variável de ambiente (na Azure, em Configurações do Web App).

## 2. A rota de lugares que a IA chama

Na previsão de calma, a IA chama o Java com o token do próprio usuário:

```
GET {JAVA_API_URL}/api/locais/{id}
Authorization: Bearer <token do usuário>
```

O que a IA espera de volta:

- **200** com um JSON que tenha pelo menos:
  - `categoria`: qualquer um dos 12 tipos do Java (`PARQUE`, `BIBLIOTECA`, `MUSEU`, `CENTRO_CULTURAL`, `SHOPPING`, `RESTAURANTE`, `CAFE`, `TRANSPORTE`, `SAUDE`, `SERVICO_PUBLICO`, `EDUCACAO`, `OUTRO`)
  - `nome`: opcional, mas sem ele a frase sai como "Local 3"
- **404** se o lugar não existir (a IA repassa como 404 NAO_ENCONTRADO)

O modelo foi treinado com 6 perfis; cada tipo do Java usa o perfil mais parecido, mas com o próprio horário de funcionamento (ex.: museu fecha às segundas) e o próprio nome no texto. Tipo desconhecido é tratado como `OUTRO`: **nunca dá erro por causa da categoria**.

| Tipo do Java | Perfil do modelo | Horário típico usado |
| --- | --- | --- |
| PARQUE, CENTRO_CULTURAL, OUTRO | LAZER | parque 5h–22h; centro cultural 10h–21h (fecha seg); outro 8h–20h |
| BIBLIOTECA, MUSEU, EDUCACAO | EDUCACAO | biblioteca seg–sáb; museu 10h–18h (fecha seg) |
| SHOPPING, RESTAURANTE, CAFE | MERCADO | shopping 10h–22h; restaurante 11h–23h; café 7h–20h |
| TRANSPORTE, SAUDE, SERVICO_PUBLICO | o próprio | igual ao treino |

A IA guarda os dados de cada lugar por 1 h, então não chama o Java a cada previsão. Ela espera até 8 s pela resposta (o Render gratuito demora para acordar).

Se a rota não existir, demorar demais ou cair, a IA usa uma lista local com estes 6 lugares (ids de 1 a 6); para outros ids ela responde **503** ("tente de novo"), não 404, porque o lugar pode existir no Java. **Se o seed do Java usar os mesmos ids, as duas fontes batem:**

| id | nome | categoria |
| --- | --- | --- |
| 1 | UBS Vila Mariana | SAUDE |
| 2 | Mercado Municipal Paulistano | MERCADO |
| 3 | Terminal Parque Dom Pedro II | TRANSPORTE |
| 4 | Parque Ibirapuera | LAZER |
| 5 | Poupatempo Sé | SERVICO_PUBLICO |
| 6 | Biblioteca Mário de Andrade | EDUCACAO |

**Me confirma:** a rota existe com esse caminho? O campo se chama `categoria` mesmo? Se for diferente, eu ajusto o `app/catalogo.py`.

## 3. Formato de erro

A IA responde erros no mesmo formato do contrato:

```json
{ "status": 401, "erro": "NAO_AUTENTICADO", "mensagem": "Token inválido.", "campos": [], "timestamp": "...", "path": "/ia/direitos" }
```

## 4. Na apresentação de IA (sua parte, cerca de 1 min)

Explicar o login único: "o usuário faz login uma vez no Java e o mesmo token vale na API .NET e no serviço de IA, porque os três validam com o mesmo segredo, que fica só nas variáveis de ambiente". Se der, mostrar o insight com Spring AI do Java como mais um uso de IA generativa no projeto.

Pergunta provável: *"E se o token expirar?"* A IA responde 401 com "Sessão expirada. Faça login novamente." e o app manda o usuário de volta para o login.
