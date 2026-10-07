/**
 * Cadastros simples do painel, descritos como dados. Uma tela genérica (lista + criar + editar
 * + remover) é gerada a partir daqui, espelhando os schemas da API (schemas/admin.py e
 * schemas/governance.py). Campo novo na API = uma linha aqui.
 */

export type FieldType =
  | "text"
  | "textarea"
  | "int"
  | "money"
  | "decimal"
  | "color"
  | "date"
  | "select"
  | "checkbox"
  | "checkboxes"
  | "list";

export interface Field {
  name: string;
  label: string;
  type: FieldType;
  required?: boolean;
  options?: readonly string[];
  hint?: string;
  createOnly?: boolean; // não editável depois de criado (slug, canal...)
  defaultValue?: string | number | boolean | readonly string[];
}

export type Cell = "text" | "money" | "color" | "bool" | "list" | "lowStock" | "percent";

export interface Column {
  name: string;
  label: string;
  cell?: Cell;
}

export interface Resource {
  slug: string; // rota do painel
  apiPath: string; // rota em /v1/admin
  title: string;
  singular: string;
  description: string;
  fields: readonly Field[];
  columns: readonly Column[];
  titleField: string;
}

const MATERIAL_KINDS = ["PLA", "PETG", "ASA", "ABS", "TPU", "PA", "PC", "RESINA"] as const;

export const RESOURCES: readonly Resource[] = [
  {
    slug: "materiais",
    apiPath: "/materials",
    title: "Materiais",
    singular: "material",
    description: "Filamentos: tipo, cor, preço por kg e estoque. Só cores ativas e em estoque aparecem na loja.",
    titleField: "color_name",
    fields: [
      { name: "kind", label: "Tipo", type: "select", options: MATERIAL_KINDS, required: true },
      { name: "color_name", label: "Nome da cor", type: "text", required: true },
      { name: "color_hex", label: "Cor", type: "color", required: true, defaultValue: "#FFFFFF" },
      { name: "brand", label: "Marca", type: "text" },
      { name: "finish", label: "Acabamento", type: "text", hint: "silk, matte, glitter…" },
      { name: "supplier", label: "Fornecedor", type: "text" },
      { name: "price_per_kg", label: "Preço por kg (R$)", type: "money", required: true },
      { name: "density_g_cm3", label: "Densidade (g/cm³)", type: "decimal", hint: "vazio = típica do tipo (PLA 1,24 · PETG 1,27 · ASA 1,07)" },
      { name: "stock_grams", label: "Estoque (g)", type: "int", defaultValue: 0 },
      { name: "reorder_point_grams", label: "Repor abaixo de (g)", type: "int", defaultValue: 500 },
      { name: "active", label: "Ativo", type: "checkbox", defaultValue: true },
    ],
    columns: [
      { name: "color_hex", label: "", cell: "color" },
      { name: "kind", label: "Tipo" },
      { name: "color_name", label: "Cor" },
      { name: "brand", label: "Marca" },
      { name: "price_per_kg", label: "R$/kg", cell: "money" },
      { name: "stock_grams", label: "Estoque (g)" },
      { name: "low_stock", label: "", cell: "lowStock" },
      { name: "active", label: "Ativo", cell: "bool" },
    ],
  },
  {
    slug: "impressoras",
    apiPath: "/printers",
    title: "Impressoras",
    singular: "impressora",
    description: "Máquinas disponíveis (ou planejadas). Área de impressão e consumo entram no custo e no encaixe das peças.",
    titleField: "name",
    fields: [
      { name: "name", label: "Apelido", type: "text", required: true },
      { name: "model", label: "Modelo", type: "text", required: true },
      { name: "bed_x_mm", label: "Mesa X (mm)", type: "int", required: true },
      { name: "bed_y_mm", label: "Mesa Y (mm)", type: "int", required: true },
      { name: "bed_z_mm", label: "Altura Z (mm)", type: "int", required: true },
      { name: "avg_watts", label: "Consumo médio (W)", type: "int", required: true },
      { name: "hourly_wear", label: "Desgaste por hora (R$)", type: "money", required: true },
      { name: "enclosed", label: "Fechada (necessária para ASA)", type: "checkbox" },
      { name: "has_ams", label: "Tem AMS (troca de cor)", type: "checkbox" },
      { name: "supported_materials", label: "Materiais que imprime", type: "checkboxes", options: MATERIAL_KINDS },
      { name: "status", label: "Status", type: "select", options: ["ativa", "inativa", "planejada"], defaultValue: "ativa" },
    ],
    columns: [
      { name: "name", label: "Apelido" },
      { name: "model", label: "Modelo" },
      { name: "bed_x_mm", label: "X" },
      { name: "bed_y_mm", label: "Y" },
      { name: "bed_z_mm", label: "Z" },
      { name: "supported_materials", label: "Materiais", cell: "list" },
      { name: "has_ams", label: "AMS", cell: "bool" },
      { name: "status", label: "Status" },
    ],
  },
  {
    slug: "embalagens",
    apiPath: "/packaging",
    title: "Embalagens",
    singular: "embalagem",
    description: "Caixas de envio. Peso e medidas embalados vão para frete e tarifas dos marketplaces.",
    titleField: "name",
    fields: [
      { name: "name", label: "Nome", type: "text", required: true },
      { name: "inner_x_mm", label: "Interno X (mm)", type: "int", required: true },
      { name: "inner_y_mm", label: "Interno Y (mm)", type: "int", required: true },
      { name: "inner_z_mm", label: "Interno Z (mm)", type: "int", required: true },
      { name: "weight_g", label: "Peso da caixa (g)", type: "int", required: true },
      { name: "cost", label: "Custo (R$)", type: "money", required: true },
      { name: "active", label: "Ativa", type: "checkbox", defaultValue: true },
    ],
    columns: [
      { name: "name", label: "Nome" },
      { name: "inner_x_mm", label: "X" },
      { name: "inner_y_mm", label: "Y" },
      { name: "inner_z_mm", label: "Z" },
      { name: "weight_g", label: "Peso (g)" },
      { name: "cost", label: "Custo", cell: "money" },
      { name: "active", label: "Ativa", cell: "bool" },
    ],
  },
  {
    slug: "tarifas",
    apiPath: "/channel-fees",
    title: "Tarifas por canal",
    singular: "faixa de tarifa",
    description:
      "Comissão e taxa fixa por faixa de preço. Nunca ficam no código: até as integrações com ML/Shopee, cadastre conferindo a tabela oficial de cada canal.",
    titleField: "channel",
    fields: [
      { name: "channel", label: "Canal", type: "text", required: true, createOnly: true, hint: "ex.: mercadolivre_classico, shopee, site_pix" },
      { name: "category", label: "Categoria (vazio = todas)", type: "text" },
      { name: "min_price", label: "Preço a partir de (R$)", type: "money", defaultValue: "0" },
      { name: "max_price", label: "Preço abaixo de (R$, vazio = sem limite)", type: "money" },
      { name: "commission_rate", label: "Comissão", type: "decimal", required: true, hint: "0.12 = 12%" },
      { name: "fixed_fee", label: "Taxa fixa por unidade (R$)", type: "money", defaultValue: "0" },
      { name: "notes", label: "Observações / fonte", type: "textarea" },
    ],
    columns: [
      { name: "channel", label: "Canal" },
      { name: "category", label: "Categoria" },
      { name: "min_price", label: "De", cell: "money" },
      { name: "max_price", label: "Até", cell: "money" },
      { name: "commission_rate", label: "Comissão", cell: "percent" },
      { name: "fixed_fee", label: "Taxa fixa", cell: "money" },
    ],
  },
  {
    slug: "nichos",
    apiPath: "/niches",
    title: "Nichos",
    singular: "nicho",
    description: "Ramos do negócio. Criar um nicho novo é cadastro, não código. A voz orienta os textos da IA.",
    titleField: "name",
    fields: [
      { name: "slug", label: "Identificador", type: "text", required: true, createOnly: true, hint: "minúsculas e hífen" },
      { name: "name", label: "Nome", type: "text", required: true },
      { name: "target_count", label: "Meta de produtos", type: "int", defaultValue: 0 },
      { name: "voice", label: "Voz da marca neste nicho", type: "textarea" },
      { name: "categories", label: "Categorias", type: "list", hint: "separadas por vírgula" },
      { name: "sort_order", label: "Ordem", type: "int", defaultValue: 0 },
      { name: "active", label: "Ativo", type: "checkbox", defaultValue: true },
    ],
    columns: [
      { name: "name", label: "Nicho" },
      { name: "slug", label: "Identificador" },
      { name: "target_count", label: "Meta" },
      { name: "active", label: "Ativo", cell: "bool" },
    ],
  },
  {
    slug: "licencas",
    apiPath: "/licenses",
    title: "Licenças",
    singular: "licença",
    description: "Personagens e marcas licenciados. Sem licença vigente, o Guardião bloqueia.",
    titleField: "licensor",
    fields: [
      { name: "licensor", label: "Licenciante", type: "text", required: true },
      { name: "covered_terms", label: "Personagens/marcas cobertos", type: "list", required: true, hint: "separados por vírgula" },
      { name: "categories", label: "Categorias permitidas (vazio = todas)", type: "list" },
      { name: "channels", label: "Canais permitidos (vazio = todos)", type: "list" },
      { name: "territory", label: "Território", type: "text" },
      { name: "valid_from", label: "Válida de", type: "date", required: true },
      { name: "valid_until", label: "Válida até", type: "date", required: true },
      { name: "royalty_pct", label: "Royalty (%)", type: "decimal", hint: "0.08 = 8%" },
      { name: "royalty_per_unit", label: "Royalty por unidade (R$)", type: "money" },
      { name: "approval_rules", label: "Regras de aprovação de arte", type: "textarea" },
      { name: "contract_url", label: "Link do contrato", type: "text" },
      { name: "active", label: "Ativa", type: "checkbox", defaultValue: true },
    ],
    columns: [
      { name: "licensor", label: "Licenciante" },
      { name: "covered_terms", label: "Cobre", cell: "list" },
      { name: "valid_from", label: "De" },
      { name: "valid_until", label: "Até" },
      { name: "active", label: "Ativa", cell: "bool" },
    ],
  },
  {
    slug: "clientes",
    apiPath: "/customers",
    title: "Clientes",
    singular: "cliente",
    description: "Pessoas, paróquias, lojas e empresas. WhatsApp só recebe mensagens com opt-in (Meta e LGPD).",
    titleField: "name",
    fields: [
      { name: "kind", label: "Tipo", type: "select", options: ["pf", "pj"], defaultValue: "pf", hint: "pf = pessoa · pj = paróquia, loja, empresa" },
      { name: "name", label: "Nome / nome fantasia", type: "text", required: true },
      { name: "legal_name", label: "Razão social", type: "text" },
      { name: "document", label: "CPF/CNPJ", type: "text" },
      { name: "email", label: "E-mail", type: "text" },
      { name: "whatsapp", label: "WhatsApp", type: "text", hint: "formato +5515999999999" },
      { name: "whatsapp_opt_in", label: "Aceitou avisos por WhatsApp", type: "checkbox" },
      { name: "marketing_opt_in", label: "Aceitou marketing", type: "checkbox" },
      { name: "segment", label: "Segmento", type: "text", hint: "fiel, catequese, cerimonialista, revendedor…" },
      { name: "notes", label: "Observações", type: "textarea" },
    ],
    columns: [
      { name: "name", label: "Nome" },
      { name: "kind", label: "Tipo" },
      { name: "whatsapp", label: "WhatsApp" },
      { name: "whatsapp_opt_in", label: "Opt-in", cell: "bool" },
      { name: "segment", label: "Segmento" },
    ],
  },
  {
    slug: "termos",
    apiPath: "/guardian/terms",
    title: "Termos do Guardião",
    singular: "ajuste",
    description: "Acrescente termos para bloquear ou remova um termo padrão que esteja gerando falso positivo.",
    titleField: "term",
    fields: [
      { name: "term", label: "Termo", type: "text", required: true, createOnly: true },
      { name: "mode", label: "Ação", type: "select", options: ["add", "remove"], required: true, createOnly: true, hint: "add = bloquear · remove = deixar de bloquear" },
      { name: "rule_code", label: "Regra (opcional)", type: "text", createOnly: true, hint: "ex.: marca_famosa; vazio = lista do admin / todas" },
      { name: "reason", label: "Motivo", type: "textarea" },
    ],
    columns: [
      { name: "term", label: "Termo" },
      { name: "mode", label: "Ação" },
      { name: "rule_code", label: "Regra" },
      { name: "reason", label: "Motivo" },
    ],
  },
];

export function findResource(slug: string): Resource | undefined {
  return RESOURCES.find((r) => r.slug === slug);
}
