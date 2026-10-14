# Texto para LinkedIn

Use o texto abaixo como rascunho. Antes de publicar, adapte a abertura e os
aprendizados para a sua experiência e acrescente os links validados do
repositório e da demonstração.

---

Como transformar um projeto de finanças pessoais em um estudo de caso de engenharia de software?

No OhMyCoin, trabalhei na evolução de uma aplicação com Python, Flask e MySQL que reúne contas, movimentações, cartões, dívidas, metas de economia e um dashboard financeiro.

A interface é uma parte do projeto. Outra parte importante está nas regras que sustentam os números:

• Separação da lógica de negócio em serviços por domínio.
• Uso de Decimal e tratamento do arredondamento de parcelas.
• Pagamentos de dívidas e estornos com consistência transacional.
• Distinção entre fluxo de caixa registrado e compromissos previstos.
• Validação de permissões, proteção CSRF e revogação de sessões após troca de senha.
• Ambiente de demonstração reproduzível com Docker Compose e dados fictícios.

Na versão validada, a suíte passou com 110 testes e 81% de cobertura da aplicação. O pipeline também verificou lint, dependências, segurança estática e navegação em desktop e celular.

Um aprendizado que levo desse trabalho: um dashboard útil depende tanto da clareza das regras financeiras quanto da apresentação dos gráficos. Por isso, documentei as decisões e os limites das estimativas, incluindo a ausência de conciliação de faturas.

As imagens mostram a demonstração em funcionamento. O próximo passo é evoluir a conciliação e ampliar os cenários de teste.

Como você costuma testar regras de parcelamento e estorno nos seus projetos?

#Python #Flask #MySQL #Docker #DesenvolvimentoWeb
