# CHANGELOG — Ajustes P0 (pré-primeiro-commit)

Correções de severidade **P0** aplicadas às configurações antes do primeiro commit do núcleo
determinístico. Cada item tem potencial de quebrar o teste gating ou de produzir minuta
juridicamente incorreta. A fonte da verdade são os YAMLs em `config/`; os blocos YAML
embutidos no documento de requisitos `.md` são rascunhos e **não** são normativos.

## 1. Códigos canônicos do checklist

- O gabarito do caso-ouro usava `EXTRATO_RENDIMENTO` e `IRPF_OU_ISENTO`; o checklist
  congelado define `EXTRATO_RENDIMENTO_FONTE_PAGADORA` e `IRPF_OU_DECLARACAO_ISENTO`.
- **Decisão:** os códigos canônicos são os do `checklist_iptu.yaml` (congelado, v1.0.0).
  A fixture do caso-ouro e os testes passam a usá-los. O `.md` fica como referência
  não-normativa.

## 2. Mapa correto do Decreto nº 34.767/2018

- O `.md` atribuía `art. 3º` a "imóvel único" e `art. 6º` a "outras fontes de renda".
- O `legal_references.yaml` mapeia corretamente `art. 3º` = outras fontes de renda e
  `art. 7º` = indeferimento de plano — que é o mapa que reproduz o fundamento do caso-ouro.
- **Mudança (`legal_references.yaml` → 1.2.0):** mapa confirmado e travado, com nota de
  supersessão registrada nas `notes` do decreto.

## 3. Status de norma revogada

- A Lei nº 4.158/1992 (REVOGADA pela Lei nº 8.430/2025) e o Decreto nº 34.767/2018
  (REVOGADO pelo Decreto nº 42.621/2025) continuam sendo fundamento para processos do seu
  período de vigência.
- **Mudança (`legal_references.yaml` → 1.2.0):** adicionada a seção `revocation_policy`,
  com regra de engenharia explícita: o motor não recusa citar norma revogada; cita a norma
  vigente à época do processo.

## 4. Tabela explícita de precedência da conclusão

- A lógica de conclusão estava dispersa em várias chaves; o caso-ouro depende de
  `NAO_APRESENTADO` ter precedência sobre `VERIFICAR`.
- **Mudança (`business_rules.yaml` → 1.2.0):** adicionada a seção `conclusion_resolution`
  com tabela ordenada (R1→R5), `legal_basis_augmentation` (que soma o art. 3º ao fundamento)
  e `non_determinant_warnings` (múltiplas inscrições como aviso, não como determinante).
- **Reconciliação acoplada (P0/P1):** `summary_denial.legal_regime_rules.DEC_42621_2025`
  passou de `enabled: true` (atribuído tentativamente ao art. 5º) para `enabled: false`
  com `status: PENDING_CONFIRMATION`. O art. 5º do Decreto 42.621 trata de documento/declaração
  **falsa**, não de ausência de documento — não fundamenta indeferimento de plano. Sob esse
  regime, documento ausente rebaixa para `VERIFICAR_MANUALMENTE`.

## Versões resultantes

| Config | Antes | Depois | Frozen |
|---|---|---|---|
| `legal_references.yaml` | 1.1.0-poc-legal-review | **1.2.0-poc-p0-fixes** | não |
| `business_rules.yaml` | 1.1.0-poc-legal-review | **1.2.0-poc-p0-fixes** | não |
| `checklist_iptu.yaml` | 1.0.0-poc | 1.0.0-poc (inalterado) | sim |
| `conclusion_mapping.yaml` | 1.1.0-poc-legal-review | inalterado | não |
| `document_taxonomy.yaml` | 1.0.0-poc | inalterado | sim |

A dependência declarada `business_rules.depends_on.legal_references_version` foi atualizada
para `1.2.0-poc-p0-fixes` e é validada em tempo de carga pelo `ConfigLoader`.

## Pendências P1 conhecidas (fora deste lote)

Registradas para o próximo ciclo, não bloqueiam o núcleo:

1. Inversão de congelamento: `checklist_iptu` congelado depende de fatos temporais ainda
   pendentes em `legal_references` (idade do comprovante de residência, prazos da matrícula).
   Recomenda-se mover esses fatos para `legal_references` como fonte única.
2. Três listas divergentes de vínculo com o imóvel (`document_taxonomy` não tem
   `COPROPRIETARIO` nem `TITULAR_DOMINIO_UTIL`).
3. Vocabulário de gatilho de "outras rendas" em três dialetos.
4. Ausência de `prompts.yaml` versionado, embora `prompt_version` seja exigido na auditoria.
5. `CERTIDAO_OBITO` duplicado em `COMPROVANTE_ESTADO_CIVIL`.
