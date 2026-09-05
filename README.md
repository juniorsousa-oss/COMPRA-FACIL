# Compra Fácil — Streamlit

Aplicativo reconstruído em Python/Streamlit com Supabase como banco único.

## Publicar no Streamlit Community Cloud

1. Entre no Streamlit Community Cloud e faça login com GitHub.
2. Clique em **Create app**.
3. Repository: `juniorsousa-oss/COMPRA-FACIL`
4. Branch: `main`
5. Main file path: `app.py`
6. Em **Advanced settings / Secrets**, cole:

```toml
SUPABASE_URL = "https://cuixazpxkvniqldmmnth.supabase.co"
SUPABASE_KEY = "SUA_CHAVE_PUBLICAVEL"
```

7. Clique em **Deploy**.

O Streamlit vai gerar um endereço público `*.streamlit.app`.

## Banco compartilhado

A aplicação usa o projeto Supabase `cuixazpxkvniqldmmnth` como base central. Lista atual, orçamento, produtos e histórico ficam no banco, portanto o conteúdo pode ser acessado de computadores e celulares diferentes.

## Segurança

A versão atual foi preparada para teste compartilhado. Antes de uso corporativo, adicionar autenticação e RLS por usuário/empresa.

