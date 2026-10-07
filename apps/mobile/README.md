# apps/mobile — app Android e iOS (Expo)

Expo SDK 57 (React Native 0.86) + TypeScript + expo-router, no mesmo monorepo. Fala direto
com a API pública da loja (`/v1/store`) e usa os tipos e o tema de `@print3d/shared`.

## O que o app faz hoje
- Início montado no painel (aviso, destaque, vitrines), temas, páginas institucionais
- Busca (palavra e significado) e assistente de compra
- Produto com fotos, opções, cores, personalização e quantidade (vibração ao escolher)
- Carrinho (o mesmo da loja web, guardado na API), frete por CEP (local, Melhor Envio)
- Checkout com Pix; "Meus pedidos" no aparelho com o andamento e a chave Pix para copiar
- Marca, cores claro/escuro e nome vindos do painel (Marca); nada fixo no código

Próximos (dependem de domínio/contas): login Google + Apple, push de status, AR "ver na mesa",
visualizador 3D, Foto vira peça com a câmera, deep links.

## Nada roda no Windows
- CI (`ci.yml`): tipos, testes e `expo export` (empacota o JavaScript) a cada push.
- Build nativo e envio às lojas: **EAS** na nuvem (`mobile.yml`), disparado por tag `app-vX.Y.Z`.

## Para publicar (uma vez)
1. Conta em expo.dev → `eas init` gera o **EAS_PROJECT_ID**.
2. Contas de loja no nome da empresa: Apple Developer Program e Google Play Console.
3. Secrets do repositório: `EXPO_TOKEN`, `EAS_PROJECT_ID`, `APP_ID` (ex.: `com.empresa.loja`),
   `APP_NAME`, `EXPO_PUBLIC_API_URL` (`https://api.<domínio>` — **exige domínio com HTTPS**).
4. Criar a tag `app-v0.1.0`: o EAS gera Android + iOS e envia para teste interno / TestFlight.

Sem domínio, o app aponta para o IP da API por HTTP (liberado só enquanto o endereço começar
com `http://`; com `https://` a liberação some sozinha).
