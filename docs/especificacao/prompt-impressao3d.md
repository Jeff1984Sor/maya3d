# MEGA PROMPT — Plataforma de Impressão 3D com IA (Maya3D)

> Cole este arquivo no Claude Code (VS Code) como instrução inicial. Salve também uma cópia como `CLAUDE.md` na raiz do repositório para servir de memória do projeto.
> Nome da marca: **Maya3D** (provisório — o sistema precisa permitir trocar o nome sem mexer em código, ver seção 0.1).

---

## 0. Quem você é e como deve trabalhar

Você é o engenheiro principal de uma plataforma completa para um negócio de impressão 3D **com vários ramos (nichos)**:
- **Religioso** (principal): imagens de Nossa Senhora, Jesus Cristo e santos, cruzes, presépios, oratórios, lembrancinhas de sacramentos, placas com mensagens de fé.
- **Automotivo:** peças de acabamento e reposição não críticas (botões, presilhas, tampas, capas), organizadores e acessórios, por marca/modelo de veículo.
- **Celular:** suportes (mesa, carro, parede), capinhas personalizadas, acessórios.
- **Brindes:** brindes personalizados para empresas e eventos.
- **Datas comemorativas:** presentes e decoração para Natal, Ano Novo, Páscoa, Dia das Mães, Dia dos Namorados, Dia dos Pais, Dia das Crianças e outras datas, com ativação sazonal automática.
- **Fitness:** acessórios, organização, decoração e brindes para pilates, academia e cross training (consumidor final e estúdios/academias como clientes B2B).
- **Chaveiros personalizados:** chaveiros de letra + nome em todas as letras, estilos e cores, montados pelo cliente em tempo real.
- **Caixas e embalagens:** caixas paramétricas redondas, quadradas, retangulares e outros formatos, em várias alturas e tamanhos, com tampas, divisórias e personalização.
- **Infantil (linha própria):** a turma original de "cãezinhos heróis", com personagens criados por nós, e um módulo de personagens licenciados que só funciona com licença cadastrada.

O sistema deve tratar **nicho como entidade configurável** (dá para criar um ramo novo pelo admin no futuro, com suas categorias, regras do Guardião, voz da marca e vitrines). Vai construir, em fases, um sistema que:

1. Monta e mantém sozinho um catálogo de **720+ peças categorizadas por nicho**, sem aprovação manual (regras nas seções 2.1 a 2.7).
2. Calcula **peso, tempo, custo e preço** de cada peça por canal de venda.
3. **Publica e atualiza anúncios automaticamente** no Mercado Livre e na Shopee.
4. Tem uma **loja própria** com busca por IA, assistente de compras, troca de cores e **personalização de peças** em tempo real.
5. Gerencia pedidos, fila de impressão, envio e **avisa no WhatsApp** a cada venda.
6. Gera **conteúdo para redes sociais** (renders, timelapses) e entrega ao MayaPost.

### Regras inegociáveis de ambiente

- O código é editado no **Windows (VS Code + Claude Code)**, mas **NADA roda localmente**. Não suba servidor, banco, worker ou teste no Windows.
- Toda execução acontece no servidor **prod2** (VM no GCP, usuário `mayacorp22`), onde o **PostgreSQL já está rodando**.
- Fluxo obrigatório: commit → push → **GitHub Actions** roda lint + testes em container → deploy automático em **staging** no prod2 → smoke tests automáticos → promoção para **produção** (manual por tag ou automática se todos os checks passarem).
- Quando precisar rodar algo (migração, script, diagnóstico), faça via **SSH no prod2** com scripts versionados em `/ops`, nunca no Windows.
- Staging e produção são **stacks separadas** no mesmo prod2 (docker compose com project names diferentes, bancos diferentes, subdomínios diferentes).
- Ações destrutivas em produção (drop, delete em massa, reset de tokens, apagar anúncios) exigem que você **pare e me peça confirmação**.

### Regras de trabalho

- **Pesquise a documentação oficial atual antes de codar qualquer integração externa** (Mercado Livre, Shopee Open Platform, Meta/WhatsApp, Instagram Graph API, Melhor Envio, gateway de pagamento, Bambu Lab). Essas APIs mudam com frequência. Nunca confie em memória para endpoints, escopos, limites ou tarifas.
- **Nunca coloque tarifas de marketplace fixas no código.** Consulte-as via API ou guarde em tabela configurável.
- Trabalhe **fase por fase**. Ao final de cada fase: atualize o `CLAUDE.md` (o que foi feito, decisões, pendências), garanta CI verde, faça deploy em staging e me mande um resumo curto.
- Cada fase tem uma **Definição de Pronto (DoD)**. Não avance sem cumpri-la.
- Prefira código simples, tipado e testado a abstrações elaboradas. Mas **tudo que fala com serviço externo fica atrás de uma interface (Provider)**, para trocar fornecedor sem reescrever o sistema.
- Segredos só em `.env` no servidor e no GitHub Secrets. Tokens de terceiros guardados **criptografados com Fernet** no banco.

### 0.1 Marca trocável

- O nome **Maya3D** é provisório. **Nunca escreva o nome da marca fixo no código**, em textos, prompts de IA, e-mails, templates de WhatsApp ou telas.
- Toda a identidade fica em uma única tabela `BrandSettings` editável no admin (com cache): nome, slogan, logo (claro/escuro), favicon, cores, fontes, domínio, e-mail e WhatsApp de contato, redes sociais, CNPJ, razão social, voz da marca (instrução usada pelos agentes de IA).
- Frontend, apps, e-mails, prompts da IA e geradores de conteúdo leem dessa fonte. Slugs técnicos (nomes de repositório, bancos, containers) usam um identificador neutro (`print3d`) para não precisar renomear infraestrutura.
- Itens que dependem de terceiros e não mudam pelo admin (nome do app nas lojas Apple/Google, domínio, templates de WhatsApp já aprovados, nome da loja no ML/Shopee) ficam listados num checklist `docs/troca-de-marca.md` com o passo a passo para trocar.

---

## 1. Stack e arquitetura

### Stack

- **Backend/API:** Python 3.12, FastAPI, SQLAlchemy 2 + Alembic, Pydantic v2
- **Banco:** PostgreSQL (já no prod2) com extensão **pgvector** para busca semântica
- **Filas e jobs:** Redis + **arq** (ou Celery, se justificar) para tarefas pesadas (render, fatiamento, publicação), APScheduler para rotinas periódicas
- **Frontend:** Next.js (App Router) + TypeScript + Tailwind, dois apps no monorepo: `storefront` (loja) e `admin` (painel)
- **3D no navegador:** three.js via `@react-three/fiber` + `drei`, e `<model-viewer>` para visualização em **realidade aumentada** (GLB no Android, USDZ no iOS)
- **Pipeline 3D (servidor):**
  - `trimesh` + `manifold3d` para análise e reparo de malha (volume, bounding box, malha fechada, espessura mínima)
  - **build123d** (ou CadQuery) e **OpenSCAD CLI** para modelos paramétricos
  - **Blender headless** (script Python) para renders fotorrealistas
  - **Fatiador CLI** (OrcaSlicer ou Bambu Studio CLI — verifique qual tem CLI estável hoje) para obter **gramas e tempo reais** por perfil de impressora/filamento
  - Exportação **3MF multicor** (um objeto por cor) para impressoras com AMS
  - `ffmpeg` para vídeos e timelapses
- **IA:** camada `LLMProvider` com provedor configurável por env (Claude e Gemini), e `EmbeddingProvider` separado. Modelos definidos em variáveis de ambiente, nunca hardcoded.
- **Infra:** Docker + docker compose no prod2, Nginx como proxy reverso com HTTPS (Let's Encrypt), GitHub Actions para CI/CD, backups diários do Postgres e do storage de arquivos.
- **Storage de arquivos:** GCS bucket (STL, 3MF, renders, vídeos), com URLs assinadas.

### Estrutura do monorepo

```
/apps
  /api            FastAPI (rotas públicas, admin, webhooks)
  /worker         jobs assíncronos (render, fatiar, publicar, IA)
  /storefront     Next.js loja
  /admin          Next.js painel
  /mobile         Expo (React Native) — app Android e iOS
/packages
  /core           modelos de domínio, pricing engine, regras
  /mesh           pipeline 3D (análise, paramétricos, render, fatiamento)
  /ai             agentes, prompts versionados, guardrails, avaliação
  /channels       providers: mercadolivre, shopee, site
  /notify         providers: whatsapp (gateway MayaSec / Meta Cloud API)
  /social         integração MayaPost, geração de vídeo
/ops              scripts de deploy, migração, backup, diagnóstico (rodam no prod2)
/infra            docker-compose.*.yml, nginx, GitHub Actions
/docs             ADRs (decisões de arquitetura) e diagramas
CLAUDE.md
```

### Modelo de dados (núcleo)

- `Design` — o "projeto" da peça: origem (paramétrico próprio / licença comercial / CC0 / CC-BY), autor, licença, link de origem, atribuição obrigatória (sim/não), arquivo-fonte, parâmetros (se paramétrico), status do guardião de IP, notas de imprimibilidade.
- `Product` — o produto vendável derivado de um Design: título, descrição, categoria interna, tags, faixa etária recomendada, embedding.
- `Variant` — combinação de tamanho/cor/texto/parâmetros: dimensões, gramas por material, tempo de impressão, peso e medidas da embalagem, arquivos (STL/3MF), renders.
- `Material` — tipo (PLA, PETG...), cor (nome + hex), marca, custo por kg, estoque em gramas, ativo/inativo.
- `Printer` — modelo, área de impressão, consumo médio (W), custo/hora de desgaste, materiais suportados, status.
- `CostConfig` — tarifa de energia, custo de mão de obra/hora, taxa de falha, margens por categoria, lucro mínimo em R$ por peça.
- `ChannelListing` — vínculo Variant ↔ canal (ML/Shopee/site): id externo, preço, status, última sincronização, erros.
- `ChannelFee` — tarifas por canal/categoria/tipo de anúncio (atualizadas via API quando possível).
- `Order` / `OrderItem` — pedidos unificados de todos os canais, com personalização do cliente.
- `PrintJob` — fila de impressão: arquivo fatiado, impressora, material, status, tempo estimado vs real, falhas.
- `Shipment` — etiqueta, rastreio, transportadora.
- `Customer`, `Conversation` (assistente de compras), `CustomDesignRequest` (peças alteradas pelo cliente).
- `ContentPiece` — posts e vídeos gerados, status no MayaPost.
- `AuditLog` — toda decisão automática da IA (publicou, bloqueou, mudou preço, respondeu cliente) com motivo.

---

## 2. Regras de negócio que o sistema precisa respeitar

### Precificação

Custo da peça:

```
material   = gramas × custo_por_grama(material)          # gramas vêm do fatiador, não da estimativa
energia    = (consumo_W / 1000) × horas × tarifa_kWh
desgaste   = horas × custo_hora_impressora
mao_obra   = minutos_pos_processamento × custo_minuto
custo_base = (material + energia + desgaste + mao_obra) × (1 + taxa_falha)
```

Preço por canal (cálculo "de trás pra frente"):

```
preco_canal = (custo_base + lucro_desejado + custo_por_unidade_canal + frete_assumido) / (1 - comissao_canal)
```

- `lucro_desejado` = max(lucro mínimo em R$, custo_base × margem da categoria).
- Mercado Livre: comissão varia por categoria e tipo de anúncio (Clássico/Premium); abaixo de ~R$ 79 existe custo por unidade que hoje depende de peso e dimensões da embalagem. **Consulte via API** (endpoint de tarifas/listing prices) a cada cálculo ou com cache curto.
- Shopee: comissão e taxa por item variam por faixa de preço. Buscar na documentação/API atual e guardar em `ChannelFee`.
- Site próprio: só taxa do meio de pagamento (Pix com desconto, cartão com taxa) + frete.
- Arredondamento psicológico (`,90`) **depois** de garantir que o lucro mínimo foi atingido.
- **Kits automáticos:** para peças baratas, o sistema gera kits que passem do limite do custo por unidade do ML e publica como anúncios separados.
- Recalcular e sincronizar preços automaticamente quando mudar: custo do filamento, tarifa de energia, tarifas do canal, perfil de impressão.

### Guardião de IP e segurança (substitui a aprovação manual)

Nenhuma peça é publicada sem passar por TODOS os filtros. Na dúvida, **descarta**, não publica.

1. **Licença:** só entram designs com licença que permita uso comercial (CC0, CC BY, licença comercial comprada, ou paramétricos próprios). Qualquer "NC", "non-commercial", "standard digital file license" ou licença desconhecida → descartado. Guardar a atribuição e incluí-la na descrição quando exigido.
2. **Lista de bloqueio textual:** times, clubes, personagens, franquias, marcas registradas, celebridades, termos como "lego", "disney", "marvel", "pokemon", "nintendo" etc. (lista configurável no admin, com normalização de acentos e variações).
3. **Visão computacional:** um modelo multimodal analisa os renders e responde em JSON estruturado se há logo, personagem, marca, escudo ou pessoa real reconhecível. Qualquer indício → bloqueado.
4. **Imprimibilidade:** malha fechada (ou reparável), espessura mínima, cabe na mesa da impressora ativa, volume de suporte aceitável, tempo máximo por peça.
5. **Segurança de produto:** itens que pareçam brinquedo para criança pequena (peças pequenas, blocos de montar) recebem automaticamente classificação **+14 anos / colecionável / decoração** no anúncio. Não anunciar como brinquedo infantil (exige certificação Inmetro).
6. **Blocos de montar:** nunca usar "LEGO" no título, descrição ou tags; usar "blocos de montar" / "compatível com blocos de montar". Não reproduzir minifiguras.
7. Toda decisão vai para `AuditLog` com motivo. O admin tem uma tela de "bloqueados" só para consulta (não para aprovar).

### 2.1 Nicho religioso — catálogo, regras e cuidados

**Meta do nicho religioso: 300+ produtos** (de um total de 720+), distribuídos assim (o Catalogador ajusta conforme vendas):

| Categoria | Qtd. | Exemplos |
|---|---|---|
| Nossa Senhora | 50 | Aparecida, Fátima, das Graças, Guadalupe, Desatadora dos Nós, Auxiliadora, do Carmo, Perpétuo Socorro, Rosa Mística, Lourdes |
| Jesus Cristo | 30 | Sagrado Coração, Misericordioso, Bom Pastor, Menino Jesus, Cristo crucificado |
| Santos | 60 | São Jorge, Santo Antônio, São Francisco, São Bento, São José, Santa Rita, São Judas Tadeu, Santa Teresinha, São Miguel Arcanjo, Santa Luzia, São Pedro, São Benedito, Santa Clara, Divino Espírito Santo |
| Cruzes e crucifixos | 30 | de parede, de mesa, com nome, São Bento, Tau, cruz vazia (público evangélico) |
| Presépios | 25 | completos, minimalistas, peças avulsas, presépio com nome da família |
| Lembrancinhas de sacramentos | 45 | batizado, primeira comunhão, crisma, casamento, ordenação — personalizadas com nome e data, vendidas em kits |
| Oratórios e capelinhas | 20 | oratório de parede/mesa, capelinha com nome da família |
| Terços e porta-terços | 15 | dezenas, porta-terço, caixinha de terço personalizada |
| Placas e mensagens de fé | 25 | "Deus abençoe este lar", Pai Nosso, Ave Maria, orações para porta/quarto de bebê |

**Fontes dos modelos (ordem de preferência):**
1. **Paramétricos próprios**: cruzes, oratórios, placas, lembrancinhas, porta-terços, caixas — com nome/data/frase personalizáveis. Devem ser a maior parte do catálogo de lembrancinhas, cruzes e placas.
2. **Pacotes com licença comercial comprados** de designers (principal fonte para imagens de santos, Nossa Senhora e presépios, que são esculturas orgânicas).
3. Modelos **CC0 / CC BY** que passem no Guardião.

**Regras específicas do Guardião para o nicho:**
- Iconografia religiosa tradicional (santos, Nossa Senhora, Jesus, cruz) é permitida, **mas cada modelo 3D tem autor e licença próprios** — a regra de licença continua valendo para toda peça.
- **Bloquear:** reproduções de obras/esculturas modernas protegidas; logotipos e marcas de santuários, dioceses, paróquias, congregações e movimentos; **Cristo Redentor** (a Arquidiocese do Rio cobra licenciamento do uso comercial da imagem — só liberar se houver licença); imagens de **papas e pessoas reais** (vivas ou recentes); qualquer conteúdo caricato, de deboche ou ofensivo à fé de qualquer religião.
- **Textos de orações e versículos:** orações tradicionais (Pai Nosso, Ave Maria, Credo) são de domínio público. **Traduções da Bíblia** em português geralmente têm direitos autorais (ex.: versões publicadas pela SBB e outras); usar apenas tradução comprovadamente em domínio público ou trechos curtos — pesquisar e registrar a regra num ADR antes de gerar placas com versículos.
- **Segurança:** **não vender porta-velas e castiçais de PLA/PETG** para velas de chama (o plástico deforma e pode pegar fogo). Se existir, só como "para vela LED", escrito no título e na descrição.
- Linguagem sempre respeitosa nos títulos, descrições, posts e respostas da IA. A "voz da marca" (BrandSettings) para este nicho é acolhedora e reverente, sem exageros comerciais.

**Qualidade das imagens (peças orgânicas):**
- Perfil de impressão "detalhe" para santos e imagens: camada fina, bico 0.2 mm quando disponível, impressão em pé com suportes em árvore.
- Variantes por acabamento: **"cor única"** (sai direto da impressora) e **"pintada à mão"** (preço maior, prazo maior, mão de obra no cálculo).
- O Redator deve informar no anúncio que é impressão 3D (linhas de camada podem ser visíveis) para evitar devolução por expectativa errada.
- Futuro: avaliar impressora de **resina** para imagens pequenas e muito detalhadas (registrar demanda no Analista).

**Calendário comercial religioso** (o Caçador de tendências e o CMS usam para campanhas, publicando com 4–6 semanas de antecedência):
- **Natal** (presépios — maior data do nicho), Páscoa, 12/10 Nossa Senhora Aparecida, 23/04 São Jorge, 13/06 Santo Antônio (e Festas Juninas), 22/05 Santa Rita, 28/10 São Judas Tadeu, 04/10 São Francisco, mês de maio (mês de Maria), Corpus Christi.
- Temporadas de **primeira comunhão, crisma e batizados** (lembrancinhas em kit).

**Clientes B2B:** paróquias, catequeses, pastorais, lojas de artigos religiosos e cerimonialistas — pedidos em quantidade (encaixam no fluxo de amostra acima de 10 unidades) e tabela de preço por volume.

### 2.2 Nichos automotivo, celular e brindes

**Meta destes três nichos: 100 produtos** (o catálogo total é 720+: ver tabela-resumo na seção 2.8), divididos assim (o Analista rebalanceia conforme as vendas):

| Nicho / categoria | Qtd. | Exemplos |
|---|---|---|
| Automotivo — acabamento e reposição | 30 | botões de painel/vidro/ar, presilhas e grampos de forro, tampas de porta-objetos, capas de parafuso, puxadores, porta-copos de reposição — organizados por **marca → modelo → ano** |
| Automotivo — acessórios e organização | 20 | organizadores de console, porta-moedas, gancho de banco para bolsa, suporte de lixeira, porta-óculos de quebra-sol, chaveiro de carro personalizado |
| Celular — suportes | 15 | suporte de mesa (vários ângulos), suporte para carro (saída de ar, painel), suporte de parede/cabeceira, suporte para gravar vídeo |
| Celular — capinhas e acessórios | 10 | capinhas personalizadas com nome/relevo (só para os modelos de celular mais vendidos), protetor de cabo, organizador de cabos, apoio de dedo |
| Brindes personalizados | 25 | chaveiros com logo, porta-cartão de visita, porta-caneta com nome, abridor de garrafa, marcador de página, troféus e medalhas simples, lembranças de evento, kits de fim de ano para empresas |

**Regras do Guardião para estes nichos:**
- **Marcas de carro e celular:** pode usar o nome **apenas de forma descritiva de compatibilidade** ("compatível com Gol G5 2009–2012", "para iPhone 15"). **Nunca** reproduzir emblemas, logotipos, escudos ou grafias estilizadas das montadoras/fabricantes (nada de emblema da VW, Fiat, Apple etc.) e nunca dar a entender que é peça original ou oficial. Título no padrão: "<peça> compatível com <marca> <modelo> <anos>".
- **Peças de segurança proibidas:** nada ligado a freio, direção, suspensão, cinto de segurança, airbag, fixação de rodas, sistema de combustível, componentes do motor ou qualquer peça cuja falha possa causar acidente. A lista de bloqueio do Guardião inclui esses termos.
- **Material obrigatório por uso:** dentro do carro a temperatura passa de 60–70 °C no sol, e **PLA deforma**. Peças automotivas usam no mínimo **PETG** (partes protegidas do sol) e **ASA** para painel, tampas e tudo exposto ao sol. Cada produto tem o campo **"material mínimo"**; se a impressora disponível não imprime aquele material (ASA exige impressora fechada), o produto fica **"indisponível – aguardando equipamento"** e não é publicado. Quando uma impressora fechada for cadastrada, esses produtos são liberados automaticamente.
- **Encaixe:** peças de reposição precisam de medidas confirmadas. O modelo paramétrico expõe as medidas críticas (diâmetro, encaixe, furo) e cada produto tem nível de confiança do encaixe; peças sem medidas validadas por uma impressão real de teste ficam como **"sob medida"** (o cliente informa medidas/foto, fluxo da seção 5.0 de amostra), não como produto de prateleira.
- **Capinhas:** só modelos de celular com medidas confiáveis e alta demanda; material **TPU** (flexível) com perfil próprio; foco em capinha **personalizada** (nome, relevo, cor), porque capinha lisa não compete em preço com as de fábrica. O Analista acompanha margem e pode pausar a categoria.
- **Brindes com logo de empresa:** o cliente sobe o próprio logo e declara nos termos que tem direito de uso. O Guardião bloqueia logos de marcas famosas enviados por quem claramente não é o dono (times, montadoras, marcas de consumo conhecidas).
- **Brindes B2B:** tabela de preço por volume, prazo calculado pela fila real de impressão, amostra obrigatória acima de 10 unidades (seção 5.0), orçamento em PDF gerado automaticamente.

**Voz da marca por nicho:** religioso = acolhedor e reverente; automotivo = técnico e objetivo (compatibilidade, material, medidas); celular = prático e moderno; brindes = profissional e criativo. O `BrandSettings` guarda a voz por nicho e os agentes usam a do produto.

**Vitrines:** a loja tem uma entrada por nicho (Religioso, Automotivo, Celular, Brindes), cada uma com seu banner, categorias e campanhas. No automotivo, a navegação principal é um **seletor "Meu carro" (marca → modelo → ano)** que filtra só o que é compatível, e fica salvo para o cliente.

**Calendário comercial destes nichos:** Black Friday e Natal (brindes corporativos e de fim de ano — pedidos B2B entre outubro e começo de dezembro), Dia dos Pais (automotivo e celular), Dia das Mães, volta às aulas, lançamentos de celulares (capinhas dos modelos novos).

### 2.3 Nicho datas comemorativas

**Meta do nicho: 100+ produtos** (o catálogo total é 720+: ver tabela-resumo na seção 2.8). Um produto pode pertencer a mais de um nicho/ocasião (ex.: presépio é religioso e Natal; chaveiro de carro personalizado é automotivo e Dia dos Pais) — usar tags de **ocasião** em vez de duplicar produto.

| Data | Qtd. | Exemplos |
|---|---|---|
| **Natal** | 25 | bolas e enfeites de árvore com nome da família, estrela/topo de árvore, Papai Noel e renas decorativos (desenho próprio), boneco de neve, guirlanda de porta, calendário do Advento, porta-guardanapo natalino, árvore de mesa geométrica, luminária natalina para LED, plaquinha "Natal da família ___", kit lembrancinha de amigo-secreto, marcador de lugar para a ceia |
| **Ano Novo** | 8 | números do ano decorativos ("2027"), topo de bolo/plaquinha "Feliz Ano Novo", porta-retrato de retrospectiva, enfeite de mesa para a virada, chaveiro "meta do ano" |
| **Páscoa** | 12 | coelho decorativo, cestinha de coelho para bombons, cenoura porta-bombom, porta-ovos de chocolate, suporte de ovo de Páscoa, lembrancinha de Páscoa para escola/catequese, cruz de Páscoa (liga com o nicho religioso) |
| **Dia das Mães** | 12 | vaso personalizado com nome, porta-joias, **litofania com foto** (Foto vira peça), placa "Melhor mãe do mundo", porta-retrato, porta-chaves de parede com nomes dos filhos, luminária com iniciais, porta-temperos/cozinha personalizado |
| **Dia dos Namorados** | 12 | **litofania do casal**, coração com nomes e data, chaveiros de casal que se encaixam, luminária com iniciais, porta-retrato coração, caixinha surpresa, mapa do lugar onde se conheceram em relevo, placa "Desde ___" |
| **Dia dos Pais** | 12 | porta-controle remoto, porta-chaves/carteira de parede, porta-copos de churrasco, abridor de garrafa personalizado, chaveiro de carro com nome, organizador de mesa, suporte de celular personalizado, troféu "Melhor pai" |
| **Dia das Crianças** | 8 | luminária com nome, porta-lápis personalizado, plaquinha de porta de quarto, cofrinho, organizador de brinquedos, quadro de altura (régua de crescimento) — **itens de decoração/uso, não brinquedos** |
| **Outras datas** | 11 | Dia dos Professores (porta-caneta, marcador de página com nome), Dia dos Avós, Dia da Mulher, Festa Junina (lembrancinhas), Halloween (abóbora decorativa para LED), formatura (lembrancinha com curso/ano), chá de bebê e chá revelação, aniversários (topo de bolo com nome e idade) |

**Ativação sazonal automática:**
- Cada produto de data tem uma **janela de venda**: o sistema publica/ativa nos canais **6 semanas antes** da data (8 semanas para Natal e B2B), destaca no site e no app nas últimas 3 semanas, e **pausa** automaticamente depois da data (exceto produtos que vendem o ano todo, como litofania e coração com nomes).
- Prazo de produção considerado: o sistema mostra ao cliente "**peça até __ para receber antes do Dia das Mães**", calculado pela fila real de impressão + frete, e para de aceitar pedidos com promessa de entrega quando não der tempo (o produto continua vendível sem a promessa).
- Datas móveis (Páscoa, Dia das Mães = 2º domingo de maio, Dia dos Pais = 2º domingo de agosto) calculadas automaticamente a cada ano. Datas fixas: Namorados 12/06, Crianças 12/10, Professores 15/10, Avós 26/07, Mulher 08/03, Halloween 31/10, Natal 25/12, Ano Novo 01/01.
- O Caçador de tendências, o CMS (landing de cada data) e o MayaPost (calendário de conteúdo) usam esse mesmo calendário, com tudo pronto antes de cada janela abrir.

**Regras do Guardião para datas comemorativas:**
- **Personagens proibidos:** nada de personagens de desenhos, filmes, games e marcas (Disney, Marvel, Pokémon, Patrulha Canina etc.), mesmo em Dia das Crianças e Natal. Papai Noel, coelho da Páscoa e similares só com **desenho próprio ou licença comercial**, sem imitar versões de marcas.
- **Dia das Crianças:** nada anunciado como brinquedo (exige certificação do Inmetro). Produtos são decoração e organização, com aviso de peças pequenas e indicação de idade quando necessário.
- **Contato com alimento:** PLA/PETG impressos têm porosidade e não são indicados para contato prolongado com comida. **Não vender formas de chocolate impressas**; cestinhas, porta-bombom e porta-ovos são para alimentos **embalados**, escrito no anúncio. Cortadores de biscoito só com aviso de uso rápido e lavagem.
- **Velas:** igual ao nicho religioso — itens de luz só para **LED**.
- **Fotos de clientes** (litofania, porta-retrato): seguem as regras do Foto vira peça (direito sobre a imagem, apagar após o pedido).

### 2.4 Nicho fitness (pilates, academia, cross training)

**Meta: 60 produtos.**

| Categoria | Qtd. | Exemplos |
|---|---|---|
| Pilates | 20 | miniatura decorativa de reformer/cadillac, chaveiro e brinde de pilates, organizador de meias antiderrapantes, porta-elásticos e faixas, placa de recepção do estúdio (com logo do próprio estúdio), porta-cartões de agendamento, plaquinha de nome para aparelho, troféu/lembrança de aniversário de aluna, placas de frases ("Respire", "Core forte") |
| Academia | 20 | suporte de celular para esteira/bike, porta-garrafa e porta-coqueteleira de parede, gancho para toalha e mochila, organizador de suplementos, porta-fones, cabide para cinto/luvas, medalhas e troféus de desafio, chaveiro de halter/kettlebell, placas motivacionais, porta-crachá de aluno |
| Cross training / funcional | 12 | medalhas e troféus de campeonato com nome do evento e do box (logo do próprio cliente), organizador de giz/magnésio, porta-corda, suporte de cronômetro/tablet de parede, chaveiro de kettlebell, placas do box |
| Corrida e outros | 8 | porta-medalhas de parede com nome, porta-número de prova, troféus de corrida, suporte de celular para braço (case) |

**Regras do Guardião para fitness:**
- **Nada que suporte carga ou o corpo:** proibido peso, anilha, clipe/trava de anilha, pegada, puxador, gancho de carga, peça de mola, peça estrutural de aparelho de pilates ou musculação, apoio de pés/mãos em aparelho — qualquer coisa cuja quebra machuque alguém. A lista de bloqueio inclui esses termos.
- **"CrossFit" é marca registrada** (e fiscalizada): **não usar** "CrossFit" em títulos, descrições ou tags. Usar "cross training", "treino funcional", "box". Mesma regra para nomes e logos de redes de academia e marcas de equipamentos (só "compatível com", nunca logo). Logo de estúdio/box/academia só quando o próprio cliente envia e declara ter direito.
- Peças que ficam em ambiente quente, úmido ou em contato com suor: material mínimo **PETG**.

**B2B fitness:** estúdios de pilates, academias e boxes são clientes de brindes (aniversário de aluno, fidelidade, campeonatos), placas e organização, com tabela de volume e amostra acima de 10 unidades. O CMS terá uma landing "Para o seu estúdio/academia". Integração futura com sistemas de gestão de estúdios (ex.: o PilatesFinal/MayaFit) para sugerir brindes em datas dos alunos — só registrar como ideia no backlog.

### 2.5 Nicho chaveiros personalizados (letra + nome)

**Meta: 80 produtos** (cada estilo de chaveiro × letras vira produto/variante buscável; ex.: "chaveiro letra J personalizado com nome").

**Produto-estrela — "Letra + Nome":** a letra inicial grande (ex.: **J** em branco) com o nome escrito pequeno e delicado sobre ela (ex.: "Jefferson" em preto).
- Modelo **paramétrico multicor**: base = letra (cor 1), nome em relevo nas últimas camadas (cor 2), argola de metal ou furo para argola.
- Imprime **com AMS** (troca automática) **ou sem AMS** (pausa automática na altura do nome para troca manual de filamento) — o sistema gera o 3MF certo para a impressora disponível.
- Disponível em **todas as letras A–Z** (com e sem acento, Ç), números 0–9 e símbolos simples (coração, estrela, cruz — esta liga com o nicho religioso).

**Estilos (cada um com todas as letras):**
1. Letra bold + nome (o clássico do exemplo)
2. Letra cursiva/manuscrita + nome
3. Letra com coração vazado + nome
4. Nome completo recortado (sem letra, só o nome em script)
5. Inicial + data (casamento, nascimento)
6. Letra com ícone temático (pata de cachorro, halter, bola, terço, carro)
7. Casal: duas letras que se encaixam, com os nomes
8. Família/turma: kit com várias letras

**Personalizador no site/app (sem login para montar):**
- Cliente escolhe estilo → letra → digita o nome → escolhe as cores (só cores em estoque) → fonte do nome (lista curta de fontes) → acabamento (argola, mosquetão, cordão).
- **Prévia 3D ao vivo** girando, com preço atualizando.
- **Validação automática de imprimibilidade:** se o nome ficar pequeno demais para imprimir legível (altura mínima de letra e largura de traço configuráveis por bico), o sistema avisa e sugere aumentar a letra, abreviar ou trocar a fonte. Limite de caracteres por estilo.
- "Adicionar mais um" para montar kits (família, padrinhos, turma da escola, formatura, equipe de empresa) com desconto progressivo.
- **Pedido em lote B2B:** upload de planilha (CSV/Excel) com a lista de nomes → gera todos os chaveiros, um arquivo de produção agrupado por cor e a mesa de impressão já organizada.

**Regras e cuidados:**
- **Fontes só com licença de uso comercial** (ex.: Google Fonts com licença OFL), registradas no sistema com a licença.
- Argola, mosquetão e cordão entram como **insumo com custo** no cadastro de produto (seção 5.5) e controle de estoque.
- Nomes digitados passam por filtro de palavrões e de marcas/personagens (ex.: digitar nome de time ou personagem não gera o escudo/logo — só o texto, e textos de marcas famosas são bloqueados).
- Na produção, agrupar chaveiros por par de cores para encher a mesa e minimizar trocas.

### 2.6 Nicho infantil — linha própria e personagens licenciados

**Linha própria "cãezinhos heróis" (meta: 20 produtos):**
- Criar uma **turma original** de 6 a 8 cachorrinhos com profissões (bombeiro, policial, resgate, construtor, médico, piloto...), com nomes, cores, uniformes e símbolos **criados por nós**.
- **Não pode parecer com nenhuma franquia existente:** o Guardião compara os conceitos e renders com personagens conhecidos (em especial séries de cachorrinhos de resgate) e bloqueia qualquer semelhança de nome, raça+cor+uniforme, símbolo, veículo ou bordão. Prefira raças, paletas e estilo visual claramente diferentes.
- Produtos: bonequinhos colecionáveis decorativos, chaveiros, topo de bolo, luminária com nome da criança e o personagem, plaquinha de porta, lembrancinha de aniversário em kit, porta-lápis.
- Registrar o conceito (nomes e desenhos) em `docs/linha-propria.md` e preparar o material para **registro de marca no INPI** quando a linha vender.
- Mesmas regras do Dia das Crianças: decoração e colecionáveis, não brinquedo; aviso de peças pequenas.

**Módulo de personagens licenciados:**
- Entidade `License`: licenciante, personagens/marcas cobertos, produtos e categorias autorizados, canais autorizados, território, validade, royalties (% ou valor por unidade), regras de aprovação de arte, arquivo do contrato.
- Produto com personagem de terceiros **só é criado e publicado se estiver vinculado a uma `License` vigente** que cubra aquele personagem, produto e canal. Sem licença, o Guardião bloqueia como sempre.
- Licença vencida → pausa automática em todos os canais e aviso no WhatsApp.
- Royalties entram no cálculo de custo e preço, e o sistema gera o relatório de vendas por licença para prestação de contas ao licenciante.
- Nenhum produto licenciado é criado nesta versão; o módulo fica pronto e vazio até eu cadastrar uma licença.

### 2.7 Nicho caixas e embalagens

**Meta: 60 produtos**, todos a partir de **um gerador paramétrico de caixas** (é o nicho mais fácil de escalar: um modelo, centenas de combinações).

**Formatos:** redonda, quadrada, retangular, hexagonal, coração, oval.
**Alturas:** baixa (tipo porta-joias), média, alta (tipo pote/cilindro), com tamanhos padrão de "mini" (≈ 4 cm) até o limite da mesa da impressora.
**Tampas:** de encaixe (pressão), rosca (redondas), deslizante, com dobradiça impressa, com ímã (ímã entra como insumo com custo), sem tampa (cachepô/organizador).
**Opções:** divisórias internas (2, 4, 6 compartimentos ou grade personalizada), espessura de parede, texto ou nome em relevo/baixo-relevo na tampa, logo do cliente na tampa, padrões decorativos (liso, frisado, geométrico, vazado), duas cores (caixa e tampa).

**Produtos de catálogo (exemplos):** porta-joias redondo com nome, caixinha de aliança, caixa de lembrancinha (batizado, casamento — liga com religioso e datas), caixa hexagonal de presente, porta-trecos de mesa, caixa de chá com divisórias, porta-cartões, caixa organizadora de miçangas/parafusos, pote alto com rosca, caixa de ímã para presente premium, caixa coração de Dia dos Namorados, caixa para terço (religioso), caixa de chaveiro (embalagem dos próprios chaveiros da seção 2.5).

**Configurador no site/app (sem login para montar):**
- Cliente escolhe formato → **medidas internas em mm** (largura, profundidade/diâmetro, altura) ou um tamanho pronto → tipo de tampa → divisórias → cores → texto/logo.
- Prévia 3D ao vivo (abre e fecha a tampa), preço e prazo atualizando na hora.
- Validações: medidas máximas pela impressora disponível, parede e fundo mínimos, folga da tampa calibrada por material (valores configuráveis no admin após testes de encaixe).
- Avisar quando a caixa ficar grande demais e o preço subir muito (caixa impressa grande custa mais filamento e horas de máquina do que papelão — o diferencial é ser **reutilizável, personalizada e premium**).

**B2B:** lojas de semijoias, confeitarias, perfumarias/cosméticos, cerimonialistas, lojas religiosas e empresas (kits de brinde) — tabela por volume, logo do cliente na tampa, amostra acima de 10 unidades (seção 5.0), pedido em lote.

**Embalagem própria:** as caixas também podem ser usadas como **embalagem premium dos nossos produtos** (ex.: santo pequeno em caixinha com nome), como opção paga no checkout ("embalagem de presente").

**Regras do Guardião para caixas:**
- **Alimentos:** caixas impressas não são próprias para contato direto com comida; para confeitarias, só para doces **embalados**, escrito no anúncio.
- **Ímãs:** ímãs pequenos são perigosos se engolidos — fixação embutida e colada, aviso "manter longe de crianças pequenas" em caixas com ímã.
- Logos na tampa só do próprio cliente (mesmas regras de brindes).

### 2.8 Resumo do catálogo

| Nicho | Meta | Seção |
|---|---|---|
| Religioso | 300 | 2.1 |
| Automotivo | 50 | 2.2 |
| Celular | 25 | 2.2 |
| Brindes | 25 | 2.2 |
| Datas comemorativas | 100 | 2.3 |
| Fitness | 60 | 2.4 |
| Chaveiros personalizados | 80 | 2.5 |
| Infantil (linha própria) | 20 | 2.6 |
| Caixas e embalagens | 60 | 2.7 |
| **Total** | **720+** | |

Produtos podem aparecer em mais de um nicho por tags (ex.: chaveiro letra + cruz no religioso, medalha de corrida em brindes). A contagem acima é de produtos únicos.

### 2.9 Frete e entrega local (Sorocaba)

- **Regra: entrega grátis em Sorocaba para pedidos a partir de R$ 100,00** no site e nos apps.
  - Valor considerado: subtotal dos produtos **depois de cupons e descontos**, sem o frete.
  - Cidade identificada pelo **CEP** (consulta de CEP retornando a cidade/código IBGE de Sorocaba), não por faixa de CEP fixa no código.
  - Valor mínimo, cidades atendidas e taxa de entrega local abaixo do mínimo ficam **configuráveis no admin** (para incluir cidades vizinhas no futuro, criar regras por bairro ou mudar o valor).
- **Abaixo de R$ 100 em Sorocaba:** taxa de entrega local configurável (valor fixo) **ou** opção de **retirada** sem custo, se eu ativar no admin.
- **Fora de Sorocaba:** cotação normal pelo Melhor Envio (Correios/transportadoras).
- **Na loja e no app:**
  - Barra de aviso: "Frete grátis em Sorocaba nas compras a partir de R$ 100".
  - No carrinho, ao detectar CEP de Sorocaba: barra de progresso "faltam R$ X para o frete grátis" com sugestões de produtos baratos para completar (o assistente de compras também sugere).
  - Na página do produto: "Entrega grátis em Sorocaba acima de R$ 100" quando o CEP salvo for de Sorocaba.
- **Operação da entrega local:**
  - Pedidos de Sorocaba entram numa lista **"Entregas locais"** no admin, agrupados por dia e por região/bairro, com rota sugerida (link de navegação com as paradas na ordem).
  - Status próprios: "Saiu para entrega" e "Entregue" (com foto ou confirmação do recebedor), notificando o cliente no WhatsApp como os outros status.
  - Pelo WhatsApp de operação: "entregas de hoje" → lista e rota; "1234 entregue" → atualiza e avisa o cliente.
- **Custo:** cada entrega local registra um custo estimado (km/tempo ou valor fixo configurável) para o Analista medir quanto o frete grátis está custando e o impacto no lucro dos pedidos de Sorocaba.
- **Marketplaces:** essa regra **não** se aplica ao Mercado Livre e à Shopee, que têm logística e regras de frete próprias. Pesquisar se a modalidade de entrega própria do ML para a mesma cidade (ex.: Mercado Envios Flex) está disponível para a conta e, se estiver, deixar como configuração opcional.

### Marketplaces

- Respeitar as regras de cada plataforma: não direcionar comprador do ML/Shopee para o site (nada de link, telefone ou cartão promocional no pacote ou na mensagem).
- Foto principal com fundo branco; fotos devem representar fielmente a peça.
- Peso e medidas cadastrados são **da embalagem**, não só da peça.

---

## 3. IA em todo lugar (o que deixa o sistema surpreendente)

Cada agente tem: prompt versionado em `/packages/ai/prompts`, saída em **JSON validado por Pydantic**, retry com correção, log de custo/latência, e um conjunto de casos de avaliação em `/packages/ai/evals` rodando no CI.

### Agentes de bastidor

1. **Curador de catálogo** — busca designs nas fontes permitidas (APIs oficiais quando existirem; respeitar termos de uso e robots), aplica o Guardião de IP, deduplica por similaridade (embeddings + hash geométrico) e enfileira para processamento.
2. **Designer paramétrico** — mantém uma biblioteca de **25+ modelos paramétricos próprios do nicho religioso** (cruzes de vários estilos com nome, crucifixo base para aplicar imagem, oratórios e capelinhas com nome da família, placas com orações/mensagens de fé, lembrancinhas de batizado/comunhão/crisma/casamento com nome e data, porta-terço, caixinha de terço, dezenas, chaveiros religiosos, medalhas, marcadores de página de Bíblia, plaquinha de porta de quarto de bebê com anjo, suporte para imagem, base/pedestal para imagens, peças avulsas de presépio estilizadas/minimalistas etc.) e gera variações automaticamente (tamanhos, estilos, textos de exemplo, cores) até completar o catálogo. Para os outros nichos (seção 2.2): suporte de celular de mesa e de carro com ângulo e largura ajustáveis, capinha TPU com nome por modelo de celular, botão/tampa/presilha automotiva com medidas críticas parametrizadas, organizador de console por medidas, chaveiro com logo, porta-cartão, porta-caneta com nome, troféu/medalha simples.
3. **Catalogador** — define o **nicho** e a categoria interna conforme as tabelas das seções 2.1 a 2.7, com subcategorias por invocação/santo e por ocasião, e mapeia para a categoria correta de cada marketplace usando a API de predição de categoria + atributos obrigatórios.
4. **Redator** — título otimizado para busca de cada canal (limite de caracteres de cada um), descrição com voz da marca, bullets de medidas/material/cuidados, atribuição de licença quando exigida, FAQ.
5. **Fotógrafo** — gera cenas de render no Blender: fundo branco (principal), cena lifestyle, referência de escala (mão/moeda), uma imagem por cor ativa, e GIF/vídeo de 360°.
6. **Precificador** — aplica a fórmula, consulta tarifas, decide Clássico vs Premium por margem e concorrência, cria kits.
7. **Caçador de tendências** — consulta tendências de busca dos marketplaces (APIs de trends, quando disponíveis) e sugere novos produtos paramétricos que atendam a demanda; gera e publica automaticamente se passar no Guardião.
8. **Atendente de marketplace** — responde perguntas de compradores no ML/Shopee com base nos dados reais do produto. Regras: nunca inventar prazo/medida, nunca direcionar para fora da plataforma, perguntas fora do escopo ou reclamações → me avisa no WhatsApp em vez de responder.
9. **Analista** — relatório diário e semanal: vendas por canal, margem real, peças campeãs e encalhadas, taxa de falha de impressão, sugestões de ajuste de preço.

### IA voltada ao cliente (loja própria)

1. **Busca semântica** — pgvector com embeddings de título, descrição, tags e da descrição visual do render. Entende frases como "presente pra quem gosta de plantas até 50 reais" ou "algo pra organizar cabo na mesa".
2. **Assistente de compras (chat)** — conversa, entende ocasião/orçamento/estilo, mostra produtos em cards dentro do chat, monta kits, tira dúvida de medida e prazo, e leva ao checkout. Usa function calling com ferramentas: `buscar_produtos`, `ver_variante`, `cotar_personalizacao`, `cotar_frete`, `adicionar_carrinho`.
3. **Estúdio de cores** — visualizador 3D (three.js) em que o cliente troca a cor de cada parte da peça, limitado às cores **realmente em estoque**. O preço recalcula ao vivo. Botão "ver na minha mesa" em AR via `<model-viewer>`.
4. **Personalizador por linguagem natural** — o cliente escreve "coloca o nome Ana, deixa 20% maior e a base hexagonal". A IA converte o pedido em **parâmetros do modelo paramétrico** (mapeamento seguro, validado por schema e limites). Gera prévia rápida no navegador e, em background, o arquivo final + preço + prazo.
   - Para pedidos que os parâmetros não cobrem, a IA pode gerar **código OpenSCAD/build123d** executado em **sandbox isolada** (container sem rede, limite de CPU/memória/tempo), validado pelo pipeline de imprimibilidade e pelo Guardião de IP. Se falhar, oferece a alternativa mais próxima.
5. **Foto vira peça** — o cliente envia uma imagem própria e escolhe: **litofania** (foto em relevo para luz), **placa multicor** (quantização de cores → camadas por cor → 3MF), **cortador de biscoito** (contorno), **chaveiro com silhueta**. Termos exigem que o cliente tenha direito sobre a imagem; o Guardião de IP analisa a imagem antes de aceitar.
6. **Sugestão inteligente** — "quem comprou isso também personalizou...", combinações de cores que harmonizam, alerta de "peça pequena demais para o texto escolhido".

---

## 4. Integrações

- **Mercado Livre:** OAuth com refresh automático; criar/editar/pausar anúncios; upload de imagens; predição de categoria e atributos; consulta de tarifas; preço e estoque; webhooks de pedidos, perguntas e mensagens; frete pelo Mercado Envios com peso/medidas da embalagem.
- **Shopee Open Platform:** autenticação de loja, produtos, imagens, preço/estoque, pedidos via push, logística.
- **Loja própria:** checkout com `PaymentProvider` (Pix com desconto + cartão). Primeiro avaliar o **banco Cora** para Pix/boleto via API; para cartão, escolher um gateway com API (pesquisar opções atuais e registrar a decisão num ADR). Frete via **Melhor Envio** (cotação e etiqueta).
- **WhatsApp:** `NotifyProvider` com duas implementações — reutilizar o **gateway do MayaSec** (Evolution API/WaSender) e a **Meta WhatsApp Cloud API** (template aprovado para "nova venda"). Configurável por env.
- **MayaPost:** enviar `ContentPiece` (mídia + dados do produto + link do canal certo) via API/webhook do MayaPost; o MayaPost cuida de legenda, agendamento e métricas. Lembrar: Instagram Graph API v22 usa `views` (impressions foi descontinuado).
- **Impressoras Bambu Lab:** pesquisar o método **oficialmente suportado hoje** para consultar status e iniciar impressões (a Bambu restringiu acesso de terceiros via firmware). Se não houver caminho oficial confiável, a fila de impressão funciona com o arquivo 3MF pronto para eu enviar manualmente, e o status é atualizado por mim no admin/WhatsApp.
- **Nota fiscal (fase posterior):** integração com emissor de NF-e (pesquisar opções compatíveis com MEI) disparada a cada pedido.

---

## 5. Painel admin (sem aprovações, só controle)

- Dashboard: vendas do dia/semana por canal, lucro real, fila de impressão, estoque de filamento em gramas com alerta de reposição.
- Catálogo: lista com filtros, status em cada canal, motivo de bloqueio do Guardião, botão "pausar em todos os canais".
- Custos: filamentos (preço/kg, cores, estoque), impressoras, tarifa de energia, mão de obra, margens por categoria, lucro mínimo.
- Pedidos: unificados, com personalização exibida e arquivo pronto para baixar.
- Fila de impressão: ordenada por prazo, agrupando peças da mesma cor/material para reduzir trocas.
- Auditoria: todas as decisões automáticas da IA com motivo.
- Configurações: lista de bloqueio do Guardião, fontes de designs, canais ativos, modelos de IA por tarefa.

---

## 5.0 Produção em tempo real e aprovação de amostra

### Status que atualiza o cliente sozinho
- No admin existe a tela **"Produção"**, pensada para o celular: cada pedido é um card com botões grandes de avanço de etapa (**Na fila → Imprimindo → Acabamento → Embalado → Enviado**).
- Cada toque grava o status com data/hora e **notifica o cliente na hora** (push no app, e-mail e WhatsApp conforme as preferências dele), atualizando a linha do tempo em "Meus pedidos".
- Ao marcar "Imprimindo", posso anexar foto ou vídeo com um toque (câmera do celular); a mídia aparece no pedido do cliente.
- Etiqueta do pacote com **QR code**: escanear pelo admin no celular marca "Embalado"/"Enviado" automaticamente.
- Se houver integração confiável com a impressora, "Imprimindo" e a previsão de término são atualizados automaticamente; senão, ficam manuais.
- Pedidos com várias peças mostram progresso parcial ("7 de 25 impressas").
- Pedidos de marketplace atualizam o status **dentro da plataforma** (ML/Shopee) pelas APIs, nunca por canal externo.

### Aprovação de amostra (pedidos grandes)
- Regra: se um item do pedido tiver **quantidade maior que 10** (limite configurável no admin), o fluxo é:
  1. Status **"Imprimindo amostra"** — imprimo 1 unidade.
  2. Tiro foto/vídeo pelo admin e marco **"Amostra pronta"**.
  3. O cliente recebe a notificação e, em "Meus pedidos", vê as fotos e escolhe **"Aprovar"** ou **"Pedir ajuste"** (com campo de texto e, opcionalmente, marcação na foto).
  4. **Aprovado** → o restante entra na fila automaticamente e eu sou avisado no WhatsApp.
  5. **Ajuste** → a IA interpreta o pedido, sugere a alteração nos parâmetros da peça, eu confirmo, e uma nova amostra é gerada (limite de rodadas gratuitas configurável; acima disso, cobra taxa de amostra).
- **Pula a amostra quando o item já foi produzido antes:** se a mesma combinação (design + parâmetros/personalização + material + cor) já foi impressa e aprovada/entregue em pedido anterior, vai direto para a produção total. Guardar uma "impressão digital" (hash) da combinação para essa verificação.
- Lembretes automáticos se o cliente não responder (ex.: 24h e 48h); o prazo de entrega fica **pausado** enquanto aguarda aprovação, e isso é mostrado ao cliente desde o checkout ("pedidos acima de 10 unidades passam por aprovação de amostra").
- Em marketplace, a amostra é enviada pela **mensageria pós-venda da própria plataforma**, se as regras permitirem; caso contrário, o fluxo de amostra vale só para site e apps.
- Tudo registrado no `AuditLog` (quem aprovou, quando, quais ajustes).

### WhatsApp como canal principal (cliente e operação)

**Para o cliente (site e apps):**
- O WhatsApp é o **canal principal** de comunicação do pedido: cada mudança de status chega como mensagem, com a foto/vídeo quando houver. Push e e-mail ficam como complemento.
- **Aprovação de amostra pelo WhatsApp:** o cliente recebe as fotos da amostra com **botões interativos "Aprovar" e "Pedir ajuste"**. Se pedir ajuste, responde em texto ou áudio, e a IA transcreve e interpreta. A resposta atualiza o pedido no sistema na hora (a área do cliente continua mostrando tudo).
- O cliente também pode perguntar "cadê meu pedido?" ou "quero mais 10 iguais" no WhatsApp, e o assistente responde com os dados reais dele (identificado pelo número cadastrado).
- Para mensagens com cliente, usar a **API oficial (Meta WhatsApp Cloud API)**: botões interativos, templates aprovados para status de pedido e sem risco de banimento do número da loja. Respeitar a janela de 24h e os templates para mensagens iniciadas pela loja; registrar o custo por conversa no painel.
- Opt-in de WhatsApp no cadastro (obrigatório pelas regras da Meta e pela LGPD).
- Pedidos de **Mercado Livre e Shopee continuam fora do WhatsApp**: comunicação só dentro das plataformas.

**Para mim (operação pelo WhatsApp):**
- Um agente de IA (mesma arquitetura do MayaSec: gateway → agente com function calling → ferramentas) entende comandos em texto, áudio e foto no meu número:
  - Mandar foto + "amostra pronta 1234" → anexa a foto e dispara a aprovação para o cliente
  - "1234 enviado" / "1234 imprimindo" → avança o status e notifica o cliente
  - "o que tenho pra imprimir hoje?" → fila do dia agrupada por cor/material
  - "quanto vendi essa semana?" → resumo de vendas e lucro
  - "pausa o chaveiro de nome em todos os canais" → pausa anúncios
  - "filamento PLA preto acabou" → marca a cor sem estoque e tira essa opção da loja
- Ações destrutivas ou em massa pedem confirmação por botão antes de executar.
- Só números autorizados no admin podem dar comandos.

## 5.1 Identidade visual da loja

Princípio: **a loja é neutra para as peças coloridas brilharem.** Fundo claro, pouca cor na interface, cor forte só em chamadas de ação.

| Token | Cor | Uso |
|---|---|---|
| `--bg` | `#F7F4EF` (areia clara) | fundo das páginas |
| `--surface` | `#FFFFFF` | cards de produto, modais |
| `--ink` | `#1E1E24` (grafite) | textos, cabeçalho, rodapé |
| `--muted` | `#6B7280` | textos secundários |
| `--primary` | `#FF6B2C` (laranja filamento) | botões de compra, preço, links principais |
| `--secondary` | `#14B8A6` (turquesa) | personalizador, badges "personalizável", sucesso |
| `--border` | `#E7E2DA` | divisórias e bordas |

- Modo escuro: `--bg #141418`, `--surface #1E1E24`, `--ink #F7F4EF`, mantendo primário e secundário.
- Tipografia: títulos em fonte geométrica (ex.: Space Grotesk), texto em Inter.
- Cards de produto com render em fundo branco, cantos arredondados, bolinhas das cores disponíveis abaixo do preço.
- Todos os tokens em CSS variables / Tailwind theme, para trocar a paleta sem mexer em componente.

## 5.2 Conta do cliente e login

- **Navegar não exige cadastro:** catálogo, busca por IA, assistente de compras, estúdio de cores, personalizador, AR e carrinho funcionam como visitante.
- **Comprar exige conta:** ao clicar em "Finalizar compra", abre o login. Depois de logar, o carrinho do visitante é **mesclado** à conta e o cliente volta exatamente para o checkout, sem perder personalização.
- **Login com Google** como opção principal (botão em destaque + **Google One Tap** no checkout), via Auth.js/NextAuth com provider Google (OAuth 2.0 / OpenID Connect). Alternativa: **link mágico por e-mail** (sem senha).
- No primeiro login, pedir só o que falta para entregar: **celular** (para avisos do pedido) e **CEP/endereço** (com preenchimento automático pelo CEP). CPF apenas no checkout, se o meio de pagamento/nota exigir.
- Consentimento LGPD no primeiro acesso logado: termos, privacidade e opt-in separado para marketing.
- Personalizações feitas como visitante ficam salvas por sessão e são vinculadas à conta no login.
- A mesma conta funciona no site e nos apps, com tudo sincronizado.

### Área do cliente ("Minha conta") — site e apps

- **Meus pedidos**
  - Lista com foto da peça (render da personalização exata), data, valor e status
  - **Linha do tempo do pedido:** pago → na fila → **imprimindo** (com previsão de término) → acabamento → embalado → enviado → entregue
  - Foto ou timelapse curto da peça dele sendo impressa, quando disponível
  - Rastreio integrado (Melhor Envio/transportadora) dentro da tela, sem mandar o cliente para outro site
  - Nota fiscal para download (quando a emissão estiver integrada)
  - Botões **"Comprar de novo"** e **"Comprar de novo em outra cor"**
  - Cancelamento enquanto o pedido ainda não entrou em impressão
- **Minhas criações:** todas as personalizações salvas (inclusive as não compradas), com prévia 3D, para editar, duplicar, compartilhar ou comprar
- **Favoritos** com aviso quando entrar uma cor nova ou o preço baixar
- **Endereços** (vários, com padrão) e **dados pessoais**
- **Pagamento:** cartões salvos apenas como token do gateway (nunca armazenar dados de cartão no nosso banco), Pix com desconto
- **Avaliações:** depois da entrega, pedir nota + foto da peça real; fotos aprovadas pelo Guardião viram prova social no produto (com autorização do cliente)
- **Trocas e devoluções:** solicitação dentro da conta, seguindo o Código de Defesa do Consumidor (direito de arrependimento em compras online) e uma política clara para peças personalizadas — a IA não decide sozinha, o pedido de troca me avisa no WhatsApp
- **Ajuda:** chat com o assistente da loja já sabendo os pedidos do cliente ("cadê meu pedido?" responde na hora); se não resolver, abre atendimento e me avisa no WhatsApp
- **Benefícios:** cupons, cashback em compras pelo site/app e link de indicação ("ganhe e dê desconto")
- **Notificações:** escolher o que receber por push, e-mail e WhatsApp (pedido sempre ativo; marketing só com opt-in)
- **Privacidade (LGPD):** baixar meus dados e excluir minha conta (obrigatório nas lojas de apps)
- Pedidos do Mercado Livre e da Shopee **não** aparecem aqui nem geram contato fora dessas plataformas (regra dos marketplaces). A área do cliente é só para compras feitas no site e nos apps.

## 5.3 Apps Android e iOS

- **Tecnologia:** Expo (React Native) + TypeScript + expo-router, no mesmo monorepo, compartilhando tipos, cliente da API, tokens de cor e lógica de preço/personalização com o storefront (`/packages/shared`).
- **Build e distribuição 100% na nuvem com EAS Build/Submit** — nada de Android Studio ou Xcode local (o Windows nem compila iOS). Pipeline: push na main → EAS build → **TestFlight** (iOS) e **teste interno da Play Store** (Android); produção por tag. Atualizações de JS via **EAS Update** (OTA) sem passar pela loja quando a mudança não envolver código nativo.
- **Login:** Google nativo **e Sign in with Apple** (a App Store exige uma opção equivalente quando o app oferece login social). Mesmo fluxo do site: navega sem conta, pede login só para comprar.
- **Pagamento:** produtos físicos usam o próprio gateway (Pix/cartão), sem compra in-app das lojas.
- **Experiência "uau" no app:**
  - **"Ver na minha mesa"** em realidade aumentada: Quick Look (USDZ) no iOS e Scene Viewer (GLB) no Android, abertos direto do produto
  - **Visualizador 3D** com troca de cores por toque e gesto de girar/zoom (react-three-fiber nativo)
  - **Foto vira peça** usando a câmera na hora
  - **Busca por voz** e assistente de compras em chat
  - **Push notifications:** pedido confirmado, "sua peça está sendo impressa" (com foto/timelapse curto quando disponível), enviado, entregue; lançamentos e promoções só com opt-in
  - Vibração sutil (haptics) ao trocar cor e adicionar ao carrinho, animações fluidas (Reanimated), modo escuro automático
  - Compartilhar produto/personalização com link que abre no app ou no site (deep links / universal links)
- **Contas de loja:** Apple Developer Program e Google Play Console no nome da empresa. Preparar ícone, splash, screenshots e textos das lojas (gerados pela IA a partir do catálogo).
- **Políticas:** página de privacidade, exclusão de conta dentro do app (exigência das duas lojas), formulário de segurança de dados (Play) e rótulos de privacidade (App Store).

## 5.4 Gerenciador do site (CMS no admin)

Quero alterar e publicar o site sozinho, sem mexer em código e sem novo deploy.

- **Editor visual de páginas** no admin, por blocos arrastáveis: banner principal (carrossel), vitrine de produtos (manual ou por regra: "mais vendidos", "categoria X", "novidades"), categorias em destaque, faixa de promoção, depoimentos/avaliações, timelapses, texto livre, FAQ, chamada para o app.
- Páginas editáveis: home, páginas de categoria, landing pages de campanha (ex.: Dia das Mães), "Sobre", políticas, FAQ, blog.
- **Rascunho → Pré-visualizar → Publicar**, com **agendamento** (publica e despublica sozinho em data/hora) e **histórico de versões** com botão de voltar.
- **Pré-visualização** em desktop e celular antes de publicar.
- Edição de **menu, rodapé, contatos, redes sociais, selo de frete grátis, barra de aviso**.
- **Tema:** trocar logo, favicon e os tokens de cor/fonte da seção 5.1 com prévia ao vivo.
- **SEO por página e produto:** título, descrição, imagem de compartilhamento, URL amigável; sitemap e dados estruturados de produto gerados automaticamente.
- **Promoções e cupons:** criar cupom, desconto por categoria, frete grátis acima de X, com datas de início/fim.
- **IA no CMS:** "cria uma landing de Dia das Mães com peças de presente até R$ 80" → a IA monta a página com blocos, textos e produtos certos como **rascunho** para eu revisar e publicar; gera textos de banner, sugestões de SEO e artes de banner com os renders das peças.
- **O mesmo conteúdo alimenta os apps:** banners, vitrines e campanhas aparecem no app via API, sem precisar publicar versão nova nas lojas.
- Publicação invalida o cache (revalidação sob demanda do Next.js), então a mudança aparece em segundos.
- **Uma edição, todos os canais:** qualquer mudança feita no admin em produto (título, descrição, fotos, preço, cores disponíveis, estoque, pausar/ativar) é propagada automaticamente para **Mercado Livre e Shopee** via API, respeitando as regras de cada um (limite de caracteres do título, campos que não podem mudar depois de vendas, fotos com fundo branco). O admin mostra, por produto, o status da sincronização em cada canal e o erro quando algo for recusado.
- **Promoções nos marketplaces:** ao criar uma campanha no admin, oferecer a opção de aplicar também como promoção/desconto no ML e na Shopee, usando as APIs de promoções de cada um (pesquisar o que está disponível hoje), sempre recalculando para não ficar abaixo do lucro mínimo.
- **Visual da loja dentro dos marketplaces** (banners e vitrine da página do vendedor/loja Shopee): pesquisar se há API oficial. Se houver, sincronizar banners das campanhas; se não, a IA gera as artes no tamanho exigido por cada plataforma e eu subo manualmente (avisar no WhatsApp quando houver arte nova para subir).
- Permissões: perfis de usuário do admin (dono, operador de produção, editor de conteúdo), para no futuro outra pessoa poder editar o site sem acessar custos e financeiro.

## 5.5 Telas de cadastro completas + botão "✨ Enriquecer com IA"

### Padrão para TODAS as telas de cadastro do admin
- Todo formulário (produto, cliente, material, impressora, campanha, página do CMS, cupom, kit) tem o botão **"✨ Enriquecer com IA"**: a pessoa digita poucas palavras e a IA preenche o resto.
- Também existe um botãozinho ✨ **por campo de texto** (ex.: só melhorar a descrição, só sugerir tags).
- A IA **nunca grava direto**: mostra as sugestões destacadas no próprio formulário (antes/depois) e eu aceito tudo, aceito por campo ou edito. Cada sugestão aceita fica registrada no `AuditLog`.
- **A IA não inventa números:** medidas, peso, gramas, tempo e custo vêm do pipeline 3D e das configurações. Se não houver dado, o campo fica marcado "a confirmar", nunca chutado.
- Componente reutilizável (`<AiEnrichButton schema=... context=...>`) com saída JSON validada pelo mesmo schema do formulário, para não ter um código diferente em cada tela.
- Usa a voz da marca do `BrandSettings` e as regras do nicho (seção 2.1).

### Cadastro de produto (bem completo)
Organizado em abas, com barra lateral mostrando **custo, preço por canal e lucro** atualizando ao vivo enquanto edito.

1. **Básico:** nome interno, título público, categoria e subcategoria (ex.: Nossa Senhora → Aparecida), ocasião (Natal, batizado, comunhão...), tags, status (rascunho/ativo/pausado), produto personalizável (sim/não).
2. **Arquivos 3D:** upload de STL/3MF/STEP ou escolha de um modelo paramétrico; origem e **licença** (com link e atribuição); status do Guardião de IP; visualizador 3D; parâmetros editáveis (texto, tamanho, estilo) com limites mínimo/máximo.
3. **Dimensões e peso:**
   - **Da peça:** largura × profundidade × altura (mm), volume, área de contato com a mesa, espessura mínima — calculados do arquivo, com opção de escala (%) que recalcula tudo.
   - **Da embalagem:** caixa escolhida de uma tabela de embalagens cadastradas (ou sugerida automaticamente), medidas e **peso total embalado** (usado no frete e nas tarifas dos marketplaces).
4. **Produção:** impressora(s) compatíveis, perfil de impressão (normal/detalhe), material, bico, preenchimento, suportes, **gramas por cor** e **tempo de impressão** (vindos do fatiador), peças por mesa (impressão em lote), tempo de pós-processamento (lixar, montar, pintar), taxa de falha específica da peça.
5. **Cores e variantes:** cores disponíveis (só as cadastradas em Materiais, com estoque), esquema multicor por parte da peça, variantes de tamanho e acabamento (**cor única / pintada à mão**), SKU automático por variante, render de cada variante.
6. **Custos (detalhado, por variante):** filamento por cor, energia, desgaste da máquina, mão de obra, pintura/acabamento, embalagem (caixa, proteção, etiqueta, brinde/cartão), taxa de falha → **custo total**. Todos calculados automaticamente, com campo de ajuste manual quando eu quiser sobrescrever (marcado como "manual").
7. **Preço por canal:** lucro desejado (R$ ou %), preço calculado e preço final no **site (Pix/cartão), Mercado Livre (Clássico/Premium) e Shopee**, com tarifa, frete e **lucro líquido** de cada um; tabela de preço por quantidade (B2B: 10, 50, 100 unidades); kits.
8. **Textos:** título por canal (respeitando limite de caracteres), descrição completa, bullets (medidas, material, cuidados, "feito em impressão 3D"), FAQ, texto de atribuição de licença.
9. **Mídias:** renders gerados, fotos reais, vídeo/timelapse, ordem das imagens, imagem principal com fundo branco.
10. **Canais:** liga/desliga por canal, status de sincronização, ID externo, categoria e **atributos obrigatórios** de cada marketplace, erros de publicação.
11. **SEO:** URL amigável, título e descrição para Google, imagem de compartilhamento.
12. **Estoque:** sob demanda (padrão) ou estoque pronto (quantidade), prazo de produção em dias.
13. **Histórico:** vendas, avaliações, alterações de preço e quem alterou.

**✨ Exemplo no produto:** digito "Nossa Senhora Aparecida 15cm manto azul" → a IA preenche título por canal, descrição acolhedora, categoria/subcategoria, ocasiões, tags, sugestão de cores (manto azul, coroa dourada, rosto bege), bullets, FAQ, SEO e atributos do ML/Shopee. Medidas, gramas e custo continuam vindo do arquivo e do fatiador.

### Cadastro de cliente (admin)
1. **Identificação:** tipo (pessoa física / **paróquia, igreja, loja ou empresa**), nome / razão social e nome fantasia, CPF ou CNPJ (com consulta automática de dados públicos do CNPJ), data de nascimento (opcional).
2. **Contato:** WhatsApp (com opt-in), e-mail, telefone, contato responsável (para paróquias/empresas).
3. **Endereços:** vários (entrega/cobrança), com preenchimento por CEP.
4. **Comercial:** origem (site, app, ML, Shopee, indicação, paróquia), segmento (fiel, catequese, cerimonialista, revendedor), tabela de preço (varejo/atacado), cupons e cashback, limite de crédito para B2B (opcional).
5. **Preferências:** canais de aviso, interesses (santos de devoção, ocasiões), datas importantes que **o cliente informou** (ex.: batizado do filho) para lembretes de campanha — só com consentimento.
6. **Histórico:** pedidos, valor total comprado, ticket médio, personalizações salvas, avaliações, conversas com o assistente e atendimentos.
7. **LGPD:** consentimentos com data, exportar dados, anonimizar/excluir.

**✨ Exemplo no cliente:** digito "paróquia são josé, catequese, compra lembrancinha de comunhão todo ano" → a IA preenche tipo, segmento, interesses, tags, sugestão de tabela de preço e um lembrete de campanha antes da temporada de comunhão. A IA **não busca nem inventa** dados pessoais na internet; dados oficiais só via consulta de CEP e CNPJ.

### Outras telas com o mesmo padrão
- **Materiais/filamentos:** marca, tipo, cor (nome + hex + foto), preço por kg, estoque em gramas, fornecedor, ponto de reposição. ✨: "PLA dourado silk Voolt" → nome, hex aproximado e sugestão de uso (coroas, detalhes).
- **Impressoras, embalagens, kits, cupons, campanhas, páginas do CMS**: todos com ✨.

## 6. Fases de execução

### Fase 0 — Fundação e CI/CD sem rodar nada localmente
- Monorepo, docker compose (staging e prod), Nginx + HTTPS, GitHub Actions (lint, typecheck, testes, build de imagens, deploy por SSH no prod2), scripts em `/ops`.
- Banco com pgvector, Alembic, Redis, storage GCS.
- Healthchecks e smoke tests pós-deploy.
- `CLAUDE.md` inicial.
- **DoD:** um push na main sobe API + admin + storefront "hello" em staging com HTTPS, e o pipeline fica verde.

### Fase 1 — Núcleo 3D e precificação
- Modelos de domínio e migrações.
- Pipeline: upload STL → análise (dimensões, volume, malha) → fatiamento CLI (gramas e tempo reais) → custo → preço por canal.
- Primeiros **10 modelos paramétricos** com geração de variações.
- Renders Blender (fundo branco + cada cor).
- Admin de custos e materiais.
- Telas completas de cadastro de produto, material, impressora e embalagem, com o componente "✨ Enriquecer com IA" (seção 5.5). O cadastro de cliente completo entra na Fase 5.
- **DoD:** cadastro de um paramétrico gera variantes com renders, gramas e preço de cada canal, visíveis no admin; testes do pricing engine com casos reais.

### Fase 2 — Catálogo autônomo de 720+ peças (9 nichos)
- Entidade `Niche` configurável (categorias, regras do Guardião, voz da marca, vitrine) e cadastro de compatibilidade veicular (marca → modelo → ano) e de modelos de celular.
- Agentes Curador, Designer paramétrico (25+ bases religiosas + 15+ de automotivo/celular/brindes + 10+ de fitness + 8 estilos de chaveiro letra+nome + a turma de cãezinhos heróis), Catalogador, Redator, Fotógrafo.
- Personalizador de chaveiros letra + nome (seção 2.5) com prévia 3D, validação de texto mínimo e pedido em lote por planilha.
- Gerador paramétrico de caixas e configurador com medidas, tampas e divisórias (seção 2.7), com teste de encaixe da tampa por material.
- Módulo `License` pronto e vazio (seção 2.6).
- Guardião de IP completo com as regras das seções 2.1 a 2.7, com evals no CI (casos que DEVEM ser bloqueados — ex.: Cristo Redentor sem licença, logo de santuário, papa, porta-vela de chama em PLA, emblema de montadora, peça de freio, painel em PLA, personagem de desenho em produto de Dia das Crianças, forma de chocolate impressa, "CrossFit" no título, trava de anilha, nome de chaveiro com palavrão ou marca, cãozinho parecido com personagem de franquia, produto de personagem sem licença vigente — e casos que DEVEM passar).
- Campo "material mínimo" por produto e liberação automática quando houver impressora capaz.
- Deduplicação.
- Prioridade de produção do catálogo: **presépios e itens de Natal + brindes corporativos de fim de ano primeiro** (datas mais fortes e mais próximas), depois Nossa Senhora, cruzes, lembrancinhas, santos, suportes de celular e automotivo.
- **DoD:** catálogo com 720+ produtos distribuídos conforme a tabela-resumo da seção 2.8, todos com licença válida, renders, preço e textos; relatório de bloqueados com motivos.

### Fase 3 — Mercado Livre
- OAuth, publicação em lote com controle de rate limit, sincronização de preço/estoque, webhooks de pedidos e perguntas, kits automáticos, Atendente de marketplace.
- **DoD:** catálogo publicado em conta real (começar com 10 anúncios e escalar), preços batendo com a fórmula considerando tarifas reais, pedido de teste chegando no sistema.

### Fase 4 — Shopee
- Mesma cobertura da Fase 3 via Shopee Open Platform.
- **DoD:** anúncios ativos e pedidos sincronizados.

### Fase 5 — Pedidos, fila de impressão e WhatsApp
- Pedidos unificados, fila de impressão otimizada por cor/material, etiquetas Melhor Envio (site) e envio dos marketplaces.
- Aviso de venda no WhatsApp: canal, peça, personalização, cor, valor, lucro estimado, tempo de impressão, prazo de envio e link do arquivo.
- Alertas: pergunta sem resposta, prazo de envio vencendo, estoque de filamento baixo, falha de sincronização. Resumo diário às 20h.
- Tela "Produção" mobile com avanço de status notificando o cliente, QR code na etiqueta e fluxo de aprovação de amostra (seção 5.0).
- **DoD:** venda simulada em cada canal gera aviso no WhatsApp e entra na fila; um pedido de 25 unidades passa pela amostra, é aprovado pelo cliente e libera o resto; um segundo pedido igual pula a amostra.

### Fase 6 — Loja própria com IA (o "uau")
- Storefront rápido (SSR/ISR, SEO, páginas por categoria), checkout Pix/cartão, frete.
- Busca semântica, assistente de compras, estúdio de cores 3D, AR, personalizador por linguagem natural, Foto vira peça.
- Preço do site menor que nos marketplaces, com desconto no Pix (regra configurável).
- Navegação completa sem login; login (Google/e-mail) só no checkout (seção 5.2).
- CMS no admin com editor de blocos, rascunho/agendamento/versões e IA (seção 5.4).
- **DoD:** cliente consegue do zero: descrever o que quer → personalizar → ver em 3D/AR → pagar → pedido na fila e aviso no WhatsApp.

### Fase 6.5 — Apps Android e iOS
- App Expo com catálogo, busca por IA, assistente, estúdio de cores, AR, Foto vira peça, carrinho, checkout, área do cliente e push.
- Login Google + Apple, deep links, EAS Build/Submit/Update no CI.
- **DoD:** app instalado via TestFlight e teste interno da Play Store fazendo uma compra completa; push de status do pedido chegando.

### Fase 7 — Conteúdo e redes sociais
- Geração automática de mídia por produto: render 360°, carrossel por cores, vídeo vertical.
- Pipeline de timelapse: recebe o vídeo da impressora/celular, corta, acelera, aplica marca e nome da peça com ffmpeg, envia ao MayaPost.
- Calendário de conteúdo sugerido pela IA (lançamentos, campeões de venda, datas comemorativas).
- **DoD:** cada produto novo gera pelo menos um post e um vídeo prontos no MayaPost.

### Fase 8 — Otimização contínua
- Analista diário/semanal no WhatsApp.
- Ajuste automático de preço dentro de limites (nunca abaixo do lucro mínimo), pausa de anúncios encalhados, reforço de campeões.
- Caçador de tendências gerando novos produtos.
- Nota fiscal integrada.
- **DoD:** relatório semanal com ações tomadas automaticamente e seus resultados.

---

## 7. Qualidade, segurança e observabilidade

- Testes unitários para pricing, Guardião de IP e pipeline 3D; testes de contrato com mocks das APIs externas; evals dos agentes de IA no CI.
- Logs estruturados (JSON), métricas de jobs (duração, falhas), alerta no WhatsApp para erro crítico.
- Rate limiting e retries com backoff em todas as integrações; idempotência em webhooks.
- LGPD: dados mínimos de cliente, política de privacidade, exclusão sob pedido, imagens enviadas pelos clientes apagadas após o pedido (prazo configurável).
- Sandbox de código gerado por IA: sem rede, sem acesso ao filesystem do host, limites de recursos e tempo.
- Backups diários (Postgres + GCS) com teste de restauração mensal automatizado em staging.
- Custos de IA: limite diário por agente, cache de respostas, modelo mais barato para tarefas simples e modelo mais forte para personalizador e Guardião.

---

## 8. Como começar agora

1. Leia este documento inteiro e me devolva: dúvidas bloqueantes (no máximo 5), um ADR inicial com as escolhas de stack que ficaram em aberto (fila, fatiador CLI, gateway de cartão) e o plano da Fase 0 em checklist.
2. Depois da minha resposta, execute a Fase 0 até a DoD.
3. Siga fase por fase, atualizando o `CLAUDE.md` e me mandando um resumo curto ao fim de cada uma.
