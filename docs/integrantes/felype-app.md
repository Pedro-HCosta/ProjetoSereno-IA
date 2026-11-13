# Felype (app): o que você precisa saber do serviço de IA

Você é quem mostra a IA funcionando: as duas funções aparecem **dentro das telas do app**. Este guia tem tudo o que o app precisa para chamar o serviço.

## 1. Básico

- **URL base:** `https://<web-app-da-ia>.azurewebsites.net` (te passo assim que subir). Use essa URL da Azure no app: é HTTPS e funciona no emulador e no celular.
- **Testando com a IA rodando num PC:** no celular, `localhost` é o próprio celular, não o PC. No emulador Android use `http://10.0.2.2:8000`; no celular físico, o IP do PC na mesma rede (ex.: `http://192.168.0.10:8000`). Rode a IA com `python iniciar.py --rede` (deixa o serviço acessível para o celular e o emulador; o Windows pode pedir para liberar no firewall). No **Expo Go** o HTTP sem S funciona; num **build** (APK ou development build) o Android bloqueia, e para liberar só em teste use o plugin `expo-build-properties` com `"android": { "usesCleartextTraffic": true }` no `app.json`. Com a URL da Azure (HTTPS) nada disso é necessário.
- **Documentação interativa:** `{URL}/ia/docs` (Swagger, dá para testar tudo pelo navegador antes de ligar no app)
- **Login:** use o **mesmo token** que o Java devolve no login, guardado com `expo-secure-store`, em todas as chamadas: `Authorization: Bearer <token>`
- **Tempo:** a resposta pode levar **até uns 10 s** quando o LLM é chamado (geralmente 1 a 3 s; repetidas saem do cache na hora). **Mostre um carregando** e não use um timeout menor que 15 s no app.

## 2. Card "Previsão de calma" (tela de detalhe do lugar)

```
POST /ia/previsao-calma
{ "localId": 2, "diaSemana": 6, "hora": 12 }
```

- `diaSemana`: **0 = domingo … 6 = sábado**, o mesmo formato do `new Date().getDay()`. Também aceita o nome: `"SABADO"`, `"segunda"`.
- `hora`: 0 a 23 (`new Date().getHours()`), ou `"12:30"` (só a hora conta).

Exemplo de chamada (serve igual para `/ia/direitos`, só muda a rota e o corpo):

```ts
import * as SecureStore from "expo-secure-store";

const IA_URL = process.env.EXPO_PUBLIC_IA_URL; // no .env do app: EXPO_PUBLIC_IA_URL=https://...azurewebsites.net

export async function chamarIA(rota: string, corpo: object) {
  const token = await SecureStore.getItemAsync("token"); // o mesmo token do login no Java
  const controle = new AbortController();
  const limite = setTimeout(() => controle.abort(), 15000); // o LLM pode levar até ~10 s
  try {
    const r = await fetch(`${IA_URL}${rota}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify(corpo),
      signal: controle.signal,
    });
    const dados = await r.json();
    if (!r.ok) throw dados; // { status, erro, mensagem, campos, ... }
    return dados;
  } finally {
    clearTimeout(limite);
  }
}

// Card de previsão para "agora":
const agora = new Date();
const previsao = await chamarIA("/ia/previsao-calma", {
  localId: 2, diaSemana: agora.getDay(), hora: agora.getHours(),
});
```

Só a URL vai no `.env` do app. A chave do LLM e o `JWT_SECRET` **nunca** vão para o app: variáveis `EXPO_PUBLIC_` ficam visíveis dentro do APK.

Resposta:

```json
{
  "nivelPrevisto": 78,
  "faixa": "AGITADO",
  "explicacao": "Sábado ao meio-dia o Mercado costuma estar cheio e barulhento...",
  "melhorHorario": 8,
  "alertas": ["Barulho alto previsto nesse horário", "Lugar cheio previsto nesse horário"],
  "geradoPor": "llm"
}
```

Sugestão de tela:

- **Faixa com cor:** `TRANQUILO` verde, `MODERADO` amarelo, `AGITADO` vermelho. O `nivelPrevisto` vai de 0 (muito calmo) a 100 (muito intenso).
- **Explicação** em texto corrido.
- **"Melhor horário: 8h"**. Se vier `null`, o lugar costuma estar fechado nesse dia.
- **Alertas** como chips ou ícones.
- `geradoPor` é só informativo: `"regra"` quer dizer que o LLM não respondeu e entrou um texto padrão. O card funciona igual.

## 3. Botão "Quais são meus direitos?" (tela da estação com equipamento parado)

Mostre o botão quando a API .NET do Eduardo indicar elevador ou escada parados.

```
POST /ia/direitos
{
  "situacao": "O elevador da estação está parado e eu uso cadeira de rodas. Quais são meus direitos?",
  "contexto": "Estação Sé, elevador fora de serviço"
}
```

- `situacao`: de 5 a 500 caracteres. Pode ser uma frase pronta do app ou um campo para a pessoa escrever.
- `contexto`: até 300 caracteres, opcional. **Coloque aqui o nome da estação e o status do equipamento que vieram do .NET**: é isso que liga a IA à API do Eduardo e melhora a busca.

Resposta:

```json
{
  "resposta": "Você tem direito a ... (Lei 13.146/2015, art. 46) ...",
  "fontes": [
    { "lei": "Lei 13.146/2015", "artigo": "art. 46", "trecho": "...", "url": "https://www.planalto.gov.br/...", "relevancia": 0.41 }
  ],
  "encontrouBase": true,
  "geradoPor": "llm",
  "aviso": "Esta orientação é informativa e não substitui a de um advogado ou da Defensoria Pública."
}
```

Sugestão de tela:

- A `resposta` em destaque.
- Embaixo, "Base legal": cada fonte com lei, artigo e um botão "Ler na lei" que abre a `url` no navegador do celular (`Linking.openURL(fonte.url)`, do `react-native`, ou `WebBrowser.openBrowserAsync` do `expo-web-browser` para abrir dentro do app). O `trecho` pode ficar recolhido.
- O `aviso` em letra pequena no rodapé (**precisa aparecer**).
- Se `encontrouBase` for `false`, a resposta já vem dizendo que não encontrou base e indicando a Defensoria. Só não mostre a seção de fontes (a lista vem vazia).

## 4. Erros

Todos vêm no mesmo formato: `{ status, erro, mensagem, campos, timestamp, path }`. A `mensagem` já está em português e pode ir direto para o usuário.

| Status | `erro` | O que fazer no app |
| --- | --- | --- |
| 400 | `VALIDACAO` | Mostrar a mensagem; `campos` diz qual campo está errado |
| 401 | `NAO_AUTENTICADO` | Mandar para o login (token ausente ou expirado) |
| 404 | `NAO_ENCONTRADO` | "Lugar não encontrado" |
| 503 na previsão | `SERVICO_INDISPONIVEL` | A API Java não respondeu a tempo (ex.: Render acordando). Vale tentar de novo uma vez depois de alguns segundos |
| 503 / 500 | `SERVICO_INDISPONIVEL` / `ERRO_INTERNO` | "Não foi possível carregar a previsão agora" e esconder o card |

## 5. Na apresentação de IA (sua parte, a maior: cerca de 4 min)

1. **Previsão:** abrir o Mercado Municipal no sábado ao meio-dia → mostrar nível, faixa, explicação e melhor horário → trocar para terça de manhã e mostrar a previsão mudando.
2. **Direitos:** abrir a estação com elevador parado (o Eduardo explica de onde vem o dado) → tocar no botão → mostrar a resposta citando a lei e o link para o Planalto.

Antes de entrar na sala, faça cada uma dessas consultas uma vez: elas ficam no cache e na hora respondem instantaneamente. Deixe o celular ou emulador espelhado no projetor e conectado numa rede confiável (o 4G do próprio celular costuma ser mais seguro que o Wi-Fi da sala). Se a rede falhar, o plano B é mostrar as mesmas chamadas pelo Swagger (`/ia/docs`) no notebook.
