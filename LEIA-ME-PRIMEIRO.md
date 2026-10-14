# OhMyCoin — código e kit de apresentação

Este pacote contém o código completo do projeto, a configuração Docker, os testes, a documentação e 20 imagens reais da demonstração com dados fictícios.

## Executar

Instale Docker com Compose v2. Abra um terminal nesta pasta e execute:

```bash
cp .env.example .env
docker compose up --build
```

No PowerShell, substitua o primeiro comando por `Copy-Item .env.example .env`.

Aguarde a inicialização do MySQL e da aplicação. Acesse http://localhost:5000 e entre com `demo@example.com` / `Demo@12345`.

O primeiro build precisa de internet para baixar dependências. Os dados de demonstração são carregados automaticamente. Para parar preservando os dados, use `docker compose down`.

## O que publicar

- **GitHub:** publique o conteúdo desta pasta como um novo repositório. O README já exibe imagens e explica como executar. Consulte `divulgacao/GUIA_DE_PUBLICACAO.md`.
- **LinkedIn:** copie o texto de `divulgacao/LINKEDIN.md` e anexe as imagens indicadas no guia. Compartilhe o código pelo link do novo repositório.
- **Imagens:** `docs/screenshots/` contém 10 telas em desktop e as mesmas 10 em celular.
- **Validação:** `VALIDACAO.md` registra a versão de referência e os resultados obtidos.

O ZIP não contém histórico Git, ambiente virtual, banco de dados ou arquivo `.env` real. O `.env.example` contém apenas valores de demonstração. O ambiente fornecido serve para avaliação local; configuração e operação de produção são tratadas separadamente em `docs/SECURITY.md`.
