# Guia de publicação

## GitHub

Use esta pasta extraída como raiz do projeto. Não coloque apenas o ZIP dentro do repositório: publique os arquivos extraídos para que o código e o README sejam navegáveis.

Crie um novo repositório vazio, inicialmente privado, sem README automático. Dentro da pasta extraída:

```bash
git init -b main
git add .
git status
git commit -m "Initial public release"
git remote add origin https://github.com/SEU_USUARIO/SEU_NOVO_REPOSITORIO.git
git push -u origin main
```

Substitua a URL pela do novo repositório. Confira o README, as imagens e a execução de Actions antes de tornar esse novo repositório público. O repositório antigo e seu histórico permanecem separados. O procedimento detalhado está em `docs/PUBLICATION.md`.

Se você já executou a demonstração, o `.gitignore` exclui o `.env`. Confira `git status` antes do commit. Nenhuma licença de reutilização foi escolhida neste pacote; caso queira permitir reutilização pública, escolha a licença adequada e adicione um arquivo LICENSE.

Descrição sugerida do repositório:

> Personal finance application built with Python, Flask and MySQL. Docker demo, transactional financial rules, automated tests and responsive dashboard.

Tópicos sugeridos: `python`, `flask`, `mysql`, `docker`, `personal-finance`, `pytest`, `web-application`.

## LinkedIn

Use o texto de `LINKEDIN.md`, acrescente o link público do novo repositório e anexe uma seleção das imagens abaixo. O código fica acessível pelo repositório; as imagens apresentam o sistema no post.

| Ordem | Arquivo em `docs/screenshots/` | Texto alternativo sugerido |
| --- | --- | --- |
| 1 | `dashboard-desktop.png` | Dashboard do OhMyCoin com indicadores, gráficos de fluxo de caixa e compromissos financeiros fictícios. |
| 2 | `cartoes-desktop.png` | Tela de cartões da demonstração do OhMyCoin, com limites estimados e compras parceladas. |
| 3 | `dividas-desktop.png` | Tela de dívidas do OhMyCoin, com acompanhamento de parcelas e pagamentos de exemplo. |
| 4 | `caixinhas-mobile.png` | Metas de economia do OhMyCoin em uma tela de celular, com valores fictícios. |

Todas as imagens são capturas reais de página inteira. Confira a prévia do post para escolher o enquadramento desejado. As versões desktop e mobile permitem adaptar a seleção sem recriar telas.

## Inventário das imagens

Há versões `-desktop.png` e `-mobile.png` de: dashboard, previsoes, movimentacoes, contas, cartoes, dividas, caixinhas, categorias, configuracoes e perfil.

Os registros e as credenciais de demonstração são fictícios. Os resultados de testes referem-se à versão descrita em `VALIDACAO.md`; atualize os números se modificar o código e executar uma nova validação.
