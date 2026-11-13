# Resultados do modelo de previsão

Gerado por `python -m ml.treinar`. Alvo: nível de sobrecarga de 0 a 100 (média de ruído, luz e lotação).
Dados: 5500 avaliações de 22 lugares — fontes: {'sintetico': 5500}.

| Cenário | Modelo (MAE / R²) | Média geral (MAE / R²) | Média por categoria e hora (MAE / R²) |
| --- | --- | --- | --- |
| teste aleatório (20% das avaliações) | **7.9 / 0.786** | 17.85 / -0.0 | 8.44 / 0.749 |
| lugares novos (nunca vistos) | **9.36 / 0.67** | 17.09 / -0.006 | 9.42 / 0.666 |

MAE em pontos da escala 0–100 (menor é melhor). R² = quanto da variação o modelo explica (1 = tudo).

## Checagens de bom senso

| Caso | Previsto (cheio) | Previsto (vazio) | Resultado |
| --- | --- | --- | --- |
| UBS: segunda 8h deve ser mais cheia que segunda 16h | 76 | 23 | ok |
| Terminal: quarta 18h mais cheio que domingo 18h | 69 | 36 | ok |
| Parque: sábado 11h mais cheio que terça 11h | 80 | 35 | ok |
| Poupatempo: segunda 10h mais cheio que sexta 17h | 67 | 22 | ok |
| Biblioteca: terça 9h mais calma que terça 15h | 49 | 19 | ok |
