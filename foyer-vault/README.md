# Foyer Vault — application Home Assistant

Stocke le **coffre déjà chiffré** de Foyer et, à part, les **fichiers chiffrés** (photos, PDF). Home Assistant ne voit ni les budgets ni les images.

Mettre à jour le module en **1.3.0** pour le stockage fichiers. Limites : 4 Mo par fichier, 64 Mo au total.

## Via GitHub (recommandé si HA demande une URL)

1. Créez un dépôt GitHub **public**.
2. À la racine du dépôt : `repository.yaml` + dossier `foyer-vault/`.
3. Dans HA : **Paramètres → Applications → ⋮ → Dépôts** → coller
   `https://github.com/VOTRE-COMPTE/nom-du-depot`
4. Installer **Foyer Vault** → secret → Démarrer. Port **8099**.
6. Dans Foyer : `http://IP-DU-HA:8099` + le même secret.
7. Notifications (optionnel) : HTTPS + **Notifications du foyer** dans Synchronisation. Tous les téléphones du coffre. iPhone : ajouter l’app à l’écran d’accueil.

## Sans GitHub (dossier local)

Copier uniquement le dossier `foyer-vault` dans le partage **addons** de HA, puis **Paramètres → Applications**.
