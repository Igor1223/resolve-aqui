# Resolve Aqui

Plataforma independente para ajudar pessoas a encontrar orientações simples sobre serviços e problemas do cotidiano.

## Funcionalidades desta base
- Site responsivo e PWA instalável.
- API Python com FastAPI.
- Cadastro e login com senha armazenada em hash e token JWT.
- Guias pesquisáveis e categorias.
- Favoritos e histórico de consultas.
- Assistente de IA opcional, ativado por variável de ambiente.
- Endpoint administrativo protegido por chave.
- Estrutura inicial para empacotar o site como Android usando Capacitor.

## Executar localmente
Requer Python 3.10+.

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

Abra http://127.0.0.1:8000. Documentação da API: http://127.0.0.1:8000/docs.

Copie `.env.example` para `.env` e configure os segredos. O FastAPI não carrega `.env` automaticamente nesta versão; exporte as variáveis no ambiente do servidor.

## IA
Defina `OPENAI_API_KEY` no ambiente do servidor. Sem essa chave, o restante do sistema funciona e o endpoint de IA informa que o recurso não está configurado. Nunca coloque a chave no JavaScript do navegador nem no Git.

## Android
Requer Node.js LTS, Android Studio e SDK Android.

```bash
npm install
npx cap add android
npx cap sync android
npx cap open android
```

Antes de gerar APK, configure no frontend a URL HTTPS pública da API. O app empacota a interface, mas o backend precisa estar hospedado para login, favoritos e IA funcionarem. Configure CORS, política de privacidade e assinatura do aplicativo.

## Segurança e limites
- Troque `SECRET_KEY` e `ADMIN_API_KEY` por valores fortes em produção.
- O banco atual é SQLite, adequado ao protótipo. Para produção com múltiplos usuários, implemente PostgreSQL e migrações.
- O endpoint administrativo usa uma chave no header; ainda não existe painel visual de administração.
- Os guias iniciais são exemplos e ainda não foram validados por órgãos públicos. Confirme procedimentos, links e documentos antes de uso público.
- O Resolve Aqui não é órgão público, não garante benefícios e não substitui orientação médica ou jurídica.
- Nunca solicite senhas gov.br ou códigos de autenticação.

## Próximos marcos
1. Testes automatizados e integração contínua.
2. Painel administrativo para revisar guias.
3. PostgreSQL e migrações.
4. Fontes oficiais verificadas por município e data de revisão.
5. Localização de serviços e acessibilidade avançada.
6. Build Android assinado e distribuição.
