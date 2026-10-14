# Validação do projeto

Este documento registra verificações reproduzíveis do código publicado. Os
resultados abaixo devem ser atualizados sempre que uma mudança relevante for
feita na aplicação ou na infraestrutura.

Última execução local: 14/10/2026.

## Resultados de referência

- 110 testes aprovados; cobertura da aplicação de 81%.
- Ruff, Bandit, pip-audit e verificação heurística da árvore de publicação aprovados.
- Build Docker, inicialização MySQL, login da demonstração e reinicialização verificados.
- Dez páginas com dados de exemplo verificadas em Chromium, em desktop (1440 px) e celular (390 px).
- Sem erros JavaScript/CSP ou transbordamento horizontal da página nos cenários verificados; gráficos e cancelamento de exclusões também verificados.

Os resultados não equivalem a uma auditoria exaustiva nem a uma garantia de produção. O scanner da árvore não verifica o histórico Git. As regras financeiras e os limites de estimativas estão em `docs/FINANCIAL_RULES.md`.

## Conferência do pacote

O repositório conserva os arquivos necessários à aplicação, incluindo testes, migrações, Docker, `.env.example` e o workflow do GitHub Actions. O `.gitignore` exclui `.env` real, caches, ambientes virtuais e bancos locais. As imagens em `docs/screenshots/` usam somente dados fictícios.
