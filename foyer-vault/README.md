# Foyer Vault — application Home Assistant

Stocke le **coffre déjà chiffré** de Foyer. Home Assistant ne voit pas les budgets.

## Via GitHub (recommandé si HA demande une URL)

1. Créez un dépôt GitHub **public**.
2. À la racine du dépôt : `repository.yaml` + dossier `foyer-vault/`.
3. Dans HA : **Paramètres → Applications → ⋮ → Dépôts** → coller
   `https://github.com/VOTRE-COMPTE/nom-du-depot`
4. Installer **Foyer Vault** → secret → Démarrer. Port **8099**.
6. Dans Foyer : `http://IP-DU-HA:8099` + le même secret.
7. Notifications (optionnel) : HTTPS + **Notifications du foyer** dans Synchronisation. Tous les téléphones du coffre. iPhone : ajouter l’app à l’écran d’accueil. Mettre à jour le module en **1.2.0**.

## Sans GitHub (dossier local)

Copier uniquement le dossier `foyer-vault` dans le partage **addons** de HA, puis **Paramètres → Applications**.
