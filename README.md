# ResolveAI

Central de atendimento com busca na base de conhecimento e sugestões de resposta ligadas às fontes consultadas. O agente revisa o texto antes de registrar a resposta.

## Rodar localmente

Requer Node.js 20 ou superior.

```bash
npm install
npm start
```

Abra <http://localhost:3004>. Chamados e artigos fictícios são criados na primeira execução. O banco SQLite fica em `data/support.sqlite`.

As sugestões funcionam localmente sem credenciais: uma busca lexical seleciona artigos relacionados e prepara um rascunho de revisão. Para chamar um modelo OpenAI, copie `.env.example` para `.env`, configure `OPENAI_API_KEY` e `OPENAI_MODEL`, reinicie o servidor e use o mesmo fluxo. A chave permanece no servidor e o modo usado volta explicitamente na resposta da API.

## Funcionalidades

- Fila de atendimento com filtros, categorias e prioridade.
- Criação e atualização de chamados.
- Base local pesquisável com artigos de suporte fictícios.
- Seleção de artigos por correspondência com a mensagem e o assunto.
- Sugestão de rascunho com fontes identificadas e envio apenas após ação do agente.
- Registro da resposta e resolução do chamado.
- Encaminhamento para revisão humana quando nenhum artigo tem correspondência.

## Decisões técnicas

- A base de conhecimento é enviada como contexto delimitado ao modelo configurado; a instrução pede para usar somente os artigos e evitar promessas sem fonte.
- Sem credencial, a busca lexical fornece um rascunho demonstrativo e indica seu modo. Esse fallback não é uma chamada a um modelo de linguagem.
- Toda sugestão inclui `needsReview: true`; o fluxo não envia mensagens ao cliente automaticamente.
- A busca lexical local é simples e adequada a uma demonstração pequena; em produção, seria substituída por recuperação semântica, autenticação e controle de acesso.

## API

- `GET /api/tickets` — lista chamados.
- `POST /api/tickets` — cria chamado.
- `PATCH /api/tickets/:id/status` — atualiza status.
- `GET /api/articles` — lista artigos.
- `POST /api/suggest` — recupera fontes e gera rascunho.
- `POST /api/replies` — registra resposta revisada.

## Próximas melhorias

Editor da base de conhecimento, teste de qualidade da recuperação, controle de acesso por equipe e avaliação de respostas com um conjunto de exemplos rotulados.
