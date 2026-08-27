# HomeBudget — interface Home Assistant

Sert l’application HomeBudget. **Foyer Vault reste séparé** (coffre chiffré).

## Installation (même dépôt que le vault)

Le dépôt GitHub `Gku86/foyer-vault` contient deux apps :

- `foyer-vault` — déjà installée
- `homebudget` — celle-ci

1. GitHub : déposer le dossier `homebudget/` à la racine du dépôt (à côté de `foyer-vault/`).
2. HA → **Paramètres → Applications → ⋮ → Rechercher des mises à jour**.
3. Installer **HomeBudget**, démarrer. Port **8100**.
4. Tunnel Cloudflare (hostname **différent** du vault), ex. `https://budget.fchvtn.ovh` → `http://127.0.0.1:8100`.
5. Ouvrir cette URL. La synchro continue d’utiliser `https://foyer.fchvtn.ovh`.

## Mise à jour

1. Remplacer le contenu de `homebudget/` (surtout `www/` et `config.yaml` — incrémenter `version`).
2. Pousser sur GitHub.
3. HA → Applications → HomeBudget → **Mettre à jour**.

Ne désinstallez pas Foyer Vault.
