# Gustavo: o que você precisa saber do serviço de IA

Você abre e fecha a apresentação de IA. Mesmo sem mexer no código, é bom saber explicar o que a IA faz e por que ela importa: o professor pode perguntar para qualquer integrante.

## 1. O Sereno em uma frase

Um app de acessibilidade urbana que avisa, **antes de a pessoa sair de casa**, se o destino e o caminho são acessíveis para ela.

## 2. As duas funções de IA

| Função | Para quem | O que faz | Como funciona (bem resumido) |
| --- | --- | --- | --- |
| **Previsão de calma** | Pessoas com sensibilidade sensorial (autismo, TDAH, ansiedade) | Diz como um lugar deve estar num dia e hora (barulho, luz, lotação), sugere o horário mais tranquilo e explica numa frase simples | Um modelo de Machine Learning (Random Forest) prevê o nível de 0 a 100; um LLM escreve a explicação |
| **Quais são meus direitos?** | Pessoas com deficiência ou mobilidade reduzida | Quando o elevador ou a escada da estação estão parados, explica o que a lei garante, citando o artigo | RAG: busca os artigos mais parecidos em 3 leis federais e o LLM responde **só com base neles** |

As 3 leis: Lei Brasileira de Inclusão (13.146/2015), Lei de Acessibilidade (10.098/2000) e a Lei Berenice Piana, sobre autismo (12.764/2012).

## 3. Sua fala de abertura (cerca de 1 min)

"Para quem tem hipersensibilidade sensorial ou mobilidade reduzida, sair de casa exige planejamento: o lugar vai estar lotado e barulhento? O elevador da estação funciona? E se não funcionar, o que eu posso exigir? O Sereno responde essas perguntas, e a IA está por trás das respostas."

Exemplos concretos ajudam: uma pessoa autista que desiste de ir à UBS por medo de chegar no horário de pico; um cadeirante que encontra o elevador da estação parado e não sabe o que a lei garante.

## 4. Fechamento (30 s)

"O Sereno transforma informação espalhada em autonomia: saber quando ir, como chegar e o que exigir." E abrir para perguntas.

## 5. Se perguntarem para você

- **"A IA pode inventar lei?"** Ela só pode citar artigos que a busca encontrou, e se a pergunta não tem relação com acessibilidade ela responde que não encontrou base. Toda resposta mostra o trecho original e o link da lei no site do Planalto, e um aviso de que não substitui a Defensoria.
- **"Os dados são reais?"** Por enquanto são simulados (6.000 avaliações de 24 lugares). O modelo está pronto para receber avaliações reais dos usuários.
- **"O que acontece se a IA cair?"** O app continua funcionando: entra um texto padrão no lugar da frase do LLM.
- **"Guarda dados pessoais?"** Não. Para o LLM vão só lugar, dia, hora e nível, ou a pergunta e os trechos de lei; nunca e-mail ou id do usuário.

Detalhes técnicos (números, arquitetura, mudanças de requisito) ficam com o Pedro; se a pergunta for muito técnica, pode passar para ele.
