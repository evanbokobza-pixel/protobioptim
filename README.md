# Protobioptim

`protobioptim` est le repo technique du projet `Bioptim`, reconstruit sur une base plus simple a deployer :

- `FastAPI` pour le backend
- `Postgres` via `Supabase`
- `Supabase Storage` pour les fichiers
- `Render` pour l'hebergement

Le projet fonctionne aussi en mode local avec :

- `SQLite` si `DATABASE_URL` n'est pas renseignee
- stockage local si `STORAGE_BACKEND=local`

Cela permet de developper et verifier l'application sans bloquer sur les services cloud, tout en gardant une architecture deploiement-ready.

## Fonctionnalites

- creation de compte et connexion
- espace patient
- commande d'abonnement ou de demande unique
- depot de fichiers d'analyses
- suivi des demandes
- espace admin pour traiter les dossiers

## Lancer en local

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

Puis ouvrir :

```text
http://127.0.0.1:8000
```

## Variables importantes

- `DATABASE_URL`
  pour Supabase Postgres en production
- `SUPABASE_URL`
  url du projet Supabase
- `SUPABASE_SERVICE_ROLE_KEY`
  cle service role du projet Supabase
- `SUPABASE_STORAGE_BUCKET`
  bucket prive pour les analyses
- `SESSION_SECRET_KEY`
  secret des sessions FastAPI

## Deploiement Render

Render sait deployer FastAPI avec :

- `Build Command`: `pip install -r requirements.txt`
- `Start Command`: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Le fichier `render.yaml` est deja prepare.

## Setup Supabase

1. creer un projet Supabase
2. recuperer l'URL du projet et la `service_role`
3. recuperer la connection string Postgres
4. creer ou laisser l'app creer le bucket `bioptim-files`
5. renseigner les variables dans Render

## Notes

- le paiement reste volontairement fictif pour l'instant
- pour un usage reel avec de vraies donnees de sante, il faudra ajouter un vrai cadrage securite, conformite et hebergement adapte
