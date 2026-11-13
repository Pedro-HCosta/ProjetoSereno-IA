# Eduardo (.NET): o que você precisa saber do serviço de IA

O serviço de IA **não chama a sua API diretamente**. A ligação passa pelo app: o app pega na sua API o status da estação e, quando um equipamento está parado, pergunta à IA quais são os direitos da pessoa. Ou seja, **os dados das suas estações e equipamentos são o gatilho do botão "Quais são meus direitos?"**.

## 1. O que precisa estar igual entre a API .NET e a IA

| Item | Valor |
| --- | --- |
| `JWT_SECRET` | o mesmo valor nos três serviços (mínimo 32 caracteres), só em variável de ambiente |
| `iss` / `aud` | `sereno-auth` / `sereno-app` |
| Formato de erro | `{ status, erro, mensagem, campos, timestamp, path }`: a IA copiou o formato da sua API |

## 2. O seed das estações

Para a demonstração funcionar, **pelo menos uma estação precisa ter elevador ou escada rolante parados** nos dados que o seed cria. Sem isso o botão de direitos não aparece no app. **Me confirma se o seed já deixa uma assim**; se não, dá para mudar o status de um equipamento antes de apresentar.

## 3. Como o app usa os seus dados com a IA

1. O app chama a sua API (estação, acessibilidade/rotas) e vê, por exemplo, "Elevador fora de serviço" na estação Sé.
2. O app chama `POST /ia/direitos` com:

```json
{
  "situacao": "O elevador da estação está parado e eu uso cadeira de rodas. Quais são meus direitos?",
  "contexto": "Estação Sé, elevador fora de serviço"
}
```

3. A IA busca os artigos de lei mais parecidos (Lei Brasileira de Inclusão, Lei 10.098 e Lei 12.764) e devolve uma resposta citando o artigo, com os trechos e links do Planalto.

Quanto mais claro o texto do status do equipamento (ex.: "elevador fora de serviço", "escada rolante parada"), melhor a busca: o `contexto` entra na pesquisa junto com a pergunta.

## 4. Test Plans

Os test cases do serviço de IA no Azure Test Plans podem se basear nas rotas abaixo (todas, menos o health, exigem `Authorization: Bearer <token>`):

| Caso | Chamada | Resultado esperado |
| --- | --- | --- |
| Serviço no ar | `GET /ia/health` | 200, `status: "UP"` |
| Sem token | `POST /ia/direitos` sem cabeçalho | 401 `NAO_AUTENTICADO` |
| Previsão válida | `POST /ia/previsao-calma` `{ "localId": 2, "diaSemana": 6, "hora": 12 }` | 200 com `nivelPrevisto` de 0 a 100 e `faixa` |
| Hora inválida | mesmo corpo com `"hora": 25` | 400 `VALIDACAO`, `campos` aponta `hora` |
| Lugar inexistente | `"localId": 999` | 404 `NAO_ENCONTRADO` |
| Direitos no tema | pergunta do item 3 | 200, `encontrouBase: true`, cita "Lei 13.146" |
| Direitos fora do tema | `"situacao": "Qual a capital da França?"` | 200, `encontrouBase: false`, `fontes: []` |

Os testes automatizados da IA (38, com pytest) rodam com `python iniciar.py testes`; dá para tirar print disso para a evidência.

## 5. Na apresentação de IA (sua parte, cerca de 1 min)

Junto com o Felype na demonstração dos direitos: "esta estação está com o elevador parado, informação que vem da API .NET; com um toque o app pergunta à IA quais são os direitos da pessoa".
