# Dépôt Home Assistant — Foyer Vault

Dépôt d’application (ex-add-on) pour Home Assistant OS.

## Ajouter dans HA (dépôt GitHub)

1. Créez un dépôt **public** sur GitHub (ex. `foyer-vault`).
2. Déposez à la racine :
   - `repository.yaml`
   - le dossier `foyer-vault/` (config.yaml, Dockerfile, build.yaml, server.py)
3. Dans Home Assistant : **Paramètres → Applications → ⋮ → Dépôts**
4. Collez l’URL du dépôt, du type :
   `https://github.com/VOTRE-COMPTE/foyer-vault`
5. Installez **Foyer Vault**, définissez un secret, démarrez.

Le serveur écoute sur le port **8099**. Dans Foyer : `http://IP-DU-HA:8099` + le secret.
